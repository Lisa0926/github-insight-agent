# -*- coding: utf-8 -*-
"""
LLM decision cache with TTL for GIA.

Caches LLM strategy and sufficiency decisions to avoid redundant calls
when the same query + project combination is analyzed within the TTL window.

Storage: ~/.hermes/llm_cache.jsonl
TTL: 1 hour (configurable)
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from src.core.logger import get_logger

logger = get_logger(__name__)

CACHE_DIR = Path.home() / ".hermes"
CACHE_FILE = CACHE_DIR / "llm_cache.jsonl"
DEFAULT_TTL_SECONDS = 3600  # 1 hour


def _cache_key(query: str, project_names: list) -> str:
    """Generate a stable cache key from query + sorted project names."""
    projects = ",".join(sorted(project_names))
    raw = f"{query}|{projects}"
    return hashlib.md5(raw.encode()).hexdigest()


class LLMCache:
    """Simple TTL-based cache for LLM decisions, persisted to JSONL."""

    def __init__(self, ttl: int = DEFAULT_TTL_SECONDS, cache_file: Path = None):
        self.ttl = ttl
        self.cache_file = cache_file or CACHE_FILE

    def get(self, query: str, project_names: list) -> Optional[Dict[str, Any]]:
        """Look up a cached result."""
        key = _cache_key(query, project_names)
        now = time.time()

        try:
            if not self.cache_file.exists():
                return None
            with open(self.cache_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    if entry.get("key") == key:
                        if now - entry.get("timestamp", 0) < self.ttl:
                            logger.debug(f"LLMCache hit: key={key}")
                            return entry.get("value")
                        else:
                            logger.debug(f"LLMCache expired: key={key}")
                            return None
        except Exception as e:
            logger.warning(f"LLMCache read error: {e}")
        return None

    def put(self, query: str, project_names: list, value: Dict[str, Any]) -> None:
        """Store a result with current timestamp."""
        key = _cache_key(query, project_names)
        entry = {
            "key": key,
            "query": query,
            "projects": sorted(project_names),
            "value": value,
            "timestamp": time.time(),
        }
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            logger.debug(f"LLMCache stored: key={key}")
        except Exception as e:
            logger.warning(f"LLMCache write error: {e}")

    def clear_expired(self) -> int:
        """Remove expired entries. Returns number of entries removed."""
        now = time.time()
        removed = 0
        try:
            if not self.cache_file.exists():
                return 0
            lines = self.cache_file.read_text(encoding="utf-8").split("\n")
            valid = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if now - entry.get("timestamp", 0) < self.ttl:
                    valid.append(line)
                else:
                    removed += 1
            self.cache_file.write_text("\n".join(valid) + "\n", encoding="utf-8")
        except Exception as e:
            logger.warning(f"LLMCache clear_expired error: {e}")
        return removed


# ---- Module-level singleton ----

_cache: Optional[LLMCache] = None


def get_llm_cache(ttl: int = DEFAULT_TTL_SECONDS) -> LLMCache:
    """Return the global LLMCache singleton."""
    global _cache
    if _cache is None:
        _cache = LLMCache(ttl=ttl)
    return _cache


def reset_llm_cache() -> None:
    """Reset singleton (for testing)."""
    global _cache
    _cache = None
