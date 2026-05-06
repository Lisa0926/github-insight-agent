# -*- coding: utf-8 -*-
"""Tests for LLM decision cache (llm_cache.py)."""

import json
import tempfile
from pathlib import Path

from src.core.llm_cache import LLMCache, _cache_key, get_llm_cache, reset_llm_cache


class TestCacheKey:
    """Test cache key generation."""

    def test_same_input_same_key(self):
        key1 = _cache_key("react framework", ["react", "vue"])
        key2 = _cache_key("react framework", ["vue", "react"])
        assert key1 == key2

    def test_different_query_different_key(self):
        key1 = _cache_key("react", ["react"])
        key2 = _cache_key("vue", ["react"])
        assert key1 != key2

    def test_order_independent(self):
        key1 = _cache_key("test", ["a", "b", "c"])
        key2 = _cache_key("test", ["c", "b", "a"])
        assert key1 == key2


class TestLLMCache:
    """Test LLMCache class."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        self.tmp.close()
        self.cache = LLMCache(ttl=10, cache_file=Path(self.tmp.name))
        reset_llm_cache()

    def teardown_method(self):
        import os
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass
        reset_llm_cache()

    def test_put_and_get(self):
        self.cache.put("query1", ["proj1"], {"strategy": "deep", "confidence": 0.9})
        result = self.cache.get("query1", ["proj1"])
        assert result == {"strategy": "deep", "confidence": 0.9}

    def test_get_missing_query(self):
        result = self.cache.get("nonexistent", ["proj1"])
        assert result is None

    def test_get_wrong_project(self):
        self.cache.put("query1", ["proj1"], {"data": "test"})
        result = self.cache.get("query1", ["proj2"])
        assert result is None

    def test_expired_entry(self):
        expired_cache = LLMCache(ttl=0, cache_file=Path(self.tmp.name))
        expired_cache.put("q", ["p"], {"val": 1})
        result = expired_cache.get("q", ["p"])
        assert result is None

    def test_clear_expired(self):
        short_cache = LLMCache(ttl=0, cache_file=Path(self.tmp.name))
        short_cache.put("q1", ["p"], {"v": 1})
        short_cache.put("q2", ["p"], {"v": 2})
        removed = short_cache.clear_expired()
        assert removed == 2
        assert short_cache.get("q1", ["p"]) is None

    def test_clear_expired_keeps_valid(self):
        self.cache.put("q1", ["p"], {"v": 1})
        self.cache.put("q2", ["p"], {"v": 2})
        removed = self.cache.clear_expired()
        assert removed == 0
        assert self.cache.get("q1", ["p"]) == {"v": 1}

    def test_get_after_ttl_expiry(self):
        short_cache = LLMCache(ttl=1, cache_file=Path(self.tmp.name))
        short_cache.put("q", ["p"], {"v": 1})
        # Simulate expiry by writing with old timestamp
        lines = []
        with open(self.tmp.name, "r") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    entry["timestamp"] = entry["timestamp"] - 10  # age it
                    lines.append(json.dumps(entry))
        with open(self.tmp.name, "w") as f:
            f.write("\n".join(lines) + "\n")
        assert short_cache.get("q", ["p"]) is None


class TestSingleton:
    """Test singleton functions."""

    def setup_method(self):
        reset_llm_cache()

    def teardown_method(self):
        reset_llm_cache()

    def test_get_llm_cache_returns_instance(self):
        cache = get_llm_cache()
        assert isinstance(cache, LLMCache)

    def test_get_llm_cache_same_instance(self):
        c1 = get_llm_cache()
        c2 = get_llm_cache()
        assert c1 is c2

    def test_reset_clears_singleton(self):
        c1 = get_llm_cache()
        reset_llm_cache()
        c2 = get_llm_cache()
        assert c1 is not c2
