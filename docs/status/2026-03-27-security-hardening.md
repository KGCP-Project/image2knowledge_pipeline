# 2026-03-27 -- Security Hardening: Prompt Injection Protection

## What was done

Added a security pipeline to protect against prompt injection via image formatting elements:

### New modules
- **src/sanitize.py** -- Image sanitization that strips all metadata (EXIF, IPTC, XMP, ICC profiles, PNG text chunks, JPEG comments, GIF comment extensions), flattens suspicious alpha channels, and re-encodes from raw pixel data as clean PNG. Original image is preserved; sanitized copy is used in-memory only.
- **src/validator.py** -- Post-extraction validation that scans extracted text for 12 categories of injection patterns (role override, instruction manipulation, system prompt references, encoded payloads, exfiltration attempts). Includes false positive reduction for security infographics, AI tutorials, and leadership content. Medium/high severity findings block processing unless `--force` is used.

### Updated modules
- **src/templates.py** -- Extraction prompt now includes untrusted-input guardrails instructing the model to treat all image content as DATA, not INSTRUCTIONS.
- **src/extractor.py** -- Accepts `sanitized_bytes` kwarg to use clean bytes instead of reading raw file from disk.
- **src/processor.py** -- Full pipeline: sanitize -> extract -> validate -> structure -> write. New parameters: `skip_sanitize`, `force_on_warning`.
- **convert.py** -- New CLI flags: `--no-sanitize`, `--force`.
- **requirements.txt** -- Added Pillow>=10.0 dependency.
- **CLAUDE.md** -- Updated architecture diagram and pipeline documentation.

### New tests
- **tests/test_sanitize.py** -- 16 tests covering metadata stripping, alpha flattening, pixel preservation, in-memory mode, error handling.
- **tests/test_validator.py** -- 16 tests covering injection detection, false positive reduction, severity levels, report formatting.
- **tests/test_processor.py** -- Updated with 7 new tests for security pipeline integration (sanitize failure, validation blocking, force override, sanitized bytes passing).
- **tests/test_regression.py** -- Updated to mock sanitizer for existing regression tests.

## Decisions made
- Sanitization happens in-memory (no temp files) to minimize disk I/O and cleanup concerns
- Original images are never modified -- only the sanitized copy is sent to the API
- Validation blocks on medium/high severity by default; `--force` flag overrides
- Alpha channels with >10 unique values are flagged as suspicious and flattened to RGB
- Used `frombytes()`/`tobytes()` instead of deprecated `getdata()` for Pillow 14 compatibility

## What's left
- PDF file support (tracked in KGCP-Project/image2knowledge_pipeline#1)
- Contrast enhancement pre-scan for detecting near-invisible text
- Color distance filtering for text matching background colors

## Lessons learned
- Tests should be written before implementation (TDD) -- was corrected on this during the session
- Minimal test PNG fixtures from conftest.py are too small for Pillow to open, requiring sanitizer mocking in processor/regression tests
- The `anthropic_ref` injection pattern needed broader false positive filtering for educational content about Claude that mentions "system prompt"

## Test results
162/162 tests passing (was 115 before this session)
