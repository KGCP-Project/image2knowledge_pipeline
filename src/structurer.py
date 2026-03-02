"""Raw extraction → structured markdown via Claude API."""

import logging
import time
from datetime import date
from pathlib import Path

import anthropic

from .config import DEFAULT_CONFIG
from .templates import STRUCTURING_PROMPT

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2


def structure_extraction(
    raw_extraction: str,
    source_file: str,
    model: str = None,
    include_frontmatter: bool = None,
) -> str:
    """Convert raw extraction into structured markdown.

    Args:
        raw_extraction: The raw text output from the extraction step.
        source_file: Original image filename (for frontmatter metadata).
        model: Claude model to use.
        include_frontmatter: Whether to prepend YAML frontmatter.

    Returns:
        Formatted markdown string.
    """
    model = model or DEFAULT_CONFIG["model"]
    if include_frontmatter is None:
        include_frontmatter = DEFAULT_CONFIG["include_frontmatter"]

    prompt = STRUCTURING_PROMPT.format(extraction=raw_extraction)

    client = anthropic.Anthropic()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"Structuring attempt {attempt} for {source_file}")
            message = client.messages.create(
                model=model,
                max_tokens=DEFAULT_CONFIG["max_tokens_structuring"],
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )
            markdown = message.content[0].text

            if not markdown or not markdown.strip():
                raise ValueError("Empty structuring result")

            if include_frontmatter:
                frontmatter = _build_frontmatter(raw_extraction, source_file)
                markdown = frontmatter + "\n" + markdown

            logger.info(f"Structuring complete for {source_file} ({len(markdown)} chars)")
            return markdown

        except anthropic.RateLimitError:
            delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(f"Rate limited, retrying in {delay}s...")
            time.sleep(delay)
        except anthropic.APIError as e:
            if attempt == MAX_RETRIES:
                raise
            delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(f"API error ({e}), retrying in {delay}s...")
            time.sleep(delay)

    raise RuntimeError(f"Structuring failed after {MAX_RETRIES} attempts for {source_file}")


def _build_frontmatter(raw_extraction: str, source_file: str) -> str:
    """Build YAML frontmatter from the raw extraction metadata."""
    # Parse basic metadata from the extraction text
    title = _extract_field(raw_extraction, "TITLE")
    author = _extract_field(raw_extraction, "AUTHOR/SOURCE") or _extract_field(
        raw_extraction, "AUTHOR"
    )
    content_type = _extract_field(raw_extraction, "CONTENT TYPE") or "other"

    lines = [
        "---",
        "source_type: image_extraction",
        f"source_file: {source_file}",
        f"content_type: {content_type.lower().replace(' ', '_')}",
    ]
    if title:
        lines.append(f'title: "{title}"')
    if author:
        lines.append(f'author: "{author}"')
    lines.append(f"extracted_date: {date.today().isoformat()}")
    lines.append("---")
    return "\n".join(lines)


def _extract_field(text: str, field_name: str) -> str:
    """Try to pull a metadata field value from the raw extraction text."""
    for line in text.split("\n"):
        line_stripped = line.strip().lstrip("#").strip()
        # Match patterns like "TITLE: Some Title" or "1. TITLE: Some Title"
        for prefix in [f"{field_name}:", f"{field_name} -", f"{field_name}."]:
            if prefix.lower() in line_stripped.lower():
                idx = line_stripped.lower().index(prefix.lower()) + len(prefix)
                value = line_stripped[idx:].strip().strip('"').strip("'")
                if value:
                    return value
    return ""
