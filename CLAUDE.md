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
├── CLAUDE.md                    # This file — system prompt and project spec
├── README.md                    # User-facing documentation
├── convert.py                   # Main CLI entry point
├── src/
│   ├── __init__.py
│   ├── extractor.py             # Image → raw text extraction via Claude Vision API
│   ├── structurer.py            # Raw extraction → structured markdown via Claude API
│   ├── processor.py             # Orchestrates single-image pipeline
│   ├── batch.py                 # Folder/batch processing logic
│   ├── templates.py             # Output markdown templates and formatting rules
│   └── config.py                # Configuration and defaults
├── output/                      # Default output directory
├── examples/                    # Example inputs and outputs for reference
│   ├── input/
│   └── output/
└── requirements.txt
```

---

## Processing Pipeline

### Step 1: Image Intake
- Validate file exists and is a supported image format
- For folders: enumerate all image files, optionally recursive
- Generate output filename from input filename (slugified, lowercase, hyphens)

### Step 2: Vision Extraction (extractor.py)
- Send image to Claude Vision API with extraction prompt
- Extract ALL text, relationships, structure, attribution

### Step 3: Structured Formatting (structurer.py)
- Convert raw extraction to clean structured markdown
- Apply appropriate formatting based on content type

### Step 4: Output
- Write markdown with optional YAML frontmatter
- Generate batch index when processing folders

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

## Dependencies
- anthropic >= 0.40.0
- click >= 8.0
- Python 3.9+
