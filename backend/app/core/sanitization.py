"""Input sanitization utilities for preventing prompt injection and validating input."""

import re

# Maximum allowed length for user questions
MAX_QUESTION_LENGTH = 2000

# Patterns that may indicate prompt injection attempts, grouped by category
# Each tuple is (pattern, category)
# Order matters - more specific patterns should come before general ones
SUSPICIOUS_PATTERNS: list[tuple[str, str]] = [
    # Direct prompt manipulation (check first - most specific)
    (r"(?i)\[\s*INST\s*\]", "prompt_format_injection"),
    (r"(?i)<\|im_start\|>", "prompt_format_injection"),
    (r"(?i)<\|system\|>", "prompt_format_injection"),
    # Markdown/formatting injection (check before role play)
    (r"```\s*(system|assistant)", "role_override_attempt"),
    # System/role override attempts
    (r"(?i)\bsystem\s*:\s*", "role_override_attempt"),
    (r"(?i)\bassistant\s*:\s*", "role_override_attempt"),
    (r"(?i)\buser\s*:\s*", "role_override_attempt"),
    # Instruction override attempts
    (
        r"(?i)\bignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?)",
        "instruction_override_attempt",
    ),
    (
        r"(?i)\bdisregard\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?)",
        "instruction_override_attempt",
    ),
    (
        r"(?i)\bforget\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?)",
        "instruction_override_attempt",
    ),
    # New instruction injection
    (r"(?i)\bnew\s+instructions?\s*:", "instruction_override_attempt"),
    (r"(?i)\bupdated\s+instructions?\s*:", "instruction_override_attempt"),
    (r"(?i)\boverride\s+instructions?\s*:", "instruction_override_attempt"),
    # Role play attempts (check last - most general)
    (r"(?i)\byou\s+are\s+now\s+", "role_play_attempt"),
    (r"(?i)\bpretend\s+(to\s+be|you\s+are)\s+", "role_play_attempt"),
]


def sanitize_input(text: str) -> str:
    """Sanitize user input by removing control characters and normalizing whitespace.

    Args:
        text: Raw user input text

    Returns:
        Sanitized text with control characters removed and whitespace normalized
    """
    if not text:
        return ""

    # Remove ASCII control characters (except newline, tab, carriage return)
    # \x00-\x08: NULL to BACKSPACE
    # \x0b: Vertical tab
    # \x0c: Form feed
    # \x0e-\x1f: Shift out to Unit separator
    # \x7f: DEL
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Normalize whitespace: replace multiple spaces/tabs with single space
    # But preserve intentional newlines (just normalize them)
    lines = text.split("\n")
    normalized_lines = [" ".join(line.split()) for line in lines]
    text = "\n".join(normalized_lines)

    # Remove leading/trailing whitespace
    return text.strip()


def check_suspicious_content(text: str) -> tuple[bool, str | None]:
    """Check if text contains suspicious patterns that may indicate prompt injection.

    This function checks for common prompt injection patterns. When suspicious
    content is detected, the request should be blocked and an error returned.

    Args:
        text: User input text to check

    Returns:
        Tuple of (is_suspicious, category)
        - is_suspicious: True if suspicious pattern detected
        - category: Category of the detected pattern, or None
    """
    if not text:
        return False, None

    for pattern, category in SUSPICIOUS_PATTERNS:
        if re.search(pattern, text):
            return True, category

    return False, None
