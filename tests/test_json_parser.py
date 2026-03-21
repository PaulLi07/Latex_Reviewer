"""
Unit tests for JSON parser
"""
import pytest
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm.json_parser import (
    extract_json,
    extract_review_items,
    extract_scan_summary,
    JSONParseError
)


class TestExtractJSON:
    """Tests for extract_json function"""

    def test_clean_json_object(self):
        """Test extracting clean JSON object"""
        content = '{"key": "value"}'
        result = extract_json(content)
        assert result == {"key": "value"}

    def test_json_in_markdown_block(self):
        """Test extracting JSON from markdown code block"""
        content = '''Here's the analysis:

```json
{"violations": []}
```

That's all.'''
        result = extract_json(content)
        assert result == {"violations": []}

    def test_json_with_extra_text(self):
        """Test extracting JSON with extra text before and after"""
        content = '''Some introduction text.

{"key": "value", "nested": {"a": 1}}

Some concluding text.'''
        result = extract_json(content)
        assert result == {"key": "value", "nested": {"a": 1}}

    def test_json_with_nested_braces_in_strings(self):
        """Test JSON with braces inside string values"""
        content = '{"text": "This has {braces} inside", "key": "value"}'
        result = extract_json(content)
        assert result == {"text": "This has {braces} inside", "key": "value"}

    def test_json_array(self):
        """Test extracting JSON array"""
        content = '[{"id": 1}, {"id": 2}]'
        result = extract_json(content, expect_array=True)
        assert result == [{"id": 1}, {"id": 2}]

    def test_require_structure_validation(self):
        """Test required structure validation"""
        content = '{"key": "value"}'
        with pytest.raises(JSONParseError, match="Missing required keys"):
            extract_json(content, require_structure=["violations"])

    def test_require_structure_passes(self):
        """Test required structure validation passes"""
        content = '{"violations": [], "summary": "done"}'
        result = extract_json(content, require_structure=["violations"])
        assert result == {"violations": [], "summary": "done"}

    def test_invalid_json_raises_error(self):
        """Test that invalid JSON raises explicit error"""
        content = '{"key": invalid}'
        with pytest.raises(JSONParseError, match="Invalid JSON"):
            extract_json(content)

    def test_no_json_raises_error(self):
        """Test that missing JSON raises explicit error"""
        content = "This is just plain text with no JSON."
        with pytest.raises(JSONParseError, match="No valid JSON found"):
            extract_json(content)

    def test_deeply_nested_json(self):
        """Test parsing deeply nested JSON structure"""
        content = '{"level1": {"level2": {"level3": {"level4": "deep"}}}}'
        result = extract_json(content)
        assert result == {"level1": {"level2": {"level3": {"level4": "deep"}}}}

    def test_json_with_escaped_quotes(self):
        """Test JSON with escaped quotes in strings"""
        content = r'{"text": "He said \"hello\""}'
        result = extract_json(content)
        assert result == {"text": 'He said "hello"'}


class TestExtractReviewItems:
    """Tests for extract_review_items function"""

    def test_extract_violations(self):
        """Test extracting review items from violations array"""
        content = '''```json
{
    "violations": [
        {
            "rule_id": "1.1",
            "category": "Language",
            "location": "beginning",
            "context": "Bad text",
            "comment": "Fix this",
            "suggested_revision": "Good text",
            "severity": "high"
        }
    ]
}
```'''
        result = extract_review_items(content, section_title="Introduction", section_number="1")
        assert len(result) == 1
        assert result[0]["rule_id"] == "1.1"
        assert result[0]["category"] == "Language"
        assert result[0]["location"] == "1 Introduction, beginning"

    def test_empty_violations(self):
        """Test handling empty violations array"""
        content = '{"violations": []}'
        result = extract_review_items(content)
        assert result == []

    def test_location_formatting_without_section_number(self):
        """Test location formatting without section number"""
        content = '{"violations": [{"location": "middle", "rule_id": "1"}]}'
        result = extract_review_items(content, section_title="Abstract")
        assert result[0]["location"] == "Abstract, middle"


class TestExtractScanSummary:
    """Tests for extract_scan_summary function"""

    def test_extract_terms_and_issues(self):
        """Test extracting terms and potential issues"""
        content = '''```json
{
    "terms": ["latex", "theorem"],
    "potential_issues": [
        {"category": "Typography", "count": 3},
        {"category": "Language", "count": 1}
    ]
}
```'''
        result = extract_scan_summary(content)
        assert result["terms"] == ["latex", "theorem"]
        assert len(result["potential_issues"]) == 2
        assert result["potential_issues"][0]["category"] == "Typography"

    def test_only_terms(self):
        """Test scan summary with only terms (no issues)"""
        content = '{"terms": ["term1", "term2"]}'
        result = extract_scan_summary(content)
        assert result["terms"] == ["term1", "term2"]
        assert result["potential_issues"] == []

    def test_only_issues(self):
        """Test scan summary with only issues (no terms)"""
        content = '{"potential_issues": [{"category": "Language", "count": 2}]}'
        result = extract_scan_summary(content)
        assert result["terms"] == []
        assert len(result["potential_issues"]) == 1

    def test_invalid_structure_raises_error(self):
        """Test that invalid structure raises error"""
        content = '{"random": "data"}'
        with pytest.raises(JSONParseError, match="must contain"):
            extract_scan_summary(content)

    def test_extra_fields_preserved(self):
        """Test that extra fields in the JSON are preserved"""
        content = '{"terms": ["t1"], "potential_issues": [], "metadata": {"version": 1}}'
        result = extract_scan_summary(content)
        assert "metadata" in result
        assert result["metadata"]["version"] == 1


class TestEdgeCases:
    """Tests for edge cases and tricky inputs"""

    def test_multiple_json_objects_returns_first(self):
        """Test that multiple JSON objects returns the first valid one"""
        content = '{"first": true} {"second": false}'
        result = extract_json(content)
        assert result == {"first": True}

    def test_brackets_in_markdown_code_fence(self):
        """Test handling of brackets in markdown without proper JSON block"""
        content = '''Here's some code:
```python
if x > 0 and y < 0:
    print("hello")
```

{"actual": "json"}'''
        result = extract_json(content)
        assert result == {"actual": "json"}

    def test_very_long_content_truncated(self):
        """Test that very long content raises ValueError"""
        content = '{"key": "' + "x" * 200_000 + '"}'
        with pytest.raises(ValueError, match="too large"):
            extract_json(content, max_length=100_000)

    def test_empty_string_raises_error(self):
        """Test that empty string raises error"""
        with pytest.raises(JSONParseError, match="No valid JSON found"):
            extract_json("")
