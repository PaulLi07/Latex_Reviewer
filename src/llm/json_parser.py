"""
Robust JSON Parser for LLM Responses

Handles LLM responses that may contain:
- Markdown code blocks
- Extra text before/after JSON
- Nested objects and arrays
- Mixed content
"""
import json
import re
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class JSONParseError(Exception):
    """Explicit JSON parsing error with context"""

    def __init__(self, message: str, content_preview: str = "", position: int = -1):
        self.message = message
        self.content_preview = content_preview
        self.position = position
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        parts = [f"JSONParseError: {self.message}"]
        if self.position >= 0:
            parts.append(f" at position {self.position}")
        if self.content_preview:
            parts.append(f"\nContent preview: {self.content_preview}")
        return "".join(parts)


def extract_json(
    content: str,
    *,
    expect_array: bool = False,
    require_structure: Optional[List[str]] = None,
    max_length: int = 100_000
) -> Any:
    """
    Extract and parse JSON from LLM response content.

    Handles:
    - Markdown code blocks (```json ... ```)
    - Extra text before/after JSON
    - Both objects and arrays
    - Nested structures

    Args:
        content: Raw LLM response text
        expect_array: True if expecting JSON array, False for object
        require_structure: List of required top-level keys (for objects)
        max_length: Maximum content length to process (safety limit)

    Returns:
        Parsed JSON data (dict or list)

    Raises:
        JSONParseError: If JSON cannot be extracted or is invalid
        ValueError: If content exceeds max_length
    """
    if len(content) > max_length:
        raise ValueError(f"Content too large ({len(content)} > {max_length})")

    # Strategy 1: Try to extract from markdown code blocks first
    json_str = _extract_from_code_blocks(content)
    if json_str:
        return _parse_and_validate(json_str, expect_array, require_structure, content)

    # Strategy 2: Find JSON using bracket counting (more robust than find/rfind)
    json_str = _extract_using_bracket_counting(content, expect_array)
    if json_str:
        return _parse_and_validate(json_str, expect_array, require_structure, content)

    # Strategy 3: Last resort - try to find any valid JSON
    json_str = _find_any_valid_json(content)
    if json_str:
        return _parse_and_validate(json_str, expect_array, require_structure, content)

    # Nothing worked
    raise JSONParseError(
        "No valid JSON found in response",
        content_preview=_get_preview(content)
    )


def _extract_from_code_blocks(content: str) -> Optional[str]:
    """Extract JSON from markdown code blocks (```json ... ```)"""
    # Pattern for ```json ... ``` blocks
    json_block_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
    matches = re.findall(json_block_pattern, content, re.DOTALL | re.IGNORECASE)

    if matches:
        # Return the first valid block
        for match in matches:
            match = match.strip()
            if match and match.startswith(('{', '[')):
                return match

    return None


def _extract_using_bracket_counting(content: str, expect_array: bool) -> Optional[str]:
    """
    Extract JSON by counting brackets to find complete structures.

    This is more robust than find('{')/rfind('}') because:
    - It handles nested structures correctly
    - It doesn't get confused by brackets in strings
    - It finds the FIRST complete JSON structure
    """
    start_char = '[' if expect_array else '{'
    end_char = ']' if expect_array else '}'

    # Find first occurrence of start character
    start_idx = content.find(start_char)
    if start_idx == -1:
        return None

    # Track bracket depth and string context
    depth = 0
    in_string = False
    escape_next = False

    for i in range(start_idx, len(content)):
        char = content[i]

        if escape_next:
            escape_next = False
            continue

        if char == '\\':
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        # Only count brackets when not in a string
        if not in_string:
            if char == start_char:
                depth += 1
            elif char == end_char:
                depth -= 1
                if depth == 0:
                    # Found complete structure
                    json_str = content[start_idx:i + 1]
                    return json_str

    return None


