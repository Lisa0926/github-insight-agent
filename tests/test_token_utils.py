# -*- coding: utf-8 -*-
"""Tests for token counting utilities (token_utils.py)."""

from src.core.token_utils import count_tokens, truncate_to_tokens, estimate_messages_tokens


class TestCountTokens:
    """Test count_tokens function."""

    def test_empty_string(self):
        assert count_tokens("") == 0

    def test_none(self):
        assert count_tokens(None) == 0

    def test_simple_text(self):
        n = count_tokens("Hello world")
        assert n > 0

    def test_chinese_text(self):
        n = count_tokens("你好世界")
        assert n > 0

    def test_long_text_more_tokens(self):
        short = count_tokens("Hello")
        long = count_tokens("Hello " * 100)
        assert long > short

    def test_consistent_repeated_call(self):
        text = "tiktoken should produce consistent results"
        assert count_tokens(text) == count_tokens(text)


class TestTruncateToTokens:
    """Test truncate_to_tokens function."""

    def test_empty_string(self):
        assert truncate_to_tokens("", 10) == ""

    def test_none(self):
        assert truncate_to_tokens(None, 10) == ""

    def test_zero_max(self):
        assert truncate_to_tokens("hello", 0) == ""

    def test_negative_max(self):
        assert truncate_to_tokens("hello", -5) == ""

    def test_no_truncation_needed(self):
        text = "short"
        result = truncate_to_tokens(text, 100)
        assert result == text

    def test_actually_truncates(self):
        long_text = "the quick brown fox jumps over the lazy dog " * 20
        result = truncate_to_tokens(long_text, 10)
        assert len(result) < len(long_text)
        # Verify result fits within budget
        from src.core.token_utils import _get_encoding
        enc = _get_encoding()
        assert len(enc.encode(result)) <= 10

    def test_truncated_content_is_prefix(self):
        text = "abcdefghij" * 10
        result = truncate_to_tokens(text, 5)
        assert text.startswith(result)


class TestEstimateMessagesTokens:
    """Test estimate_messages_tokens function."""

    def test_empty_messages(self):
        assert estimate_messages_tokens([]) == 0

    def test_single_message(self):
        messages = [{"role": "user", "content": "Hello"}]
        total = estimate_messages_tokens(messages)
        assert total > 0

    def test_multiple_messages(self):
        messages = [
            {"role": "system", "content": "You are a helper."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        total = estimate_messages_tokens(messages)
        assert total > 0

    def test_messages_more_than_single(self):
        single = estimate_messages_tokens([{"role": "user", "content": "hi"}])
        multi = estimate_messages_tokens([
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ])
        assert multi > single
