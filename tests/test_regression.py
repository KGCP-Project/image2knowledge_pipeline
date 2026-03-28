"""Regression tests -- end-to-end pipeline behavior with mocked API responses.

These tests verify that the full pipeline produces stable, well-formed output
and catches regressions in output format, frontmatter structure, and file handling.
"""

import io
import pytest
from pathlib import Path
from datetime import date
from unittest.mock import patch, MagicMock

from src.processor import process_image
from src.batch import process_batch
from src.config import slugify_filename
from src.sanitize import SanitizeResult


MOCK_EXTRACTION = """\
TITLE: DevOps Lifecycle Overview
SUBTITLE: The 8 phases of continuous delivery
AUTHOR/SOURCE: Platform Engineering Weekly
CONTENT TYPE: process_diagram

SECTIONS:
## Plan
- Define requirements and roadmap

## Code
- Write and review application code

## Build
- Compile, lint, and package artifacts

## Test
- Run unit, integration, and e2e tests

## Release
- Tag version, generate changelog

## Deploy
- Push to staging and production

## Operate
- Monitor uptime and performance

## Monitor
- Collect metrics, logs, and alerts

RELATIONSHIPS: Sequential cycle -- Monitor feeds back into Plan.
VISUAL STRUCTURE: Circular flow (infinity loop / figure-8)."""

MOCK_STRUCTURED = """\
# DevOps Lifecycle Overview

> The 8 phases of continuous delivery

---

## 1. Plan

- Define requirements and roadmap

## 2. Code

- Write and review application code

## 3. Build

- Compile, lint, and package artifacts

## 4. Test

- Run unit, integration, and e2e tests

## 5. Release

- Tag version, generate changelog

## 6. Deploy

- Push to staging and production

## 7. Operate

- Monitor uptime and performance

## 8. Monitor

- Collect metrics, logs, and alerts

> Note: This is a continuous cycle -- Monitor feeds back into Plan.

## Quick Reference

| Phase | Key Activity |
|-------|-------------|
| Plan | Define requirements and roadmap |
| Code | Write and review application code |
| Build | Compile, lint, and package artifacts |
| Test | Run unit, integration, and e2e tests |
| Release | Tag version, generate changelog |
| Deploy | Push to staging and production |
| Operate | Monitor uptime and performance |
| Monitor | Collect metrics, logs, and alerts |

## Usage Notes

- The cycle is continuous -- each phase feeds into the next.
- Automation is key to reducing cycle time across all 8 phases.

*Original process diagram by Platform Engineering Weekly*"""


