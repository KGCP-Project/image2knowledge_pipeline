---
title: "CLAUDE.md -- Image-to-Knowledge Document Converter"
scope: "System prompt, architecture, pipeline spec, and development standards"
last_updated: 2026-03-27
---

# CLAUDE.md — Image-to-Knowledge Document Converter

> A CLI tool that converts infographic images into structured, AI-consumable knowledge documents (markdown). Designed as a standalone utility and future ingestion module for the Knowledge Graph Context Pipeline (KGCP).

---

## Project Overview

### Purpose
Convert visual knowledge artifacts (infographics, architecture diagrams, flowcharts, framework charts, reference sheets, screenshots, presentation slides) into clean, structured markdown documents optimized for use by LLMs (Claude, Claude Code) and human reference.

### Design Philosophy
- **One image in, one knowledge document out** — each image produces a standalone `.md` file
- **Preserve all information** — extract every piece of text, relationship, and structure from the image
- **Add structure the visual implied** — tables, hierarchies, flow sequences that the image communicated visually should be made explicit in text
- **Enhance where obvious** — quick-reference tables, cross-references, and usage notes add value without distorting the source
- **Attribution always** — credit the original creator at the bottom of every document

---

## Architecture

```
image-to-knowledge/
├── CLAUDE.md                    # This file -- system prompt and project spec
├── README.md                    # User-facing documentation
├── convert.py                   # Main CLI entry point
├── src/
│   ├── __init__.py
│   ├── sanitize.py              # Image sanitization -- strips metadata, flattens alpha
│   ├── extractor.py             # Image -> raw text extraction via Claude Vision API
│   ├── validator.py             # Post-extraction prompt injection detection
│   ├── structurer.py            # Raw extraction -> structured markdown via Claude API
│   ├── processor.py             # Orchestrates single-image pipeline
│   ├── batch.py                 # Folder/batch processing logic
│   ├── templates.py             # Output markdown templates and formatting rules
│   └── config.py                # Configuration and defaults
├── tests/
│   ├── conftest.py              # Shared fixtures and mock data
│   ├── test_config.py           # Config/utility unit tests
│   ├── test_sanitize.py         # Image sanitization tests
│   ├── test_extractor.py        # Extraction unit tests (mocked API)
│   ├── test_validator.py        # Injection detection tests
│   ├── test_structurer.py       # Structuring unit tests (mocked API)
│   ├── test_processor.py        # Pipeline orchestration tests
│   ├── test_batch.py            # Batch processing tests
│   ├── test_cli.py              # CLI entry point tests
│   └── test_regression.py       # End-to-end regression tests
├── output/                      # Default output directory
├── examples/                    # Example inputs and outputs for reference
│   ├── input/
│   └── output/
└── requirements.txt
```

---

## Processing Pipeline

### Step 0: Image Sanitization (sanitize.py) -- SECURITY
- **Original image is preserved** -- never modified
- Strip all metadata: EXIF, IPTC, XMP, ICC profiles, PNG text chunks, JPEG comments, GIF comment extensions
- Flatten suspicious alpha channels (unique values > threshold) to prevent hidden text layers
- Re-encode from raw pixel data as clean PNG -- no metadata carries over
- Output: sanitized bytes in memory (no temp files by default)
- Can be skipped with `--no-sanitize` (not recommended)

### Step 1: Image Intake
- Validate file exists and is a supported image format
- For folders: enumerate all image files, optionally recursive
- Generate output filename from input filename (slugified, lowercase, hyphens)

### Step 2: Vision Extraction (extractor.py)
- Send **sanitized image bytes** (not raw file) to Claude Vision API
- Extraction prompt includes untrusted-input guardrails instructing the model to treat image content as DATA, not INSTRUCTIONS
- Extract ALL text, relationships, structure, attribution

### Step 3: Post-Extraction Validation (validator.py) -- SECURITY
- Scan extracted text for prompt injection indicators:
  - Role override attempts ("you are", "act as", "pretend to be")
  - Instruction manipulation ("ignore previous", "new instructions", "disregard")
  - System prompt references
  - Output control attempts
  - Encoded payloads (base64, hex)
  - Data exfiltration patterns
- False positive reduction: contextual filtering for security infographics, AI tutorials, leadership content
- Severity levels: low (noted), medium/high (blocks processing unless `--force`)
- Flagged extractions halt the pipeline and report findings for manual review

### Step 4: Structured Formatting (structurer.py)
- Convert raw extraction to clean structured markdown
- Apply appropriate formatting based on content type
- **Receives text only** -- never sees the original image, so visual injection is severed

### Step 5: Output
- Write markdown with optional YAML frontmatter
- Generate batch index when processing folders

### Security Pipeline Summary
```
Original Image (preserved)
  --> sanitize.py (strip metadata, flatten alpha, re-encode as clean PNG)
  --> extractor.py (untrusted-input prompt, sanitized bytes only, no tools)
  --> validator.py (scan for injection patterns, block on medium/high)
  --> structurer.py (text-only input, no image access)
  --> output .md
```

---

## Key Commands

```bash
# Single image
python convert.py image.png

# Folder batch
python convert.py /path/to/folder/ --output-dir ./docs/

# Dry run
python convert.py /path/to/folder/ --dry-run --verbose
```

## Testing

### Requirements

- **Every function must have tests.** All public functions in `src/` and `convert.py` must have corresponding unit tests. No function should exist without test coverage.
- **Every change must include tests.** Any code change — new feature, bug fix, refactor — must be accompanied by new or updated tests that cover the change. Do not merge or commit code without passing tests.
- **Run tests before committing.** Always run `python3 -m pytest tests/ -v` and confirm all tests pass before committing changes.
- **Mock external APIs.** Tests must never make real API calls. Use `unittest.mock.patch` to mock `anthropic.Anthropic` in extractor and structurer tests.
- **Regression tests protect output stability.** The `test_regression.py` suite verifies that output format (frontmatter structure, filename slugification, index generation) remains stable across changes. Add regression test cases when output behavior changes intentionally.

### Test Structure

```
tests/
├── conftest.py           # Shared fixtures (tmp images, mock data, mock clients)
├── test_config.py        # is_supported_image, slugify_filename, get_output_path, DEFAULT_CONFIG
├── test_extractor.py     # extract_from_image (mocked API calls, retries, error handling)
├── test_structurer.py    # structure_extraction, _build_frontmatter, _extract_field
├── test_processor.py     # ProcessingResult, process_image (pipeline orchestration)
├── test_batch.py         # find_images, process_batch, _write_index
├── test_cli.py           # CLI entry point (click runner, flag passing, exit codes)
└── test_regression.py    # End-to-end pipeline, output format stability, slug stability
```

### Running Tests

```bash
# All tests
python3 -m pytest tests/ -v

# Single module
python3 -m pytest tests/test_config.py -v

# Single test
python3 -m pytest tests/test_config.py::TestSlugifyFilename::test_basic_slugify -v
```

---

## Dependencies
- anthropic >= 0.40.0
- click >= 8.0
- Pillow >= 10.0
- pytest >= 7.0
- Python 3.9+
