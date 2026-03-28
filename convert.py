#!/usr/bin/env python3
"""Image-to-Knowledge Document Converter — CLI entry point.

Converts infographic images into structured, AI-consumable markdown documents.

Usage:
    python convert.py image.png
    python convert.py /path/to/folder/ --output-dir ./docs/
    python convert.py /path/to/folder/ --dry-run --verbose
"""

import logging
import sys
from pathlib import Path

import click

from src.processor import process_image
from src.batch import process_batch

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"


@click.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.option("-o", "--output", "output_name", default=None, help="Output filename (single image mode only).")
@click.option("--output-dir", default=None, help="Output directory (default: ./output/).")
@click.option("--recursive", is_flag=True, help="Process subfolders when input is a directory.")
@click.option("--dry-run", is_flag=True, help="Show what would be processed without making API calls.")
@click.option("--verbose", is_flag=True, help="Show detailed processing logs.")
@click.option("--concurrency", default=3, type=int, help="Max parallel processing for batch mode (default: 3).")
@click.option("--skip-existing", is_flag=True, help="Skip images that already have output files.")
@click.option("--model", default=None, help="Claude model to use (default: claude-sonnet-4-20250514).")
@click.option("--no-frontmatter", is_flag=True, help="Omit YAML frontmatter from output.")
@click.option("--no-sanitize", is_flag=True, help="Skip image sanitization (not recommended).")
@click.option("--force", is_flag=True, help="Proceed even when validation flags suspicious patterns.")
def main(input_path, output_name, output_dir, recursive, dry_run, verbose, concurrency, skip_existing, model, no_frontmatter, no_sanitize, force):
    """Convert images to structured knowledge documents.

    INPUT_PATH can be a single image file or a folder of images.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format=LOG_FORMAT)
    logger = logging.getLogger(__name__)

    input_path = Path(input_path).resolve()
    include_frontmatter = not no_frontmatter

    if input_path.is_file():
        # Single image mode
        click.echo(f"Processing: {input_path.name}")
        result = process_image(
            input_path,
            output_dir=output_dir,
            output_name=output_name,
            model=model,
            include_frontmatter=include_frontmatter,
            dry_run=dry_run,
            verbose=verbose,
            skip_sanitize=no_sanitize,
            force_on_warning=force,
        )
        if result.success:
            if dry_run:
                click.echo(f"[DRY RUN] Would create: {result.output_path}")
            else:
                click.echo(f"Created: {result.output_path}")
                if result.sanitize_summary:
                    click.echo(f"  Sanitize: {result.sanitize_summary}")
                if result.validation_report and "CLEAN" not in result.validation_report:
                    click.echo(f"  {result.validation_report}")
        else:
            click.echo(f"Failed: {result.error}", err=True)
            if result.validation_report:
                click.echo(result.validation_report, err=True)
            sys.exit(1)

    elif input_path.is_dir():
        # Batch mode
        click.echo(f"Scanning: {input_path}")
        results = process_batch(
            input_path,
            output_dir=output_dir,
            recursive=recursive,
            model=model,
            include_frontmatter=include_frontmatter,
            dry_run=dry_run,
            verbose=verbose,
            concurrency=concurrency,
            skip_existing=skip_existing,
        )

        if not results:
            click.echo("No supported images found.")
            sys.exit(0)

        succeeded = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)

        click.echo(f"\nDone: {succeeded} converted, {failed} failed out of {len(results)} total.")

        if failed:
            click.echo("\nFailed images:")
            for r in results:
                if not r.success:
                    click.echo(f"  - {r.input_path.name}: {r.error}")
            sys.exit(1)
    else:
        click.echo(f"Invalid input: {input_path}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
