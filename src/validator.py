"""Post-extraction validation to detect prompt injection patterns.

Scans extracted text for indicators that the image contained adversarial
content designed to manipulate the LLM during extraction or structuring.
"""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Patterns that indicate prompt injection attempts.
# Each tuple: (pattern_name, regex_pattern, severity)
# Severity: "high" = likely injection, "medium" = suspicious, "low" = worth noting
INJECTION_PATTERNS = [
    # Role/identity manipulation
    ("role_override", r"\b(?:you are|act as|pretend to be|assume the role|your new role)\b", "high"),
    ("identity_reset", r"\b(?:forget (?:your|all|previous)|ignore (?:previous|prior|above|all)|disregard)\b", "high"),
    ("new_instructions", r"\b(?:new instructions|updated instructions|override instructions|instead do)\b", "high"),
    ("system_prompt", r"\b(?:system prompt|system message|system instruction)\b", "high"),

    # Output manipulation
    ("output_override", r"\b(?:output only|respond with|your response (?:should|must|will))\b", "medium"),
    ("format_override", r"\b(?:do not extract|do not include|skip the|instead of extracting)\b", "medium"),
    ("hidden_instruction", r"\b(?:hidden instruction|secret instruction|invisible text)\b", "high"),

    # Data exfiltration attempts
    ("exfil_attempt", r"\b(?:send to|post to|upload to|forward to|webhook|callback)\b", "medium"),
    ("api_key_request", r"\b(?:api[_ ]?key|access[_ ]?token|secret[_ ]?key|password|credential)\b", "medium"),

    # Encoded payloads
    ("base64_payload", r"(?:[A-Za-z0-9+/]{40,}={0,2})", "low"),
    ("hex_payload", r"(?:0x[0-9a-fA-F]{20,}|\\x[0-9a-fA-F]{2}(?:\\x[0-9a-fA-F]{2}){9,})", "medium"),

    # Markdown/code injection
    ("code_execution", r"```(?:python|bash|sh|shell|javascript|js)\s*\n.*(?:exec|eval|import os|subprocess|system\()", "high"),

    # Anthropic/OpenAI specific
    ("anthropic_ref", r"\b(?:anthropic|claude|openai|gpt)\b.*\b(?:instruction|system|prompt|ignore)\b", "high"),
]


@dataclass
class ValidationResult:
    """Result of validating extracted text for injection patterns."""

    clean: bool = True
    findings: list = field(default_factory=list)
    severity: str = "none"  # none, low, medium, high

    @property
    def flagged(self) -> bool:
        """Whether this extraction should be flagged for review."""
        return self.severity in ("medium", "high")


@dataclass
class Finding:
    """A single injection pattern match."""

    pattern_name: str
    severity: str
    matched_text: str
    line_number: int
    context: str  # surrounding text for review


def validate_extraction(text: str) -> ValidationResult:
    """Scan extracted text for prompt injection indicators.

    Args:
        text: The raw extraction output to validate.

    Returns:
        ValidationResult with findings and overall severity.
    """
    result = ValidationResult()

    if not text:
        return result

    lines = text.split("\n")
    max_severity = "none"
    severity_order = {"none": 0, "low": 1, "medium": 2, "high": 3}

    for line_num, line in enumerate(lines, start=1):
        for pattern_name, pattern, severity in INJECTION_PATTERNS:
            matches = re.finditer(pattern, line, re.IGNORECASE)
            for match in matches:
                # Skip if the match is clearly part of legitimate content
                if _is_likely_legitimate(match.group(), line, pattern_name):
                    continue

                finding = Finding(
                    pattern_name=pattern_name,
                    severity=severity,
                    matched_text=match.group(),
                    line_number=line_num,
                    context=line.strip()[:200],
                )
                result.findings.append(finding)

                if severity_order.get(severity, 0) > severity_order.get(max_severity, 0):
                    max_severity = severity

                logger.warning(
                    f"Injection pattern '{pattern_name}' ({severity}) "
                    f"at line {line_num}: {match.group()}"
                )

    result.severity = max_severity
    result.clean = len(result.findings) == 0

    if result.findings:
        logger.warning(
            f"Validation found {len(result.findings)} suspicious patterns "
            f"(max severity: {max_severity})"
        )

    return result


def _is_likely_legitimate(matched_text: str, full_line: str, pattern_name: str) -> bool:
    """Heuristic check to reduce false positives.

    Some patterns match legitimate infographic content. This function
    checks common false positive scenarios.
    """
    line_lower = full_line.lower().strip()

    # API key / credential mentions in security infographics are legitimate content
    if pattern_name == "api_key_request":
        security_context_words = [
            "protect", "secure", "rotate", "manage", "store", "vault",
            "never share", "best practice", "recommendation", "policy",
            "checklist", "compliance", "audit", "risk", "vulnerability",
            "exposure", "leak", "breach",
        ]
        if any(word in line_lower for word in security_context_words):
            return True

    # Base64 patterns in technical content (hashes, encoded examples) are common
    if pattern_name == "base64_payload":
        technical_context = [
            "hash", "sha", "md5", "checksum", "certificate", "encoding",
            "example", "signature", "token format",
        ]
        if any(word in line_lower for word in technical_context):
            return True

    # "Act as" in leadership/management infographics
    if pattern_name == "role_override":
        management_context = [
            "leader", "manager", "team", "mentor", "coach", "role model",
            "servant leader", "facilitator",
        ]
        if any(word in line_lower for word in management_context):
            return True

    # References to Claude/AI in infographics ABOUT those tools
    if pattern_name in ("anthropic_ref", "system_prompt"):
        about_ai_context = [
            "how to use", "learn", "tutorial", "guide", "comparison",
            "feature", "capability", "model", "benchmark", "accuracy",
            "understand context", "uses a", "configure", "setting",
        ]
        if any(word in line_lower for word in about_ai_context):
            return True

    return False


def format_validation_report(result: ValidationResult) -> str:
    """Format a validation result as a human-readable report.

    Args:
        result: The ValidationResult to format.

    Returns:
        Formatted string report.
    """
    if result.clean:
        return "Validation: CLEAN -- no injection patterns detected."

    lines = [
        f"Validation: {result.severity.upper()} -- "
        f"{len(result.findings)} suspicious pattern(s) detected.",
        "",
    ]

    for i, finding in enumerate(result.findings, 1):
        lines.append(f"  {i}. [{finding.severity.upper()}] {finding.pattern_name}")
        lines.append(f"     Line {finding.line_number}: {finding.matched_text}")
        lines.append(f"     Context: {finding.context}")
        lines.append("")

    if result.flagged:
        lines.append("ACTION: This extraction is flagged for manual review before structuring.")

    return "\n".join(lines)
