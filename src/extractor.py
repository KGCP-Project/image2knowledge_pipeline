"""Image -> raw text extraction via Claude Vision API."""

import base64
import logging
import time
from pathlib import Path

import anthropic

from .config import MEDIA_TYPES, DEFAULT_CONFIG
from .templates import EXTRACTION_PROMPT

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds


def extract_from_image(image_path: Path, model: str = None, sanitized_bytes: bytes = None) -> str:
    """Send an image to Claude Vision API and extract all text/structure.

    Args:
        image_path: Path to the image file (used for logging and format detection
                    when sanitized_bytes is not provided).
        model: Claude model to use. Defaults to config value.
        sanitized_bytes: Pre-sanitized PNG bytes to use instead of reading from
                        disk. When provided, the original file is NOT read --
                        only the clean bytes are sent to the API.

    Returns:
        Raw extracted text with structural annotations.

    Raises:
        FileNotFoundError: If image_path doesn't exist and no sanitized_bytes.
        ValueError: If image format is unsupported.
        anthropic.APIError: If API call fails after retries.
    """
    if sanitized_bytes is not None:
        # Use pre-sanitized bytes -- always PNG after sanitization
        image_data = base64.standard_b64encode(sanitized_bytes).decode("utf-8")
        media_type = "image/png"
        logger.info(f"Using sanitized bytes for {image_path.name}")
    else:
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        suffix = image_path.suffix.lower()
        media_type = MEDIA_TYPES.get(suffix)
        if not media_type:
            raise ValueError(f"Unsupported image format: {suffix}")

        with open(image_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    model = model or DEFAULT_CONFIG["model"]

    client = anthropic.Anthropic()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"Extraction attempt {attempt} for {image_path.name}")
            message = client.messages.create(
                model=model,
                max_tokens=DEFAULT_CONFIG["max_tokens_extraction"],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_data,
                                },
                            },
                            {
                                "type": "text",
                                "text": EXTRACTION_PROMPT,
                            },
                        ],
                    }
                ],
            )
            result = message.content[0].text
            if not result or not result.strip():
                logger.warning(f"Empty extraction for {image_path.name}")
                raise ValueError("Empty extraction result")
            logger.info(f"Extraction complete for {image_path.name} ({len(result)} chars)")
            return result

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

    raise RuntimeError(f"Extraction failed after {MAX_RETRIES} attempts for {image_path.name}")
