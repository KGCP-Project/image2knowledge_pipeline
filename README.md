# Image-to-Knowledge Document Converter

A CLI tool that converts text-heavy images — infographics, diagrams, framework charts, slides, screenshots — into structured markdown documents using the Claude Vision API.

## Why

Visual content like infographics and architecture diagrams packs a lot of knowledge into a format that's hard to search, reference, or feed into an LLM. This tool extracts every piece of text and structure from an image and produces a clean markdown document that preserves all the original information in a format that's useful for both humans and AI systems.

## How It Works

The pipeline has two steps:

1. **Extract** — The image is sent to the Claude Vision API, which pulls out all text, labels, relationships, and structural information verbatim.
2. **Structure** — A second API call takes the raw extraction and formats it into well-organized markdown with headings, tables, code blocks, and attribution.

Each image produces one standalone `.md` file. Batch processing generates an index file linking to all converted documents.

## Install

```bash
pip install -r requirements.txt
```

Requires Python 3.9+ and an `ANTHROPIC_API_KEY` environment variable.

## Usage

```bash
# Single image
python convert.py image.png

# Custom output filename
python convert.py image.png -o my-document

# Folder of images
python convert.py /path/to/folder/ --output-dir ./docs/

# Recursive folder scan
python convert.py /path/to/folder/ --recursive --output-dir ./docs/

# Preview what would be processed
python convert.py /path/to/folder/ --dry-run --verbose

# Skip images that already have output files
python convert.py /path/to/folder/ --skip-existing
```

## Options

| Flag | Description |
|------|-------------|
| `-o`, `--output` | Output filename (single image mode only) |
| `--output-dir` | Output directory (default: `./output/`) |
| `--recursive` | Process subfolders when input is a directory |
| `--dry-run` | Show what would be processed without making API calls |
| `--verbose` | Show detailed processing logs |
| `--concurrency N` | Max parallel processing for batch mode (default: 3) |
| `--skip-existing` | Skip images that already have output files |
| `--model` | Claude model to use (default: claude-sonnet-4-20250514) |
| `--no-frontmatter` | Omit YAML frontmatter from output |

## Supported Formats

PNG, JPG, JPEG, GIF, WebP

## Output

Each converted document includes:

- **YAML frontmatter** with source file, content type, title, author, and extraction date
- **Structured markdown** matching the original content type (framework, flowchart, comparison chart, etc.)
- **Quick reference table** summarizing key items when applicable
- **Usage notes** with practical context for applying the content
- **Attribution** crediting the original creator

## Example

Given an infographic titled "The 3 Leadership Levers of AI Transformation", the tool produces a markdown file with the framework's three dimensions broken out into sections, a comparison table, usage notes, and full attribution — all extracted directly from the image with no information invented.

## License

MIT
