"""Tests for convert.py — CLI entry point."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from convert import main
from src.processor import ProcessingResult


@pytest.fixture
def runner():
    return CliRunner()


class TestCLISingleImage:
    """Tests for single-image CLI mode."""

    @patch("convert.process_image")
    def test_single_image_success(self, mock_process, runner, tmp_image):
        mock_process.return_value = ProcessingResult(
            tmp_image, tmp_image.parent / "test-image.md", success=True
        )
        result = runner.invoke(main, [str(tmp_image)])
        assert result.exit_code == 0
        assert "Created:" in result.output

    @patch("convert.process_image")
    def test_single_image_failure(self, mock_process, runner, tmp_image):
        mock_process.return_value = ProcessingResult(
            tmp_image, success=False, error="API error"
        )
        result = runner.invoke(main, [str(tmp_image)])
        assert result.exit_code == 1
        assert "Failed" in result.output

    @patch("convert.process_image")
    def test_dry_run_message(self, mock_process, runner, tmp_image):
        mock_process.return_value = ProcessingResult(
            tmp_image, tmp_image.parent / "test-image.md", success=True
        )
        result = runner.invoke(main, [str(tmp_image), "--dry-run"])
        assert result.exit_code == 0
        assert "DRY RUN" in result.output

    @patch("convert.process_image")
    def test_passes_output_name(self, mock_process, runner, tmp_image):
        mock_process.return_value = ProcessingResult(
            tmp_image, tmp_image.parent / "custom.md", success=True
        )
        runner.invoke(main, [str(tmp_image), "-o", "custom"])
        assert mock_process.call_args.kwargs["output_name"] == "custom"

    @patch("convert.process_image")
    def test_passes_model_option(self, mock_process, runner, tmp_image):
        mock_process.return_value = ProcessingResult(
            tmp_image, tmp_image.parent / "out.md", success=True
        )
        runner.invoke(main, [str(tmp_image), "--model", "claude-opus-4-20250514"])
        assert mock_process.call_args.kwargs["model"] == "claude-opus-4-20250514"

    @patch("convert.process_image")
    def test_no_frontmatter_flag(self, mock_process, runner, tmp_image):
        mock_process.return_value = ProcessingResult(
            tmp_image, tmp_image.parent / "out.md", success=True
        )
        runner.invoke(main, [str(tmp_image), "--no-frontmatter"])
        assert mock_process.call_args.kwargs["include_frontmatter"] is False

    def test_nonexistent_path_errors(self, runner):
        result = runner.invoke(main, ["/nonexistent/path/img.png"])
        assert result.exit_code != 0


class TestCLIBatchMode:
    """Tests for batch/folder CLI mode."""

    @patch("convert.process_batch")
    def test_batch_success(self, mock_batch, runner, tmp_image_dir):
        mock_batch.return_value = [
            ProcessingResult(Path("a.png"), Path("a.md"), success=True),
            ProcessingResult(Path("b.png"), Path("b.md"), success=True),
        ]
        result = runner.invoke(main, [str(tmp_image_dir)])
        assert result.exit_code == 0
        assert "2 converted" in result.output
        assert "0 failed" in result.output

    @patch("convert.process_batch")
    def test_batch_with_failures(self, mock_batch, runner, tmp_image_dir):
        mock_batch.return_value = [
            ProcessingResult(Path("a.png"), Path("a.md"), success=True),
            ProcessingResult(
                Path("b.png"), success=False, error="timeout"
            ),
        ]
        result = runner.invoke(main, [str(tmp_image_dir)])
        assert result.exit_code == 1
        assert "1 converted" in result.output
        assert "1 failed" in result.output
        assert "timeout" in result.output

    @patch("convert.process_batch")
    def test_batch_no_images_found(self, mock_batch, runner, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        mock_batch.return_value = []
        result = runner.invoke(main, [str(empty)])
        assert result.exit_code == 0
        assert "No supported images" in result.output

    @patch("convert.process_batch")
    def test_passes_recursive_flag(self, mock_batch, runner, tmp_image_dir):
        mock_batch.return_value = []
        runner.invoke(main, [str(tmp_image_dir), "--recursive"])
        assert mock_batch.call_args.kwargs["recursive"] is True

    @patch("convert.process_batch")
    def test_passes_concurrency(self, mock_batch, runner, tmp_image_dir):
        mock_batch.return_value = []
        runner.invoke(main, [str(tmp_image_dir), "--concurrency", "5"])
        assert mock_batch.call_args.kwargs["concurrency"] == 5

    @patch("convert.process_batch")
    def test_passes_skip_existing(self, mock_batch, runner, tmp_image_dir):
        mock_batch.return_value = []
        runner.invoke(main, [str(tmp_image_dir), "--skip-existing"])
        assert mock_batch.call_args.kwargs["skip_existing"] is True
