"""Tests for src/extractor.py — image extraction via Claude Vision API."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import anthropic

from src.extractor import extract_from_image, MAX_RETRIES


class TestExtractFromImage:
    """Tests for extract_from_image()."""

    def test_file_not_found_raises(self, tmp_path):
        fake = tmp_path / "nonexistent.png"
        with pytest.raises(FileNotFoundError):
            extract_from_image(fake)

    def test_unsupported_format_raises(self, tmp_unsupported):
        with pytest.raises(ValueError, match="Unsupported image format"):
            extract_from_image(tmp_unsupported)

    @patch("src.extractor.anthropic.Anthropic")
    def test_successful_extraction(self, mock_cls, tmp_image):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="TITLE: Test\nSome extracted text")]
        mock_client.messages.create.return_value = mock_msg

        result = extract_from_image(tmp_image)

        assert "TITLE: Test" in result
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["messages"][0]["content"][0]["type"] == "image"

    @patch("src.extractor.anthropic.Anthropic")
    def test_uses_custom_model(self, mock_cls, tmp_image):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="extracted")]
        mock_client.messages.create.return_value = mock_msg

        extract_from_image(tmp_image, model="claude-opus-4-20250514")

        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == "claude-opus-4-20250514"

    @patch("src.extractor.anthropic.Anthropic")
    def test_empty_extraction_raises(self, mock_cls, tmp_image):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="")]
        mock_client.messages.create.return_value = mock_msg

        with pytest.raises((ValueError, RuntimeError)):
            extract_from_image(tmp_image)

    @patch("src.extractor.time.sleep")
    @patch("src.extractor.anthropic.Anthropic")
    def test_retries_on_rate_limit(self, mock_cls, mock_sleep, tmp_image):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        rate_limit_resp = MagicMock()
        rate_limit_resp.status_code = 429
        rate_limit_error = anthropic.RateLimitError(
            message="rate limited",
            response=rate_limit_resp,
            body=None,
        )

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="extracted after retry")]
        mock_client.messages.create.side_effect = [
            rate_limit_error,
            mock_msg,
        ]

        result = extract_from_image(tmp_image)
        assert result == "extracted after retry"
        assert mock_client.messages.create.call_count == 2
        mock_sleep.assert_called_once()

    @patch("src.extractor.time.sleep")
    @patch("src.extractor.anthropic.Anthropic")
    def test_raises_after_max_retries_rate_limit(self, mock_cls, mock_sleep, tmp_image):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        rate_limit_resp = MagicMock()
        rate_limit_resp.status_code = 429
        rate_limit_error = anthropic.RateLimitError(
            message="rate limited",
            response=rate_limit_resp,
            body=None,
        )
        mock_client.messages.create.side_effect = rate_limit_error

        with pytest.raises(RuntimeError, match=f"failed after {MAX_RETRIES}"):
            extract_from_image(tmp_image)

    @patch("src.extractor.anthropic.Anthropic")
    def test_reads_correct_media_type_for_jpg(self, mock_cls, tmp_jpg):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="extracted")]
        mock_client.messages.create.return_value = mock_msg

        extract_from_image(tmp_jpg)

        call_kwargs = mock_client.messages.create.call_args
        image_block = call_kwargs.kwargs["messages"][0]["content"][0]
        assert image_block["source"]["media_type"] == "image/jpeg"
