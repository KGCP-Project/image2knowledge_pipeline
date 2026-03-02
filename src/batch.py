"""Folder/batch processing logic."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import List

from .config import DEFAULT_CONFIG, is_supported_image, slugify_filename
from .processor import ProcessingResult, process_image

logger = logging.getLogger(__name__)


def find_images(folder: Path, recursive: bool = False) -> List[Path]:
    """Find all supported image files in a folder.

    Args:
        folder: Directory to search.
        recursive: If True, search subdirectories as well.

    Returns:
        Sorted list of image file paths.
    """
    if not folder.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder}")

    pattern_fn = folder.rglob if recursive else folder.glob
    images = sorted(
        p for p in pattern_fn("*") if p.is_file() and is_supported_image(p)
    )
    return images


def process_batch(
    folder: Path,
    output_dir: Path = None,
    recursive: bool = False,
    model: str = None,
    include_frontmatter: bool = None,
    dry_run: bool = False,
    verbose: bool = False,
    concurrency: int = None,
    skip_existing: bool = False,
) -> List[ProcessingResult]:
    """Process all images in a folder.

    Args:
        folder: Input directory containing images.
        output_dir: Output directory for markdown files.
        recursive: Search subdirectories.
        model: Claude model override.
        include_frontmatter: Whether to include YAML frontmatter.
        dry_run: Preview mode — no API calls.
        verbose: Detailed logging.
        concurrency: Max parallel workers.
        skip_existing: Skip images that already have output files.

    Returns:
        List of ProcessingResult for each image.
    """
    folder = Path(folder).resolve()
    output_dir = Path(output_dir or DEFAULT_CONFIG["output_dir"]).resolve()
    concurrency = concurrency or DEFAULT_CONFIG["concurrency"]

    images = find_images(folder, recursive=recursive)

    if not images:
        logger.warning(f"No supported images found in {folder}")
        return []

    logger.info(f"Found {len(images)} image(s) in {folder}")

    if skip_existing:
        filtered = []
        for img in images:
            from .config import get_output_path
            out = get_output_path(img, output_dir)
            if out.exists():
                logger.info(f"Skipping (exists): {img.name}")
            else:
                filtered.append(img)
        images = filtered
        logger.info(f"{len(images)} image(s) to process after skipping existing")

    if dry_run:
        results = []
        for img in images:
            r = process_image(img, output_dir=output_dir, dry_run=True)
            results.append(r)
        return results

    results = []

    if concurrency <= 1:
        for img in images:
            r = process_image(
                img,
                output_dir=output_dir,
                model=model,
                include_frontmatter=include_frontmatter,
                verbose=verbose,
            )
            results.append(r)
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(
                    process_image,
                    img,
                    output_dir=output_dir,
                    model=model,
                    include_frontmatter=include_frontmatter,
                    verbose=verbose,
                ): img
                for img in images
            }
            for future in as_completed(futures):
                results.append(future.result())

    # Generate index file
    _write_index(results, output_dir)

    return results


def _write_index(results: List[ProcessingResult], output_dir: Path) -> None:
    """Write a _index.md summarizing all processed documents."""
    successful = [r for r in results if r.success and r.output_path]
    if not successful:
        return

    lines = [
        "# Knowledge Documents Index",
        "",
        f"> Generated on {date.today().isoformat()} | {len(successful)} documents",
        "",
        "---",
        "",
        "| Document | Source Image | Status |",
        "|----------|-------------|--------|",
    ]

    for r in sorted(successful, key=lambda x: x.output_path.name):
        doc_link = f"[{r.output_path.stem}]({r.output_path.name})"
        lines.append(f"| {doc_link} | {r.input_path.name} | Converted |")

    failed = [r for r in results if not r.success]
    if failed:
        lines.extend(["", "## Failed", ""])
        for r in failed:
            lines.append(f"- `{r.input_path.name}`: {r.error}")

    lines.append("")
    index_path = output_dir / "_index.md"
    index_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Index written: {index_path}")
