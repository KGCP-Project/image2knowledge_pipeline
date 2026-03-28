"""Image sanitization to protect against prompt injection via metadata and formatting elements.

Strips all non-pixel data (EXIF, IPTC, XMP, ICC profiles, PNG text chunks, JPEG
comments, GIF comment extensions) and re-encodes the image from raw pixel data
only. Optionally flattens alpha channels where hidden text could be embedded.
"""

import io
import logging
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, PngImagePlugin

logger = logging.getLogger(__name__)

# Alpha channel complexity threshold -- if unique alpha values exceed this,
# the channel likely contains more than simple transparency masks
ALPHA_COMPLEXITY_THRESHOLD = 10


@dataclass
class SanitizeResult:
    """Result of sanitizing an image."""

    original_path: Path
    sanitized_path: Path = None
    metadata_stripped: list = field(default_factory=list)
    alpha_flattened: bool = False
    warnings: list = field(default_factory=list)
    success: bool = True
    error: str = None


def extract_metadata_report(image_path: Path) -> dict:
    """Extract a report of all metadata found in an image before stripping.

    This is for auditing -- lets you see what was removed.

    Returns:
        Dictionary with metadata categories and their contents.
    """
    report = {}
    try:
        img = Image.open(image_path)

        # EXIF data
        exif = img.getexif()
        if exif:
            exif_items = {}
            for tag_id, value in exif.items():
                try:
                    exif_items[str(tag_id)] = str(value)[:200]
                except Exception:
                    exif_items[str(tag_id)] = "<unreadable>"
            if exif_items:
                report["exif"] = exif_items

        # PNG text chunks
        if hasattr(img, "text") and img.text:
            report["png_text_chunks"] = dict(img.text)

        # Image info (contains misc metadata including JPEG comments)
        info_keys = {k: str(v)[:200] for k, v in img.info.items()
                     if k not in ("icc_profile", "exif", "dpi", "jfif", "jfif_version",
                                  "jfif_unit", "jfif_density")}
        if info_keys:
            report["image_info"] = info_keys

        # ICC profile presence
        if "icc_profile" in img.info:
            report["icc_profile"] = "present (will be stripped)"

        # Check alpha channel
        if img.mode == "RGBA":
            alpha = img.split()[3]
            unique_alpha = len(set(alpha.tobytes()))
            report["alpha_channel"] = {
                "present": True,
                "unique_values": unique_alpha,
                "suspicious": unique_alpha > ALPHA_COMPLEXITY_THRESHOLD,
            }

    except Exception as e:
        report["error"] = str(e)

    return report