def _find_any_valid_json(content: str) -> Optional[str]:
    """
    Last resort: scan for any valid JSON substring.

    Tries to find a substring that can be parsed as JSON.
    """
    # Remove newlines to make scanning easier
    flattened = content.replace('\n', ' ')

    # Try to find object
    if '{' in flattened:
        for idx in range(flattened.count('{')):
            start = flattened.find('{', idx)
            # Try progressively larger substrings
            for end in range(start + 10, min(len(flattened), start + 5000)):
                if flattened[end] == '}':
                    try:
                        candidate = flattened[start:end + 1]
                        json.loads(candidate)  # Validate
                        return candidate
                    except json.JSONDecodeError:
                        continue

    # Try to find array
    if '[' in flattened:
        for idx in range(flattened.count('[')):
            start = flattened.find('[', idx)
            for end in range(start + 10, min(len(flattened), start + 5000)):
                if flattened[end] == ']':
                    try:
                        candidate = flattened[start:end + 1]
                        json.loads(candidate)  # Validate
                        return candidate
                    except json.JSONDecodeError:
                        continue

    return None


def _parse_and_validate(
    json_str: str,
    expect_array: bool,
    require_structure: Optional[List[str]],
    original_content: str
) -> Any:
    """
    Parse JSON string and validate structure.

    Raises:
        JSONParseError: If parsing or validation fails
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise JSONParseError(
            f"Invalid JSON: {e.msg}",
            content_preview=_get_preview(json_str, 200),
            position=e.pos if hasattr(e, 'pos') else -1
        )

    # Validate type
    if expect_array and not isinstance(data, list):
        raise JSONParseError(
            f"Expected JSON array but got {type(data).__name__}",
            content_preview=_get_preview(json_str)
        )

    if not expect_array and not isinstance(data, dict):
        raise JSONParseError(
            f"Expected JSON object but got {type(data).__name__}",
            content_preview=_get_preview(json_str)
        )

    # Validate required structure
    if require_structure and isinstance(data, dict):
        missing_keys = [k for k in require_structure if k not in data]
        if missing_keys:
            raise JSONParseError(
                f"Missing required keys: {missing_keys}",
                content_preview=_get_preview(json_str)
            )

    return data


def _get_preview(content: str, max_len: int = 200) -> str:
    """Get a preview of content for error messages"""
    if len(content) <= max_len:
        return content
    return content[:max_len] + "..."


def extract_review_items(
    content: str,
    section_title: str = "",
    section_number: str = ""
) -> List[Dict]:
    """
    Extract review items from LLM response.

    Expected JSON structure:
    {
        "violations": [
            {
                "rule_id": "...",
                "category": "...",
                "location": "...",
                "context": "...",
                "comment": "...",
                "suggested_revision": "...",
                "severity": "..."
            }
        ]
    }

    Args:
        content: Raw LLM response
        section_title: Section title (for location formatting)
        section_number: Section number (for location formatting)

    Returns:
        List of review item dictionaries

    Raises:
        JSONParseError: If JSON cannot be extracted or validated
    """
    data = extract_json(
        content,
        expect_array=False,
        require_structure=["violations"]
    )

    violations = data.get("violations", [])

    if not isinstance(violations, list):
        raise JSONParseError(
            f"'violations' must be an array, got {type(violations).__name__}",
            content_preview=_get_preview(str(violations))
        )

    # Add location formatting
    for v in violations:
        if not isinstance(v, dict):
            continue

        llm_location = v.get('location', '')

        # If section number exists, format as "number title, location"
        if section_number:
            v['location'] = f"{section_number} {section_title}, {llm_location}"
        else:
            v['location'] = f"{section_title}, {llm_location}"

    return violations


def extract_scan_summary(content: str) -> Dict:
    """
    Extract scan summary from lightweight scan response.

    Expected JSON structure:
    {
        "terms": ["term1", "term2", ...],
        "potential_issues": [
            {"category": "...", "count": N},
            ...
        ]
    }

    Args:
        content: Raw LLM response

    Returns:
        Dictionary with 'terms' and 'potential_issues' keys

    Raises:
        JSONParseError: If JSON cannot be extracted or validated
    """
    data = extract_json(content, expect_array=False)

    # Ensure we have the expected structure
    if "terms" not in data and "potential_issues" not in data:
        raise JSONParseError(
            "Scan summary must contain 'terms' or 'potential_issues'",
            content_preview=_get_preview(content[:500])
        )

    # Set defaults
    if "terms" not in data:
        data["terms"] = []
    if "potential_issues" not in data:
        data["potential_issues"] = []

    return data
