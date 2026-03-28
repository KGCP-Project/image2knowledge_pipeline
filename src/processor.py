"""Orchestrates the single-image processing pipeline."""

import logging
from pathlib import Path

from .config import DEFAULT_CONFIG, get_output_path, is_supported_image
from .extractor import extract_from_image
from .sanitize import sanitize_to_bytes
from .structurer import structure_extraction
from .validator import validate_extraction, format_validation_report

logger = logging.getLogger(__name__)


class ProcessingResult:
    """Result of processing a single image."""

    def __init__(self, input_path: Path, output_path: Path = None, success: bool = True,
                 error: str = None, validation_report: str = None,
                 sanitize_summary: str = None):
        self.input_path = input_path
        self.output_path = output_path
        self.success = success
        self.error = error
        self.validation_report = validation_report
        self.sanitize_summary = sanitize_summary

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
    skip_sanitize: bool = False,
    force_on_warning: bool = False,
) -> ProcessingResult:
    """Process a single image through the full pipeline.

    Pipeline: sanitize -> extract -> validate -> structure -> write

    The original image is never modified. A sanitized copy (in memory) is
    created and used for extraction. The original file remains untouched.

    Args:
        image_path: Path to the input image.
        output_dir: Directory for output markdown. Defaults to ./output/.
        output_name: Custom output filename. Auto-generated if None.
        model: Claude model override.
        include_frontmatter: Whether to include YAML frontmatter.
        dry_run: If True, show what would happen without making API calls.
        verbose: If True, log detailed processing info.
        skip_sanitize: If True, skip the sanitization step (not recommended).
        force_on_warning: If True, proceed even when validation flags issues.

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
        sanitized_bytes = None
        sanitize_summary = None

        # Step 0: Sanitize (original file is preserved, sanitized copy in memory)
        if not skip_sanitize:
            logger.info(f"Sanitizing {image_path.name} (original preserved)...")
            clean_bytes, san_result = sanitize_to_bytes(image_path)

            if not san_result.success:
                return ProcessingResult(
                    image_path, success=False,
                    error=f"Sanitization failed: {san_result.error}"
                )

            sanitized_bytes = clean_bytes
            stripped = san_result.metadata_stripped
            sanitize_summary = (
                f"Stripped: {', '.join(stripped)}" if stripped else "Clean (no metadata found)"
            )
            if san_result.alpha_flattened:
                sanitize_summary += " | Alpha channel flattened"
            if san_result.warnings:
                for w in san_result.warnings:
                    logger.warning(f"Sanitize warning: {w}")

            logger.info(f"Sanitize result: {sanitize_summary}")

        # Step 1: Extract (uses sanitized bytes if available, otherwise raw file)
        logger.info(f"Extracting from {image_path.name}...")
        raw_extraction = extract_from_image(
            image_path, model=model, sanitized_bytes=sanitized_bytes
        )

        if not raw_extraction or not raw_extraction.strip():
            return ProcessingResult(
                image_path, success=False,
                error="Empty extraction -- flagged for manual review"
            )

        # Step 2: Validate extraction for injection patterns
        logger.info(f"Validating extraction for {image_path.name}...")
        validation = validate_extraction(raw_extraction)
        validation_report = format_validation_report(validation)

        if validation.flagged and not force_on_warning:
            logger.warning(
                f"Extraction flagged for {image_path.name}: "
                f"{len(validation.findings)} suspicious pattern(s)"
            )
            return ProcessingResult(
                image_path, success=False,
                error=f"Extraction flagged for review ({validation.severity}): "
                      f"{len(validation.findings)} suspicious pattern(s). "
                      f"Use --force to override.",
                validation_report=validation_report,
                sanitize_summary=sanitize_summary,
            )

        if validation.findings:
            logger.info(f"Validation noted {len(validation.findings)} low-severity pattern(s)")

        # Step 3: Structure
        logger.info(f"Structuring {image_path.name}...")
        markdown = structure_extraction(
            raw_extraction,
            source_file=image_path.name,
            model=model,
            include_frontmatter=include_frontmatter,
        )

        # Step 4: Write output
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        logger.info(f"Written: {output_path}")

        return ProcessingResult(
            image_path, output_path, success=True,
            validation_report=validation_report,
            sanitize_summary=sanitize_summary,
        )

    except Exception as e:
        logger.error(f"Failed to process {image_path.name}: {e}")
        return ProcessingResult(image_path, success=False, error=str(e))