def _mock_sanitize_ok(input_path, **kwargs):
    """Return a successful sanitize result with minimal clean PNG bytes."""
    from PIL import Image
    img = Image.new("RGB", (1, 1), (255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue(), SanitizeResult(original_path=input_path)


def _mock_anthropic_for_pipeline():
    """Create a mock that returns extraction on first call, structured on second."""
    mock_cls = MagicMock()
    mock_client = MagicMock()
    mock_cls.return_value = mock_client

    responses = [MOCK_EXTRACTION, MOCK_STRUCTURED]
    call_count = {"n": 0}

    def create_response(*args, **kwargs):
        idx = min(call_count["n"], len(responses) - 1)
        call_count["n"] += 1
        msg = MagicMock()
        msg.content = [MagicMock(text=responses[idx])]
        return msg

    mock_client.messages.create.side_effect = create_response
    return mock_cls


class TestEndToEndPipeline:
    """Full pipeline regression tests with mocked API."""

    @patch("src.processor.sanitize_to_bytes", side_effect=_mock_sanitize_ok)
    @patch("src.processor.structure_extraction")
    @patch("src.processor.extract_from_image")
    def test_single_image_produces_valid_markdown(
        self, mock_extract, mock_structure, mock_sanitize, tmp_image, tmp_path
    ):
        mock_extract.return_value = MOCK_EXTRACTION

        # Simulate what structure_extraction does: prepend frontmatter to body
        from src.structurer import _build_frontmatter
        frontmatter = _build_frontmatter(MOCK_EXTRACTION, tmp_image.name)
        mock_structure.return_value = frontmatter + "\n" + MOCK_STRUCTURED

        result = process_image(
            tmp_image, output_dir=tmp_path, include_frontmatter=False
        )

        assert result.success is True
        assert result.output_path.exists()

        content = result.output_path.read_text()

        # Frontmatter checks
        assert content.startswith("---")
        assert "source_type: image_extraction" in content
        assert "content_type: process_diagram" in content
        assert 'title: "DevOps Lifecycle Overview"' in content
        assert 'author: "Platform Engineering Weekly"' in content
        assert f"extracted_date: {date.today().isoformat()}" in content

        # Body checks
        assert "# DevOps Lifecycle Overview" in content
        assert "## 1. Plan" in content
        assert "## 8. Monitor" in content
        assert "Quick Reference" in content
        assert "Usage Notes" in content

    @patch("src.processor.sanitize_to_bytes", side_effect=_mock_sanitize_ok)
    @patch("src.processor.structure_extraction")
    @patch("src.processor.extract_from_image")
    def test_output_filename_is_slugified(
        self, mock_extract, mock_structure, mock_sanitize, tmp_path
    ):
        img = tmp_path / "My DevOps_Lifecycle (v2).png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

        mock_extract.return_value = MOCK_EXTRACTION
        mock_structure.return_value = MOCK_STRUCTURED

        out_dir = tmp_path / "output"
        result = process_image(img, output_dir=out_dir)

        assert result.success is True
        assert result.output_path.name == "my-devops-lifecycle-v2.md"

    @patch("src.processor.sanitize_to_bytes", side_effect=_mock_sanitize_ok)
    @patch("src.processor.structure_extraction")
    @patch("src.processor.extract_from_image")
    def test_no_frontmatter_option(
        self, mock_extract, mock_structure, mock_sanitize, tmp_image, tmp_path
    ):
        mock_extract.return_value = MOCK_EXTRACTION
        mock_structure.return_value = MOCK_STRUCTURED

        result = process_image(
            tmp_image, output_dir=tmp_path, include_frontmatter=False
        )
        content = result.output_path.read_text()
        assert not content.startswith("---")
        assert "# DevOps Lifecycle Overview" in content


class TestBatchRegression:
    """Batch processing regression tests."""

    @patch("src.batch.process_image")
    def test_batch_generates_index(self, mock_process, tmp_image_dir, tmp_path):
        def fake_process(img, **kwargs):
            out = tmp_path / f"{slugify_filename(img.name)}.md"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(f"# {img.stem}")
            return MagicMock(
                input_path=img,
                output_path=out,
                success=True,
                error=None,
            )

        mock_process.side_effect = fake_process

        results = process_batch(tmp_image_dir, output_dir=tmp_path)

        index = tmp_path / "_index.md"
        assert index.exists()
        content = index.read_text()
        assert "Knowledge Documents Index" in content
        assert "| Document |" in content

    @patch("src.batch.process_image")
    def test_batch_index_records_failures(self, mock_process, tmp_image_dir, tmp_path):
        call_count = {"n": 0}

        def alternating_process(img, **kwargs):
            call_count["n"] += 1
            if call_count["n"] % 2 == 0:
                return MagicMock(
                    input_path=img, output_path=None,
                    success=False, error="simulated failure",
                )
            out = tmp_path / f"{slugify_filename(img.name)}.md"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(f"# {img.stem}")
            return MagicMock(
                input_path=img, output_path=out,
                success=True, error=None,
            )

        mock_process.side_effect = alternating_process

        results = process_batch(tmp_image_dir, output_dir=tmp_path)

        index = tmp_path / "_index.md"
        assert index.exists()
        content = index.read_text()
        assert "Failed" in content


class TestSlugifyRegression:
    """Ensure slug generation remains stable across versions."""

    @pytest.mark.parametrize("input_name,expected_slug", [
        ("My Image.png", "my-image"),
        ("3_horizon_AI_Strat_Framework.jpg", "3-horizon-ai-strat-framework"),
        ("My Cool Image (v2).png", "my-cool-image-v2"),
        ("ALLCAPS.PNG", "allcaps"),
        ("already-clean.webp", "already-clean"),
        ("spaces   and   tabs.jpeg", "spaces-and-tabs"),
        ("123.gif", "123"),
    ])
    def test_slugify_stability(self, input_name, expected_slug):
        """These slugs must not change -- output filenames depend on them."""
        assert slugify_filename(input_name) == expected_slug
