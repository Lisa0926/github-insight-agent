# -*- coding: utf-8 -*-
"""Tests for Studio integration and helper modules (coverage gaps)."""

from unittest.mock import patch, MagicMock


class TestStudioIntegration:
    """Test src/core/studio_integration.py"""

    def test_push_to_studio_no_crash(self):
        """push_to_studio should not crash even if Studio is not configured."""
        from src.core.studio_integration import push_to_studio
        # Should not raise — Studio is not configured
        push_to_studio("test_sender", "test content", "assistant")

    def test_push_to_studio_with_user_role(self):
        from src.core.studio_integration import push_to_studio
        push_to_studio("user", "hello", "user")

    def test_flush_traces_no_opentelemetry(self):
        """flush_traces should handle missing opentelemetry gracefully."""
        from src.core.studio_integration import flush_traces
        # Should not raise even without opentelemetry
        flush_traces()

    def test_push_to_studio_with_helper(self):
        """push_to_studio should forward via StudioHelper when configured."""
        from src.core import studio_helper
        original = studio_helper._studio_helper
        try:
            mock_helper = MagicMock()
            studio_helper._studio_helper = mock_helper
            from src.core.studio_integration import push_to_studio
            push_to_studio("agent", "content", "assistant")
            mock_helper.forward_message.assert_called_once_with(
                name="agent", content="content", role="assistant"
            )
        finally:
            studio_helper._studio_helper = original


class TestStudioHelper:
    """Test src/core/studio_helper.py"""

    def test_studio_helper_init(self):
        from src.core.studio_helper import StudioHelper
        helper = StudioHelper(studio_url="http://test.com", run_id="run-123")
        assert helper.studio_url == "http://test.com"
        assert helper.run_id == "run-123"

    def test_studio_helper_register_no_url(self):
        """register_run should return False when no URL configured."""
        from src.core.studio_helper import StudioHelper
        helper = StudioHelper()
        assert helper.register_run() is False

    def test_studio_helper_forward_no_url(self):
        """forward_message should return False when no URL configured."""
        from src.core.studio_helper import StudioHelper
        helper = StudioHelper()
        assert helper.forward_message("test", "content", "assistant") is False

    def test_studio_helper_register_success(self):
        """register_run should return True when studio is configured."""
        from src.core.studio_helper import StudioHelper
        helper = StudioHelper(studio_url="http://test.com", run_id="run-123")
        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock()
            result = helper.register_run()
            assert result is True
            mock_post.assert_called_once()

    def test_studio_helper_register_failure(self):
        """register_run should return False on request failure."""
        from src.core.studio_helper import StudioHelper
        helper = StudioHelper(studio_url="http://test.com", run_id="run-123")
        with patch("requests.post", side_effect=ConnectionError("no")):
            result = helper.register_run()
            assert result is False

    def test_studio_helper_forward_success(self):
        """forward_message should return True when studio is configured."""
        from src.core.studio_helper import StudioHelper
        helper = StudioHelper(studio_url="http://test.com", run_id="run-123")
        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock()
            result = helper.forward_message("agent", "content", "assistant")
            assert result is True
            mock_post.assert_called_once()

    def test_studio_helper_forward_failure(self):
        """forward_message should return False on request failure."""
        from src.core.studio_helper import StudioHelper
        helper = StudioHelper(studio_url="http://test.com", run_id="run-123")
        with patch("requests.post", side_effect=ConnectionError("no")):
            result = helper.forward_message("agent", "content", "assistant")
            assert result is False

    def test_set_global_studio_config(self):
        """Test set_global_studio_config creates helper."""
        from src.core.studio_helper import (
            set_global_studio_config,
        )
        with patch("src.core.studio_helper.StudioHelper") as mock_helper_cls:
            mock_helper = MagicMock()
            mock_helper_cls.return_value = mock_helper
            set_global_studio_config("http://studio.test", "run-456")
            mock_helper_cls.assert_called_once_with("http://studio.test", "run-456")

    def test_forward_to_studio_no_helper(self):
        """forward_to_studio should do nothing when no helper is set."""
        from src.core.studio_helper import forward_to_studio
        # Should not raise
        forward_to_studio("test", "content", "assistant")

    def test_get_studio_helper_none(self):
        """get_studio_helper should return None if not configured."""
        from src.core import studio_helper
        original = studio_helper._studio_helper
        studio_helper._studio_helper = None
        try:
            assert studio_helper.get_studio_helper() is None
        finally:
            studio_helper._studio_helper = original


class TestStudioIntegrationGlobalReset:
    """Reset global state after studio tests."""

    def teardown_method(self):
        from src.core import studio_helper
        studio_helper._studio_helper = None
        studio_helper._studio_url = None
        studio_helper._run_id = None
