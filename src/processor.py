"""Orchestrates the single-image processing pipeline."""

import logging
from pathlib import Path

from .config import DEFAULT_CONFIG, get_output_path, is_supported_image
from .extractor import extract_from_image
from .structurer import structure_extraction

logger = logging.getLogger(__name__)


class ProcessingResult:
    """Result of processing a single image."""

    def __init__(self, input_path: Path, output_path: Path = None, success: bool = True, error: str = None):
        self.input_path = input_path
        self.output_path = output_path
        self.success = success
        self.error = error

    def __repr__(self):
        status = "OK" if self.success else f"FAIL: {self.error}"
        return f"<ProcessingResult {self.input_path.name} -> {status}>"


def process_image(
    image_path: Path,
    output_dir: Path = None,
    output_name: str = None,
    model: str = None,
    include_frontmatter: bool = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> ProcessingResult:
    """Process a single image through the full extraction → structuring pipeline.

    Args:
        image_path: Path to the input image.
        output_dir: Directory for output markdown. Defaults to ./output/.
        output_name: Custom output filename. Auto-generated if None.
        model: Claude model override.
        include_frontmatter: Whether to include YAML frontmatter.
        dry_run: If True, show what would happen without making API calls.
        verbose: If True, log detailed processing info.

    Returns:
        ProcessingResult with status and paths.
    """
    image_path = Path(image_path).resolve()
    output_dir = Path(output_dir or DEFAULT_CONFIG["output_dir"]).resolve()

    if not image_path.exists():
        return ProcessingResult(image_path, success=False, error="File not found")

    if not is_supported_image(image_path):
        return ProcessingResult(
            image_path, success=False, error=f"Unsupported format: {image_path.suffix}"
        )

    output_path = get_output_path(image_path, output_dir, output_name)

    if dry_run:
        logger.info(f"[DRY RUN] {image_path.name} -> {output_path}")
        return ProcessingResult(image_path, output_path, success=True)

    try:
        # Step 1: Extract
        logger.info(f"Extracting from {image_path.name}...")
        raw_extraction = extract_from_image(image_path, model=model)

        if not raw_extraction or not raw_extraction.strip():
            return ProcessingResult(
                image_path, success=False, error="Empty extraction — flagged for manual review"
            )

        # Step 2: Structure
        logger.info(f"Structuring {image_path.name}...")
        markdown = structure_extraction(
            raw_extraction,
            source_file=image_path.name,
            model=model,
            include_frontmatter=include_frontmatter,
        )

        # Step 3: Write output
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        logger.info(f"Written: {output_path}")

        return ProcessingResult(image_path, output_path, success=True)

    except Exception as e:
        logger.error(f"Failed to process {image_path.name}: {e}")
        return ProcessingResult(image_path, success=False, error=str(e))
