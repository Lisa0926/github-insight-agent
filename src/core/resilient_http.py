# -*- coding: utf-8 -*-
"""
弹性 HTTP 客户端

提供:
- 指数退避重试
- 超时处理
- 429 限流优雅降级
- 熔断器模式

基于 tenacity 库实现可靠的重试逻辑。
"""

import asyncio
import time
from typing import Optional, Callable
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


# 自定义异常
class RateLimitError(Exception):
    """速率限制异常"""

    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class ServerError(requests.exceptions.RequestException):
    """服务器错误 (5xx)，可重试"""

    pass


class CircuitBreakerError(Exception):
    """熔断器异常"""

    pass


class ResilientHTTPClient:
    """
    弹性 HTTP 客户端

    提供:
    - 指数退避重试
    - 超时处理
    - 429 限流处理
    - 熔断器模式

    Attributes:
        timeout: 请求超时时间 (秒)
        max_retries: 最大重试次数
        max_wait: 最大等待时间 (秒)
        circuit_breaker_threshold: 熔断器失败阈值
        circuit_breaker_timeout: 熔断器超时时间 (秒)
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
        初始化弹性 HTTP 客户端

        Args:
            timeout: 请求超时时间
            max_retries: 最大重试次数
            max_wait: 最大等待时间 (两次重试之间)
            circuit_breaker_threshold: 熔断器失败阈值
            circuit_breaker_timeout: 熔断器超时时间
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_wait = max_wait
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout

        # 熔断器状态
        self._failure_count = 0
        self._circuit_open = False
        self._circuit_open_time: Optional[float] = None

        # Session
        self._session = requests.Session()

    def _check_circuit_breaker(self) -> None:
        """检查熔断器状态"""
        if self._circuit_open:
            if self._circuit_open_time is None:
                self._circuit_open = False
                self._failure_count = 0
            elif time.time() - self._circuit_open_time > self.circuit_breaker_timeout:
                # 熔断器超时，尝试恢复
                self._circuit_open = False
                self._failure_count = 0
                logger.info("Circuit breaker recovered")
            else:
                raise CircuitBreakerError(
                    "Circuit breaker is open, requests are blocked"
                )

    def _record_success(self) -> None:
        """记录成功"""
        self._failure_count = 0
        self._circuit_open = False

    def _record_failure(self) -> None:
        """记录失败"""
        self._failure_count += 1
        if self._failure_count >= self.circuit_breaker_threshold:
            self._circuit_open = True
            self._circuit_open_time = time.time()
            logger.warning(
                f"Circuit breaker opened after {self._failure_count} failures"
            )

    def _handle_rate_limit(self, response: requests.Response) -> None:
        """处理 429 速率限制"""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                retry_after_sec = int(retry_after)
            except ValueError:
                retry_after_sec = 60  # 默认等待 60 秒
        else:
            retry_after_sec = 60

        raise RateLimitError(
            f"Rate limit exceeded. Retry after {retry_after_sec} seconds",
            retry_after=retry_after_sec,
        )

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
        发送 HTTP 请求（带重试逻辑）

        Args:
            method: HTTP 方法
            url: 请求 URL
            timeout: 超时时间（秒）
            handle_rate_limit: 是否处理 429 限流
            **kwargs: 传递给 requests 的其他参数

        Returns:
            requests.Response 响应

        Raises:
            CircuitBreakerError: 熔断器打开
            RateLimitError: 速率限制
            requests.exceptions.RequestException: 其他请求异常
        """
        # 检查熔断器
        self._check_circuit_breaker()

        try:
            response = self._session.request(
                method,
                url,
                timeout=timeout or self.timeout,
                **kwargs,
            )

            # 处理 429 速率限制
            if response.status_code == 429 and handle_rate_limit:
                self._handle_rate_limit(response)

            # 处理其他错误状态码
            if response.status_code >= 400:
                if response.status_code >= 500:
                    # 服务器错误，可重试
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

            # 记录成功
            self._record_success()
            return response

        except RetryError:
            # 所有重试失败
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
        """发送 GET 请求"""
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        """发送 POST 请求"""
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs) -> requests.Response:
        """发送 PUT 请求"""
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs) -> requests.Response:
        """发送 DELETE 请求"""
        return self.request("DELETE", url, **kwargs)

    async def request_async(
        self,
        method: str,
        url: str,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> requests.Response:
        """
        异步发送 HTTP 请求

        Args:
            method: HTTP 方法
            url: 请求 URL
            timeout: 超时时间
            **kwargs: 其他参数

        Returns:
            requests.Response 响应
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.request(method, url, timeout=timeout, **kwargs),
        )

    def close(self) -> None:
        """关闭客户端"""
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# 便捷函数：创建带装饰器的重试函数
def with_retry(
    max_retries: int = 5,
    multiplier: float = 1,
    min_wait: float = 2,
    max_wait: float = 60,
):
    """
    重试装饰器

    使用示例:
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