def sanitize_image(
    input_path: Path,
    output_path: Path = None,
    flatten_alpha: bool = True,
    alpha_threshold: int = ALPHA_COMPLEXITY_THRESHOLD,
) -> SanitizeResult:
    """Re-render an image from raw pixel data, stripping all metadata.

    This protects against prompt injection via:
    - EXIF metadata (ImageDescription, UserComment, Artist, Copyright, XPComment)
    - IPTC data (Caption-Abstract, Keywords, Special Instructions)
    - XMP metadata (arbitrary XML text blocks)
    - PNG text chunks (tEXt, iTXt, zTXt -- arbitrary key-value text)
    - JPEG comment markers (COM segments)
    - GIF comment extensions
    - ICC color profiles (can contain descriptive text)
    - Alpha channel steganography (text hidden in transparent layer)

    Args:
        input_path: Path to the original image.
        output_path: Path for the sanitized image. If None, writes to a
                     temp file alongside the original with '_clean' suffix.
        flatten_alpha: If True, flatten suspicious alpha channels to RGB.
        alpha_threshold: Number of unique alpha values above which the
                        channel is considered suspicious.

    Returns:
        SanitizeResult with details of what was stripped.
    """
    input_path = Path(input_path)
    result = SanitizeResult(original_path=input_path)

    if not input_path.exists():
        result.success = False
        result.error = f"File not found: {input_path}"
        return result

    try:
        img = Image.open(input_path)
    except Exception as e:
        result.success = False
        result.error = f"Cannot open image: {e}"
        return result

    # Determine output path
    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}_clean.png"
    result.sanitized_path = Path(output_path)

    # Audit what we're stripping
    exif = img.getexif()
    if exif:
        result.metadata_stripped.append(f"EXIF ({len(exif)} tags)")
        logger.info(f"Stripping EXIF data ({len(exif)} tags) from {input_path.name}")

    if hasattr(img, "text") and img.text:
        result.metadata_stripped.append(f"PNG text chunks ({len(img.text)} entries)")
        logger.info(f"Stripping PNG text chunks from {input_path.name}")
        for key, value in img.text.items():
            logger.debug(f"  PNG text '{key}': {value[:100]}...")

    info_meta = {k for k in img.info.keys() if k not in ("dpi", "jfif", "jfif_version",
                                                           "jfif_unit", "jfif_density")}
    if "icc_profile" in img.info:
        result.metadata_stripped.append("ICC profile")
        logger.info(f"Stripping ICC profile from {input_path.name}")

    if "comment" in img.info:
        result.metadata_stripped.append("JPEG/GIF comment")
        logger.info(f"Stripping comment from {input_path.name}")

    if "exif" in img.info:
        result.metadata_stripped.append("EXIF binary blob")

    # Handle alpha channel
    if img.mode == "RGBA" and flatten_alpha:
        alpha = img.split()[3]
        unique_alpha = len(set(alpha.tobytes()))
        if unique_alpha > alpha_threshold:
            result.alpha_flattened = True
            result.warnings.append(
                f"Alpha channel had {unique_alpha} unique values "
                f"(threshold: {alpha_threshold}) -- flattened to RGB"
            )
            logger.warning(
                f"Suspicious alpha channel in {input_path.name}: "
                f"{unique_alpha} unique values -- flattening to RGB"
            )
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=alpha)
            img = background
        else:
            # Simple alpha (e.g., just fully opaque) -- safe to flatten
            img = img.convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Re-render from raw pixel data -- this is the key security step.
    # Creating a new image and copying pixel data ensures NO metadata,
    # no ancillary chunks, no comment markers carry over.
    clean = Image.new("RGB", img.size)
    clean.frombytes(img.tobytes())

    # Save as clean PNG with no metadata
    clean.save(str(result.sanitized_path), format="PNG", pnginfo=None)

    logger.info(
        f"Sanitized {input_path.name} -> {result.sanitized_path.name} "
        f"(stripped: {', '.join(result.metadata_stripped) or 'none'})"
    )

    return result


def sanitize_to_bytes(input_path: Path, **kwargs) -> tuple:
    """Sanitize an image and return the clean bytes directly (no temp file).

    This is the primary interface for the pipeline -- sanitize in memory
    and pass clean bytes to the API without writing intermediate files.

    Args:
        input_path: Path to the original image.
        **kwargs: Passed to sanitize logic (flatten_alpha, alpha_threshold).

    Returns:
        Tuple of (clean_png_bytes, sanitize_result).
    """
    input_path = Path(input_path)
    flatten_alpha = kwargs.get("flatten_alpha", True)
    alpha_threshold = kwargs.get("alpha_threshold", ALPHA_COMPLEXITY_THRESHOLD)

    result = SanitizeResult(original_path=input_path)

    if not input_path.exists():
        result.success = False
        result.error = f"File not found: {input_path}"
        return None, result

    try:
        img = Image.open(input_path)
    except Exception as e:
        result.success = False
        result.error = f"Cannot open image: {e}"
        return None, result

    # Audit metadata
    exif = img.getexif()
    if exif:
        result.metadata_stripped.append(f"EXIF ({len(exif)} tags)")

    if hasattr(img, "text") and img.text:
        result.metadata_stripped.append(f"PNG text chunks ({len(img.text)} entries)")

    if "icc_profile" in img.info:
        result.metadata_stripped.append("ICC profile")

    if "comment" in img.info:
        result.metadata_stripped.append("JPEG/GIF comment")

    # Handle alpha
    if img.mode == "RGBA" and flatten_alpha:
        alpha = img.split()[3]
        unique_alpha = len(set(alpha.tobytes()))
        if unique_alpha > alpha_threshold:
            result.alpha_flattened = True
            result.warnings.append(
                f"Alpha channel had {unique_alpha} unique values -- flattened"
            )
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=alpha)
            img = background
        else:
            img = img.convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Re-render clean
    clean = Image.new("RGB", img.size)
    clean.frombytes(img.tobytes())

    # Encode to bytes in memory
    buffer = io.BytesIO()
    clean.save(buffer, format="PNG", pnginfo=None)
    clean_bytes = buffer.getvalue()

    result.sanitized_path = None  # in-memory, no file
    return clean_bytes, result
