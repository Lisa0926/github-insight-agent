# -*- coding: utf-8 -*-
"""
Resilient HTTP client

Provides:
- Exponential backoff retry
- Timeout handling
- Graceful degradation for 429 rate limiting
- Circuit breaker pattern

Reliable retry logic based on the tenacity library.
"""

import asyncio
import time
from typing import Any, Dict, Optional, Callable
from functools import wraps

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)

from src.core.logger import get_logger

logger = get_logger(__name__)


class _AdaptiveRateLimiter:
    """Dynamic rate limiter that adjusts based on 429 responses.

    - On 429: doubles the inter-request delay (up to max)
    - On success after delay: gradually reduces delay by 5% per success
    - Decay factor ensures slow recovery, preventing burst after a single success
    """

    def __init__(
        self,
        initial_delay: float = 0.0,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0,
        recovery_factor: float = 0.95,
    ):
        self._delay = initial_delay
        self._max_delay = max_delay
        self._backoff_factor = backoff_factor
        self._recovery_factor = recovery_factor
        self._429_count = 0

    def on_rate_limited(self) -> None:
        """Called when a 429 response is received — increase delay."""
        self._429_count += 1
        old_delay = self._delay
        self._delay = min(self._delay * self._backoff_factor if self._delay > 0 else 1.0, self._max_delay)
        logger.warning(
            f"Rate limiter: 429 received ({self._429_count} total), "
            f"delay {old_delay:.1f}s → {self._delay:.1f}s"
        )

    def on_success(self) -> None:
        """Called on successful response — gradually reduce delay."""
        if self._delay > 0:
            self._delay *= self._recovery_factor
            # Floor: below 0.01s is effectively zero
            if self._delay < 0.01:
                self._delay = 0.0
                logger.info("Rate limiter: recovered, delay removed")

    @property
    def current_delay(self) -> float:
        return self._delay

    def get_state(self) -> Dict[str, Any]:
        return {
            "current_delay": round(self._delay, 2),
            "max_delay": self._max_delay,
            "429_count": self._429_count,
        }


# Custom exceptions
class RateLimitError(Exception):
    """Rate limit exception"""

    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class ServerError(requests.exceptions.RequestException):
    """Server error (5xx), retryable"""

    pass


class CircuitBreakerError(Exception):
    """Circuit breaker exception"""

    pass


