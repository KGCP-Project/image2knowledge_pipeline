"""Tests for src/structurer.py — raw extraction to structured markdown."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date

from src.structurer import structure_extraction, _build_frontmatter, _extract_field


class TestExtractField:
    """Tests for _extract_field() metadata parser."""

    def test_extracts_title(self):
        text = "TITLE: My Framework\nOther stuff"
        assert _extract_field(text, "TITLE") == "My Framework"

    def test_extracts_author_source(self):
        text = "AUTHOR/SOURCE: Jane Doe, Acme Corp"
        assert _extract_field(text, "AUTHOR/SOURCE") == "Jane Doe, Acme Corp"

    def test_extracts_content_type(self):
        text = "CONTENT TYPE: framework"
        assert _extract_field(text, "CONTENT TYPE") == "framework"

    def test_returns_empty_for_missing_field(self):
        text = "TITLE: Something\nNo author here"
        assert _extract_field(text, "AUTHOR") == ""

    def test_strips_quotes_from_value(self):
        text = 'TITLE: "Quoted Title"'
        assert _extract_field(text, "TITLE") == "Quoted Title"

    def test_handles_heading_prefix(self):
        text = "## TITLE: Heading Style"
        assert _extract_field(text, "TITLE") == "Heading Style"

    def test_handles_numbered_prefix(self):
        text = "1. TITLE: Numbered Style"
        assert _extract_field(text, "TITLE") == "Numbered Style"


class TestBuildFrontmatter:
    """Tests for _build_frontmatter()."""

    def test_contains_yaml_delimiters(self, sample_raw_extraction):
        fm = _build_frontmatter(sample_raw_extraction, "test.png")
        lines = fm.split("\n")
        assert lines[0] == "---"
        assert lines[-1] == "---"

    def test_contains_source_file(self, sample_raw_extraction):
        fm = _build_frontmatter(sample_raw_extraction, "my-image.png")
        assert "source_file: my-image.png" in fm

    def test_contains_title(self, sample_raw_extraction):
        fm = _build_frontmatter(sample_raw_extraction, "test.png")
        assert "Test Framework Overview" in fm

    def test_contains_author(self, sample_raw_extraction):
        fm = _build_frontmatter(sample_raw_extraction, "test.png")
        assert "Test Author" in fm

    def test_contains_content_type(self, sample_raw_extraction):
        fm = _build_frontmatter(sample_raw_extraction, "test.png")
        assert "content_type: framework" in fm

    def test_contains_extracted_date(self, sample_raw_extraction):
        fm = _build_frontmatter(sample_raw_extraction, "test.png")
        assert f"extracted_date: {date.today().isoformat()}" in fm

    def test_missing_author_omits_field(self):
        text = "TITLE: No Author Here\nCONTENT TYPE: other"
        fm = _build_frontmatter(text, "test.png")
        assert "author:" not in fm


class TestStructureExtraction:
    """Tests for structure_extraction()."""

    @patch("src.structurer.anthropic.Anthropic")
    def test_returns_markdown(self, mock_cls, sample_raw_extraction):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="# Title\n\nBody text")]
        mock_client.messages.create.return_value = mock_msg

        result = structure_extraction(sample_raw_extraction, "test.png")
        assert "# Title" in result

    @patch("src.structurer.anthropic.Anthropic")
    def test_includes_frontmatter_by_default(self, mock_cls, sample_raw_extraction):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="# Title\n\nBody")]
        mock_client.messages.create.return_value = mock_msg

        result = structure_extraction(sample_raw_extraction, "test.png")
        assert result.startswith("---")

    @patch("src.structurer.anthropic.Anthropic")
    def test_excludes_frontmatter_when_disabled(self, mock_cls, sample_raw_extraction):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="# Title\n\nBody")]
        mock_client.messages.create.return_value = mock_msg

        result = structure_extraction(
            sample_raw_extraction, "test.png", include_frontmatter=False
        )
        assert not result.startswith("---")

    @patch("src.structurer.anthropic.Anthropic")
    def test_empty_result_raises(self, mock_cls, sample_raw_extraction):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="")]
        mock_client.messages.create.return_value = mock_msg

        with pytest.raises((ValueError, RuntimeError)):
            structure_extraction(sample_raw_extraction, "test.png")

    @patch("src.structurer.anthropic.Anthropic")
    def test_uses_custom_model(self, mock_cls, sample_raw_extraction):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="# Output")]
        mock_client.messages.create.return_value = mock_msg

        structure_extraction(
            sample_raw_extraction, "test.png", model="claude-opus-4-20250514"
        )
        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == "claude-opus-4-20250514"

    @patch("src.structurer.anthropic.Anthropic")
    def test_prompt_contains_extraction_text(self, mock_cls, sample_raw_extraction):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="# Output")]
        mock_client.messages.create.return_value = mock_msg

        structure_extraction(sample_raw_extraction, "test.png")
        call_kwargs = mock_client.messages.create.call_args
        prompt_text = call_kwargs.kwargs["messages"][0]["content"]
        assert "Test Framework Overview" in prompt_text
