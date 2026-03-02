"""Tests for src/processor.py — single-image pipeline orchestration."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.processor import process_image, ProcessingResult


class TestProcessingResult:
    """Tests for the ProcessingResult data class."""

    def test_success_result(self):
        r = ProcessingResult(Path("img.png"), Path("out.md"), success=True)
        assert r.success is True
        assert r.error is None
        assert "OK" in repr(r)

    def test_failure_result(self):
        r = ProcessingResult(Path("img.png"), success=False, error="bad format")
        assert r.success is False
        assert r.error == "bad format"
        assert "FAIL" in repr(r)


class TestProcessImage:
    """Tests for process_image()."""

    def test_nonexistent_file_returns_failure(self, tmp_path):
        fake = tmp_path / "nope.png"
        result = process_image(fake)
        assert result.success is False
        assert "not found" in result.error.lower()

    def test_unsupported_format_returns_failure(self, tmp_unsupported):
        result = process_image(tmp_unsupported)
        assert result.success is False
        assert "Unsupported format" in result.error

    def test_dry_run_returns_success_without_api_call(self, tmp_image, tmp_path):
        result = process_image(tmp_image, output_dir=tmp_path, dry_run=True)
        assert result.success is True
        assert result.output_path is not None
        # No file should be written in dry run
        assert not result.output_path.exists()

    def test_dry_run_output_path_is_md(self, tmp_image, tmp_path):
        result = process_image(tmp_image, output_dir=tmp_path, dry_run=True)
        assert str(result.output_path).endswith(".md")

    @patch("src.processor.structure_extraction")
    @patch("src.processor.extract_from_image")
    def test_successful_pipeline_writes_file(
        self, mock_extract, mock_structure, tmp_image, tmp_path
    ):
        mock_extract.return_value = "TITLE: Test\nExtracted content"
        mock_structure.return_value = "# Test\n\nStructured content"

        result = process_image(tmp_image, output_dir=tmp_path)

        assert result.success is True
        assert result.output_path.exists()
        content = result.output_path.read_text()
        assert "# Test" in content

    @patch("src.processor.structure_extraction")
    @patch("src.processor.extract_from_image")
    def test_creates_output_dir_if_missing(
        self, mock_extract, mock_structure, tmp_image, tmp_path
    ):
        mock_extract.return_value = "TITLE: Test\nContent"
        mock_structure.return_value = "# Test"

        out_dir = tmp_path / "nested" / "output"
        result = process_image(tmp_image, output_dir=out_dir)

        assert result.success is True
        assert out_dir.exists()

    @patch("src.processor.structure_extraction")
    @patch("src.processor.extract_from_image")
    def test_custom_output_name(
        self, mock_extract, mock_structure, tmp_image, tmp_path
    ):
        mock_extract.return_value = "TITLE: Test\nContent"
        mock_structure.return_value = "# Test"

        result = process_image(
            tmp_image, output_dir=tmp_path, output_name="my-doc"
        )
        assert result.output_path.name == "my-doc.md"

    @patch("src.processor.extract_from_image")
    def test_empty_extraction_returns_failure(self, mock_extract, tmp_image, tmp_path):
        mock_extract.return_value = "   "

        result = process_image(tmp_image, output_dir=tmp_path)
        assert result.success is False
        assert "empty" in result.error.lower()

    @patch("src.processor.extract_from_image")
    def test_api_exception_returns_failure(self, mock_extract, tmp_image, tmp_path):
        mock_extract.side_effect = RuntimeError("API down")

        result = process_image(tmp_image, output_dir=tmp_path)
        assert result.success is False
        assert "API down" in result.error

    @patch("src.processor.structure_extraction")
    @patch("src.processor.extract_from_image")
    def test_passes_model_through(
        self, mock_extract, mock_structure, tmp_image, tmp_path
    ):
        mock_extract.return_value = "TITLE: Test\nContent"
        mock_structure.return_value = "# Test"

        process_image(tmp_image, output_dir=tmp_path, model="claude-opus-4-20250514")

        mock_extract.assert_called_once()
        assert mock_extract.call_args.kwargs["model"] == "claude-opus-4-20250514"
        assert mock_structure.call_args.kwargs["model"] == "claude-opus-4-20250514"

    @patch("src.processor.structure_extraction")
    @patch("src.processor.extract_from_image")
    def test_passes_frontmatter_flag(
        self, mock_extract, mock_structure, tmp_image, tmp_path
    ):
        mock_extract.return_value = "TITLE: Test\nContent"
        mock_structure.return_value = "# Test"

        process_image(
            tmp_image, output_dir=tmp_path, include_frontmatter=False
        )
        assert mock_structure.call_args.kwargs["include_frontmatter"] is False
