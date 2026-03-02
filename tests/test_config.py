"""Tests for src/config.py — configuration, validation, and filename handling."""

import pytest
from pathlib import Path

from src.config import is_supported_image, slugify_filename, get_output_path, DEFAULT_CONFIG


class TestIsSupportedImage:
    """Tests for is_supported_image()."""

    @pytest.mark.parametrize("ext", [".png", ".jpg", ".jpeg", ".gif", ".webp"])
    def test_supported_extensions(self, tmp_path, ext):
        p = tmp_path / f"image{ext}"
        p.touch()
        assert is_supported_image(p) is True

    @pytest.mark.parametrize("ext", [".PNG", ".JPG", ".Jpeg", ".GIF", ".WebP"])
    def test_supported_extensions_case_insensitive(self, tmp_path, ext):
        p = tmp_path / f"image{ext}"
        p.touch()
        assert is_supported_image(p) is True

    @pytest.mark.parametrize("ext", [".pdf", ".txt", ".svg", ".bmp", ".tiff", ".doc"])
    def test_unsupported_extensions(self, tmp_path, ext):
        p = tmp_path / f"file{ext}"
        p.touch()
        assert is_supported_image(p) is False

    def test_no_extension(self, tmp_path):
        p = tmp_path / "noext"
        p.touch()
        assert is_supported_image(p) is False


class TestSlugifyFilename:
    """Tests for slugify_filename()."""

    def test_basic_slugify(self):
        assert slugify_filename("My Image.png") == "my-image"

    def test_underscores_replaced(self):
        assert slugify_filename("3_horizon_AI_Strat_Framework.jpg") == "3-horizon-ai-strat-framework"

    def test_special_characters_removed(self):
        assert slugify_filename("My Cool Image (v2).png") == "my-cool-image-v2"

    def test_multiple_separators_collapsed(self):
        assert slugify_filename("image---name___here.png") == "image-name-here"

    def test_leading_trailing_hyphens_stripped(self):
        assert slugify_filename("--leading-trailing--.png") == "leading-trailing"

    def test_already_clean(self):
        assert slugify_filename("clean-name.png") == "clean-name"

    def test_numbers_preserved(self):
        assert slugify_filename("step1-step2-step3.jpg") == "step1-step2-step3"

    def test_extension_stripped(self):
        result = slugify_filename("photo.jpeg")
        assert ".jpeg" not in result
        assert result == "photo"


class TestGetOutputPath:
    """Tests for get_output_path()."""

    def test_auto_generated_name(self, tmp_path):
        input_path = Path("My Image.png")
        result = get_output_path(input_path, tmp_path)
        assert result == tmp_path / "my-image.md"

    def test_custom_name_without_extension(self, tmp_path):
        input_path = Path("anything.png")
        result = get_output_path(input_path, tmp_path, output_name="custom-name")
        assert result == tmp_path / "custom-name.md"

    def test_custom_name_with_extension(self, tmp_path):
        input_path = Path("anything.png")
        result = get_output_path(input_path, tmp_path, output_name="custom-name.md")
        assert result == tmp_path / "custom-name.md"

    def test_output_dir_is_used(self, tmp_path):
        out = tmp_path / "docs"
        result = get_output_path(Path("img.png"), out)
        assert result.parent == out


class TestDefaultConfig:
    """Verify DEFAULT_CONFIG has expected keys and sane values."""

    def test_has_required_keys(self):
        required = ["model", "max_tokens_extraction", "max_tokens_structuring",
                     "output_dir", "supported_extensions", "concurrency"]
        for key in required:
            assert key in DEFAULT_CONFIG

    def test_supported_extensions_not_empty(self):
        assert len(DEFAULT_CONFIG["supported_extensions"]) > 0

    def test_concurrency_positive(self):
        assert DEFAULT_CONFIG["concurrency"] >= 1