class ResilientHTTPClient:
    """
    Resilient HTTP client

    Provides:
    - Exponential backoff retry
    - Timeout handling
    - 429 rate limit handling
    - Circuit breaker pattern

    Attributes:
        timeout: Request timeout (seconds)
        max_retries: Maximum retry count
        max_wait: Maximum wait time (seconds)
        circuit_breaker_threshold: Circuit breaker failure threshold
        circuit_breaker_timeout: Circuit breaker timeout (seconds)
    """

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 5,
        max_wait: int = 60,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: int = 60,
    ):
        """
        Initialize resilient HTTP client

        Args:
            timeout: Request timeout
            max_retries: Maximum retry count
            max_wait: Maximum wait time (between two retries)
            circuit_breaker_threshold: Circuit breaker failure threshold
            circuit_breaker_timeout: Circuit breaker timeout
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_wait = max_wait
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout

        # Circuit breaker state
        self._failure_count = 0
        self._circuit_open = False
        self._circuit_open_time: Optional[float] = None
        self._half_open: bool = False  # P2: True during half-open probe
        self._half_open_allowed: bool = False  # P2: One probe allowed

        # Adaptive rate limiter
        self._rate_limiter = _AdaptiveRateLimiter()

        # Session
        self._session = requests.Session()

    def _check_circuit_breaker(self) -> None:
        """Check circuit breaker status with half-open support.

        States:
        - closed: normal operation, requests allowed
        - open: requests blocked (circuit tripped after failures)
        - half-open: timeout elapsed, one probe request allowed
        """
        if self._circuit_open:
            if self._circuit_open_time is None:
                # No timestamp — assume recovered
                self._close_circuit()
            elif time.time() - self._circuit_open_time > self.circuit_breaker_timeout:
                # Timeout elapsed — transition to half-open (allow one probe)
                if not self._half_open_allowed:
                    self._half_open = True
                    self._half_open_allowed = True
                    logger.info(
                        "Circuit breaker entering half-open state — allowing probe request"
                    )
                # Allow the probe request through
                return
            else:
                raise CircuitBreakerError(
                    "Circuit breaker is open, requests are blocked"
                )

    def _close_circuit(self) -> None:
        """Close the circuit breaker (reset state)."""
        self._circuit_open = False
        self._failure_count = 0
        self._half_open = False
        self._half_open_allowed = False
        logger.info("Circuit breaker recovered")

    def _record_success(self) -> None:
        """Record success. In half-open state, closes the circuit."""
        self._failure_count = 0
        if self._half_open:
            # Probe request succeeded — close the circuit
            self._close_circuit()
            logger.info("Half-open probe succeeded, circuit closed")
        else:
            self._circuit_open = False
        # Adaptive rate limiter — gradually reduce delay on success
        self._rate_limiter.on_success()

    def _record_failure(self) -> None:
        """Record failure. In half-open state, re-opens the circuit."""
        self._failure_count += 1
        if self._half_open:
            # Probe request failed — re-open the circuit
            self._half_open = False
            self._half_open_allowed = False
            self._circuit_open = True
            self._circuit_open_time = time.time()
            logger.warning("Half-open probe failed, circuit re-opened")
        elif self._failure_count >= self.circuit_breaker_threshold:
            self._circuit_open = True
            self._circuit_open_time = time.time()
            logger.warning(
                f"Circuit breaker opened after {self._failure_count} failures"
            )

    def _handle_rate_limit(self, response: requests.Response) -> None:
        """Handle 429 rate limit"""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                retry_after_sec = int(retry_after)
            except ValueError:
                retry_after_sec = 60  # Default wait 60 seconds
        else:
            retry_after_sec = 60

        raise RateLimitError(
            f"Rate limit exceeded. Retry after {retry_after_sec} seconds",
            retry_after=retry_after_sec,
        )

    def _record_rate_limited(self) -> None:
        """Called when a 429 is detected — notify adaptive rate limiter."""
        self._rate_limiter.on_rate_limited()

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type(
            (requests.exceptions.Timeout, requests.exceptions.ConnectionError, RateLimitError, ServerError)
        ),
        reraise=True,
    )
    def request(  # noqa: C901
        self,
        method: str,
        url: str,
        timeout: Optional[int] = None,
        handle_rate_limit: bool = True,
        **kwargs,
    ) -> requests.Response:
        """
        Send HTTP request (with retry logic)

        Args:
            method: HTTP method
            url: Request URL
            timeout: Timeout (seconds)
            handle_rate_limit: Whether to handle 429 rate limiting
            **kwargs: Other parameters passed to requests

        Returns:
            requests.Response

        Raises:
            CircuitBreakerError: Circuit breaker is open
            RateLimitError: Rate limit exceeded
            requests.exceptions.RequestException: Other request exceptions
        """
        # Check circuit breaker
        self._check_circuit_breaker()

        # Adaptive rate limiter — wait if needed to avoid burst
        if self._rate_limiter.current_delay > 0:
            time.sleep(self._rate_limiter.current_delay)

        try:
            response = self._session.request(
                method,
                url,
                timeout=timeout or self.timeout,
                **kwargs,
            )

            # Handle 429 rate limit
            if response.status_code == 429 and handle_rate_limit:
                self._record_rate_limited()
                self._handle_rate_limit(response)

            # Handle other error status codes
            if response.status_code >= 400:
                if response.status_code >= 500:
                    # Server error, retryable
                    raise ServerError(
                        f"Server error: {response.status_code}"
                    )
                elif response.status_code == 401:
                    raise requests.exceptions.RequestException(
                        "Unauthorized: Invalid or expired credentials"
                    )
                elif response.status_code == 403:
                    raise requests.exceptions.RequestException(
                        "Forbidden: Access denied"
                    )
                elif response.status_code == 404:
                    raise requests.exceptions.RequestException(
                        f"Not Found: {url}"
                    )

            # Record success
            self._record_success()
            return response

        except RetryError:
            # All retries failed
            self._record_failure()
            logger.error(f"Request failed after all retries: {url}")
            raise
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, RateLimitError):
            # These exceptions are caught and retried by tenacity
            raise
        except requests.exceptions.RequestException:
            # Other exceptions — record failure for server errors only
            try:
                if response.status_code >= 500:  # type: ignore[possibly-undefined]
                    self._record_failure()
            except NameError:
                # response not defined (e.g., connection error before response received)
                self._record_failure()
            raise

    def get(self, url: str, **kwargs) -> requests.Response:
        """Send GET request"""
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        """Send POST request"""
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs) -> requests.Response:
        """Send PUT request"""
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs) -> requests.Response:
        """Send DELETE request"""
        return self.request("DELETE", url, **kwargs)

    async def request_async(
        self,
        method: str,
        url: str,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> requests.Response:
        """
        Send HTTP request asynchronously

        Args:
            method: HTTP method
            url: Request URL
            timeout: Timeout
            **kwargs: Other parameters

        Returns:
            requests.Response
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.request(method, url, timeout=timeout, **kwargs),
        )

    def get_rate_limiter_state(self) -> Dict[str, Any]:
        """Get adaptive rate limiter state."""
        return self._rate_limiter.get_state()

    def close(self) -> None:
        """Close client"""
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Convenience function: create retry-decorated function
def with_retry(
    max_retries: int = 5,
    multiplier: float = 1,
    min_wait: float = 2,
    max_wait: float = 60,
):
    """
    Retry decorator

    Usage example:
        @with_retry(max_retries=3)
        def my_function():
            pass
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        @retry(
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=multiplier, min=min_wait, max=max_wait),
            retry=retry_if_exception_type(
                (requests.exceptions.Timeout, requests.exceptions.ConnectionError)
            ),
            reraise=True,
        )
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator
