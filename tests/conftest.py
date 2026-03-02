"""Shared fixtures for image-to-knowledge tests."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_image(tmp_path):
    """Create a minimal valid PNG file for testing."""
    # Minimal 1x1 white PNG
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"  # PNG signature
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
        b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
        b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    img = tmp_path / "test-image.png"
    img.write_bytes(png_bytes)
    return img


@pytest.fixture
def tmp_jpg(tmp_path):
    """Create a minimal JPEG file for testing."""
    # Minimal valid JPEG (1x1 pixel)
    jpg_bytes = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00,
        0x01, 0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xD9,
    ])
    img = tmp_path / "sample photo.jpg"
    img.write_bytes(jpg_bytes)
    return img


@pytest.fixture
def tmp_unsupported(tmp_path):
    """Create a file with an unsupported extension."""
    f = tmp_path / "document.pdf"
    f.write_bytes(b"not an image")
    return f


@pytest.fixture
def tmp_image_dir(tmp_path, tmp_image):
    """Create a directory with multiple image files."""
    (tmp_path / "alpha.png").write_bytes(tmp_image.read_bytes())
    (tmp_path / "beta.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    (tmp_path / "readme.txt").write_text("not an image")
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "gamma.webp").write_bytes(b"RIFF\x00\x00\x00\x00WEBP")
    return tmp_path


@pytest.fixture
def sample_raw_extraction():
    """Sample raw extraction text as returned by the extractor."""
    return """\
TITLE: Test Framework Overview
SUBTITLE: A sample framework for testing
AUTHOR/SOURCE: Test Author
CONTENT TYPE: framework

SECTIONS:
## Section 1 — First Area
- Point A
- Point B

## Section 2 — Second Area
- Point C
- Point D

RELATIONSHIPS: Section 1 leads to Section 2 in a sequential flow.

VISUAL STRUCTURE: Left-to-right flow with two boxes."""


@pytest.fixture
def sample_structured_markdown():
    """Sample structured markdown as returned by the structurer."""
    return """\
# Test Framework Overview

> A sample framework for testing

---

## 1. First Area

- **Point A**
- **Point B**

## 2. Second Area

- **Point C**
- **Point D**

## Quick Reference

| Area | Key Points |
|------|-----------|
| First Area | Point A, Point B |
| Second Area | Point C, Point D |

## Usage Notes

- Apply Section 1 before Section 2.

*Original framework by Test Author*"""


@pytest.fixture
def mock_anthropic_client(sample_raw_extraction, sample_structured_markdown):
    """Create a mock Anthropic client that returns canned responses.

    First call returns raw extraction, second call returns structured markdown.
    """
    client = MagicMock()
    responses = [sample_raw_extraction, sample_structured_markdown]
    call_count = {"n": 0}

    def make_response(*args, **kwargs):
        idx = min(call_count["n"], len(responses) - 1)
        call_count["n"] += 1
        msg = MagicMock()
        msg.content = [MagicMock(text=responses[idx])]
        return msg

    client.messages.create.side_effect = make_response
    return client
