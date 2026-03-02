---
name: convert-image
description: Convert text-heavy images (infographics, slides, screenshots, diagrams) into structured markdown knowledge documents. Use when the user wants to extract knowledge from an image file and produce a clean .md document.
argument-hint: "[image-path-or-folder] [--output-dir path]"
allowed-tools: Read, Write, Glob, Bash, Agent
---

# Image-to-Knowledge Document Converter

Convert image(s) at `$ARGUMENTS` into structured markdown knowledge documents.

## Instructions

### 1. Determine input type

Parse `$ARGUMENTS` for:
- **Image path**: a single file (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`)
- **Folder path**: a directory containing images (process all supported images in it)
- **`--output-dir <path>`**: optional output directory override (default: same directory as the image, or `./output/` for folders)

If no arguments provided, ask the user for the image path.

### 2. For each image, run the two-step pipeline

#### Step A — Extraction

Read the image file using the Read tool (Claude Code can view images natively). Then extract ALL information from it by analyzing it with these goals:

- **TITLE**: The main title/heading
- **SUBTITLE**: Any subtitle or tagline
- **AUTHOR/SOURCE**: Creator attribution if visible (logos, watermarks, names, URLs)
- **CONTENT TYPE**: Classify as one of: `framework`, `architecture_diagram`, `flowchart`, `reference_list`, `comparison_chart`, `process_diagram`, `infographic`, `checklist`, `matrix`, `screenshot`, `presentation_slide`, `other`
- **SECTIONS**: All distinct sections, groups, or categories with their full content
- **RELATIONSHIPS**: How sections connect (sequential, hierarchy, cycle, parallel)
- **DETAILS**: Every piece of text — miss nothing. Labels, annotations, footnotes, legends, IPs, versions, tool names, bullets
- **VISUAL STRUCTURE**: Layout description (circular cycle, grid, left-to-right flow, layered stack, hub-and-spoke, etc.)

Extract verbatim. Do NOT summarize or editorialize.

#### Step B — Structuring

Transform the extraction into a clean markdown document following these rules:

1. Start with `# [Title]`
2. Include `> [Subtitle or one-sentence summary]`
3. Add `---` after the intro
4. Use appropriate structure based on content type:
   - **Framework/Process**: Numbered sections following original sequence
   - **Architecture**: Layered sections matching diagram layers
   - **Reference list**: Categorized tables
   - **Comparison**: Side-by-side tables
   - **Cycle**: Numbered steps noting the cycle repeats
   - **Checklist**: Checkbox-style or structured lists
   - **Screenshot**: Descriptive sections capturing UI state and all visible text
   - **Presentation slide**: Preserve narrative flow and key points
5. Use tables when the source has grid/matrix layouts or for quick-reference summaries
6. Use code blocks for technical content (IPs, commands, file paths, data flows)
7. Use ASCII diagrams for architectural flows when they add clarity
8. Add a **Quick Reference** summary table when the document has 4+ comparable items
9. Add a **Usage Notes** section at the end with practical context
10. End with italicized attribution: `*Original [type] by [Author/Source]*`

**Quality standards:**
- Every piece of text from the image MUST appear in the output
- Structure should make content MORE accessible than the original image
- Tables must be well-formed
- No information invented — only restructure what was extracted
- Use **bold** for key terms, not decoration

### 3. Add YAML frontmatter

Prepend this frontmatter to each document:

```yaml
---
source_type: image_extraction
source_file: [original-filename.ext]
content_type: [detected type from extraction]
title: "[extracted title]"
author: "[extracted author/source if found]"
extracted_date: [today's date YYYY-MM-DD]
tags: [relevant tags as list]
---
```

### 4. Write the output

- **Filename**: Slugify the input filename — lowercase, hyphens, no extension. Example: `3_horizon_AI_Strat_Framework.jpg` → `3-horizon-ai-strat-framework.md`
- **Location**: Write to `--output-dir` if specified, otherwise:
  - Single image: same directory as the image
  - Folder mode: `./output/` subdirectory
- Report what was created

### 5. Batch mode (folder input)

When processing a folder:
- Find all supported images (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`)
- Process each image through the pipeline
- Use the Agent tool to process multiple images in parallel when there are more than 2
- After all images are processed, generate an `_index.md` file listing all documents with links

### Output example structure

```markdown
---
source_type: image_extraction
source_file: cloud-security-framework.png
content_type: framework
title: "Cloud Security Framework"
author: "NIST"
extracted_date: 2026-03-01
tags: [cloud, security, frameworks, nist]
---

# Cloud Security Framework

> A comprehensive framework for securing cloud infrastructure across all deployment models.

---

## 1. Identify
[Content...]

## 2. Protect
[Content...]

---

## Quick Reference

| Phase | Focus | Key Activities |
|-------|-------|---------------|
| ... | ... | ... |

## Usage Notes
- [Practical application context]

*Original framework by NIST*
```
