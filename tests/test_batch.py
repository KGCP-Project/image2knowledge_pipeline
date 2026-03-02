"""Tests for src/batch.py — folder scanning and batch processing."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.batch import find_images, process_batch, _write_index
from src.processor import ProcessingResult


class TestFindImages:
    """Tests for find_images()."""

    def test_finds_supported_images(self, tmp_image_dir):
        images = find_images(tmp_image_dir)
        names = [p.name for p in images]
        assert "alpha.png" in names
        assert "beta.jpg" in names

    def test_excludes_non_image_files(self, tmp_image_dir):
        images = find_images(tmp_image_dir)
        names = [p.name for p in images]
        assert "readme.txt" not in names

    def test_non_recursive_excludes_subdir(self, tmp_image_dir):
        images = find_images(tmp_image_dir, recursive=False)
        names = [p.name for p in images]
        assert "gamma.webp" not in names

    def test_recursive_includes_subdir(self, tmp_image_dir):
        images = find_images(tmp_image_dir, recursive=True)
        names = [p.name for p in images]
        assert "gamma.webp" in names

    def test_returns_sorted_list(self, tmp_image_dir):
        images = find_images(tmp_image_dir)
        assert images == sorted(images)

    def test_empty_dir_returns_empty(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        assert find_images(empty) == []

    def test_not_a_directory_raises(self, tmp_image):
        with pytest.raises(NotADirectoryError):
            find_images(tmp_image)


class TestWriteIndex:
    """Tests for _write_index()."""

    def test_writes_index_file(self, tmp_path):
        results = [
            ProcessingResult(
                Path("img1.png"), tmp_path / "img1.md", success=True
            ),
            ProcessingResult(
                Path("img2.png"), tmp_path / "img2.md", success=True
            ),
        ]
        _write_index(results, tmp_path)

        index = tmp_path / "_index.md"
        assert index.exists()
        content = index.read_text()
        assert "Knowledge Documents Index" in content
        assert "img1" in content
        assert "img2" in content

    def test_index_includes_failed_section(self, tmp_path):
        results = [
            ProcessingResult(
                Path("ok.png"), tmp_path / "ok.md", success=True
            ),
            ProcessingResult(
                Path("bad.png"), success=False, error="API error"
            ),
        ]
        _write_index(results, tmp_path)

        content = (tmp_path / "_index.md").read_text()
        assert "Failed" in content
        assert "bad.png" in content

    def test_no_index_when_all_failed(self, tmp_path):
        results = [
            ProcessingResult(Path("bad.png"), success=False, error="error"),
        ]
        _write_index(results, tmp_path)
        assert not (tmp_path / "_index.md").exists()

    def test_index_shows_count(self, tmp_path):
        results = [
            ProcessingResult(
                Path(f"img{i}.png"), tmp_path / f"img{i}.md", success=True
            )
            for i in range(5)
        ]
        _write_index(results, tmp_path)
        content = (tmp_path / "_index.md").read_text()
        assert "5 documents" in content


class TestProcessBatch:
    """Tests for process_batch()."""

    @patch("src.batch.process_image")
    def test_dry_run_no_api_calls(self, mock_process, tmp_image_dir, tmp_path):
        mock_process.return_value = ProcessingResult(
            Path("x.png"), tmp_path / "x.md", success=True
        )
        results = process_batch(
            tmp_image_dir, output_dir=tmp_path, dry_run=True
        )
        # dry_run calls process_image with dry_run=True
        for call in mock_process.call_args_list:
            assert call.kwargs.get("dry_run") is True

    @patch("src.batch.process_image")
    def test_returns_results_for_each_image(self, mock_process, tmp_image_dir, tmp_path):
        mock_process.return_value = ProcessingResult(
            Path("x.png"), tmp_path / "x.md", success=True
        )
        results = process_batch(tmp_image_dir, output_dir=tmp_path, dry_run=True)
        # Should have results for alpha.png and beta.jpg (non-recursive)
        assert len(results) >= 2

    def test_empty_dir_returns_empty(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        results = process_batch(empty, output_dir=tmp_path)
        assert results == []

    @patch("src.batch.process_image")
    def test_skip_existing(self, mock_process, tmp_image_dir, tmp_path):
        # Pre-create output for alpha.png
        (tmp_path / "alpha.md").write_text("existing")

        mock_process.return_value = ProcessingResult(
            Path("x.png"), tmp_path / "x.md", success=True
        )
        results = process_batch(
            tmp_image_dir, output_dir=tmp_path, skip_existing=True, dry_run=True
        )
        processed_names = [
            call.args[0].name for call in mock_process.call_args_list
        ]
        assert "alpha.png" not in processed_names

    @patch("src.batch._write_index")
    @patch("src.batch.process_image")
    def test_sequential_when_concurrency_1(
        self, mock_process, mock_index, tmp_image_dir, tmp_path
    ):
        mock_process.return_value = ProcessingResult(
            Path("x.png"), tmp_path / "x.md", success=True
        )
        process_batch(
            tmp_image_dir, output_dir=tmp_path, concurrency=1
        )
        assert mock_process.call_count >= 2

    @patch("src.batch._write_index")
    @patch("src.batch.process_image")
    def test_concurrent_when_concurrency_gt_1(
        self, mock_process, mock_index, tmp_image_dir, tmp_path
    ):
        mock_process.return_value = ProcessingResult(
            Path("x.png"), tmp_path / "x.md", success=True
        )
        process_batch(
            tmp_image_dir, output_dir=tmp_path, concurrency=3
        )
        assert mock_process.call_count >= 2
