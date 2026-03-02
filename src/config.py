"""Configuration and defaults for image-to-knowledge converter."""

import re
from pathlib import Path

DEFAULT_CONFIG = {
    "model": "claude-sonnet-4-20250514",
    "max_tokens_extraction": 4096,
    "max_tokens_structuring": 8192,
    "output_dir": "./output",
    "output_format": "md",
    "supported_extensions": [".png", ".jpg", ".jpeg", ".gif", ".webp"],
    "concurrency": 3,
    "include_frontmatter": True,
    "include_quick_reference": True,
    "include_usage_notes": True,
}

MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def is_supported_image(path: Path) -> bool:
    """Check if a file has a supported image extension."""
    return path.suffix.lower() in DEFAULT_CONFIG["supported_extensions"]


def slugify_filename(filename: str) -> str:
    """Convert a filename to a clean slug for the output markdown file.

    Examples:
        '3_horizon_AI_Strat_Framework.jpg' -> '3-horizon-ai-strat-framework'
        'My Cool Image (v2).png' -> 'my-cool-image-v2'
    """
    stem = Path(filename).stem
    slug = stem.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def get_output_path(input_path: Path, output_dir: Path, output_name: str = None) -> Path:
    """Determine the output file path for a given input image."""
    if output_name:
        name = output_name if output_name.endswith(".md") else f"{output_name}.md"
    else:
        name = f"{slugify_filename(input_path.name)}.md"
    return output_dir / name
