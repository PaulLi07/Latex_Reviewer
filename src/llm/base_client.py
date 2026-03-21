"""
LLM Client Base Class

Defines common interface for LLM providers
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import time
import logging
import json
import re
from datetime import datetime
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class ReviewItem:
    """Review item"""
    rule_id: str
    category: str
    location: str
    context: str
    comment: str
    suggested_revision: str
    severity: str = "medium"


class RateLimiter:
    """Simple rate limiter"""

    def __init__(self, min_interval: float = 1.0):
        """
        Args:
            min_interval: Minimum interval between requests (seconds)
        """
        self.min_interval = min_interval
        self.last_request_time = 0
        self.lock = Lock()

    def wait_if_needed(self):
        """Wait if necessary to comply with rate limit"""
        with self.lock:
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time

            if time_since_last_request < self.min_interval:
                wait_time = self.min_interval - time_since_last_request
                logger.debug(f"Rate limiting: waiting {wait_time:.2f} seconds")
                time.sleep(wait_time)

            self.last_request_time = time.time()


class BaseLLMClient(ABC):
    """LLM client base class"""

    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int = 4000,
        temperature: float = 0.3,
        max_retries: int = 3,
        request_timeout: int = 60,
        cache_enabled: bool = True,
        concise_mode: bool = True
    ):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_retries = max_retries
        self.request_timeout = request_timeout
        self.cache_enabled = cache_enabled
        self.concise_mode = concise_mode

    @abstractmethod
    def analyze_section(
        self,
        section_title: str,
        section_content: str,
        rules: str
    ) -> List[ReviewItem]:
        """
        Analyze document section

        Args:
            section_title: Section title
            section_content: Section content
            rules: Style rules (formatted text)

        Returns:
            List of review items
        """
        pass

    def _retry_with_backoff(self, func, *args, **kwargs):
        """Retry logic with backoff (enhanced version)"""
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                # Get error type name
                error_type = type(e).__name__
                error_module = type(e).__module__
                full_error_name = f"{error_module}.{error_type}" if error_module != "builtins" else error_type

                if attempt < self.max_retries - 1:
                    # Longer backoff times: 2^(attempt+1) + 1, minimum 2 seconds
                    wait_time = (2 ** (attempt + 1)) + 1
                    logger.warning(f"{full_error_name}: retrying in {wait_time} seconds... (attempt {attempt + 1}/{self.max_retries})")
                    logger.debug(f"Error details: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"{full_error_name}: maximum retries reached ({self.max_retries})")

        raise last_exception

    def _count_tokens_estimate(self, text: str) -> int:
        """
        Estimate token count (rough approximation: 1 token ≈ 4 characters)
        """
        return len(text) // 4

    def _save_response(
        self,
        response_data: Dict[str, Any],
        section_title: str,
        provider: str,
        cache_dir: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Save API response to file

        Args:
            response_data: Complete data including request and response
            section_title: Section title
            provider: LLM provider name
            cache_dir: Cache directory path

        Returns:
            Saved file path, or None if cache is disabled
        """
        if not self.cache_enabled or cache_dir is None:
            return None

        try:
            # Create provider directory
            provider_dir = cache_dir / provider
            provider_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename: timestamp_section_title.json
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = re.sub(r'[^\w\-_]', '_', section_title)[:50]
            filename = f"{timestamp}_{safe_title}.json"
            filepath = provider_dir / filename

            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(response_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Response saved to: {filepath}")
            return filepath

        except Exception as e:
            logger.warning(f"Failed to save response: {e}")
            return None

    @abstractmethod
    def scan_section_lightweight(
        self,
        section_title: str,
        section_content: str,
        rules: str,
        keywords: str = ""
    ) -> str:
        """
        Lightweight scan of section (Phase 1)

        Args:
            section_title: Section title
            section_content: Section content
            rules: Style rules
            keywords: User-defined keywords

        Returns:
            Scan summary (JSON string)
        """
        pass

    @abstractmethod
    def analyze_section_detailed(
        self,
        section_title: str,
        section_content: str,
        rules: str,
        keywords: str = "",
        state_summary: str = "",
        previous_summary: str = "",
        section_number: str = ""
    ) -> List[ReviewItem]:
        """
        Detailed analysis of section (Phase 2)

        Args:
            section_title: Section title
            section_content: Section content
            rules: Style rules
            keywords: User-defined keywords
            state_summary: Global state summary (terms, issues found)
            previous_summary: This section's scan summary
            section_number: Section number (e.g., "1", "1.1", "1.2")

        Returns:
            List of review items
        """
        pass

    def analyze_document_two_pass(
        self,
        sections: List[Dict],
        rules_text: str,
        keywords: str = ""
    ) -> List[ReviewItem]:
        """
        Two-pass document analysis (ensures global consistency)

        Args:
            sections: List of sections
            rules_text: Style rules text
            keywords: User-defined keywords

        Returns:
            List of all review items
        """
        from .analysis_state import AnalysisState

        all_reviews = []

        print("=" * 60)
        print("PHASE 1: Lightweight Scan")
        print("=" * 60)

        # Phase 1: Quick scan
        state = AnalysisState()

        for i, section in enumerate(sections):
            print(f"\n[{i+1}/{len(sections)}] Scanning: {section['title'][:50]}")

            summary = self.scan_section_lightweight(
                section["title"],
                section["content"],
                rules_text,
                keywords
            )

            state.raw_summaries[section["title"]] = summary

            # Parse scan results, update state
            self._update_state_from_scan(state, section["title"], summary)

        # Display statistics
        stats = state.get_statistics()
        print(f"\nScan Complete: {stats['total_terms']} terms, {stats['total_issues']} potential issues")

        print("\n" + "=" * 60)
        print("PHASE 2: Detailed Analysis")
        print("=" * 60)

        # Phase 2: Detailed analysis
        for i, section in enumerate(sections):
            print(f"\n[{i+1}/{len(sections)}] Analyzing: {section['title'][:50]}")

            # Build prompt with global state
            state_summary = state.get_summary_for_prompt()

            # Get current section's summary
            current_summary = state.raw_summaries.get(section["title"], "")

            reviews = self.analyze_section_detailed(
                section["title"],
                section["content"],
                rules_text,
                keywords,
                state_summary,
                current_summary,
                section.get("number", "")
            )

            all_reviews.extend(reviews)
            if reviews:
                # Update state
                for review in reviews:
                    state.add_issue(review.category, review.rule_id, review.location)

            print(f"  Found {len(reviews)} issues")

        print(f"\n{'=' * 60}")
        print(f"Analysis Complete: {len(all_reviews)} total issues")
        print("=" * 60)

        return all_reviews

    def _update_state_from_scan(self, state: 'AnalysisState', section_title: str, summary: str) -> None:
        """Update state from scan summary"""
        from .json_parser import extract_scan_summary, JSONParseError

        try:
            data = extract_scan_summary(summary)

            # Extract terms
            if "terms" in data:
                for term in data["terms"]:
                    state.add_term(term, section_title)

            # Extract potential issues
            if "potential_issues" in data:
                for issue in data["potential_issues"]:
                    category = issue.get("category", "Other")
                    count = issue.get("count", 0)
                    for _ in range(count):
                        # Create a virtual location for statistics
                        state.add_issue(category, "scan", section_title)

        except JSONParseError as e:
            logger.warning(f"Failed to parse scan summary for '{section_title}': {e}")
        except Exception as e:
            logger.debug(f"Unexpected error parsing scan summary: {e}")

    # ========== Shared Methods (Moved from provider classes) ==========

    def _get_system_prompt(self) -> str:
        """Get system prompt"""
        base_prompt = """You are a professional physics paper reviewer specializing in LaTeX formatting and scientific writing standards.

Your task is to:
1. Analyze the provided LaTeX document section
2. Identify violations of style rules
3. Provide specific, actionable feedback
4. Suggest corrections that maintain scientific accuracy

Output format (JSON):
{
  "violations": [
    {
      "rule_id": "Rule number (e.g., 1.1, 3.0)",
      "category": "Category name (e.g., Language, Typography)",
      "location": "Specific location description within the section",
      "context": "Problem text fragment",
      "comment": "Explanation of the issue (IN ENGLISH)",
      "suggested_revision": "Complete corrected text",
      "severity": "Severity level (high, medium, low)"
    }
  ]
}

IMPORTANT:
- Report ONLY actual violations of style rules
- If no issues found, return empty array
- context should include enough context to locate the problem
- suggested_revision should be the complete corrected text
- ALL comments must be in ENGLISH
"""

        # Concise mode additional instructions
        if self.concise_mode:
            base_prompt += """

CONCISE MODE REQUIREMENTS:
- Keep comments brief and to the point (max 2 sentences per comment)
- Focus on the most important issues
- Avoid redundant explanations
- Use clear, direct language
"""

        return base_prompt

    def _build_prompt(
        self,
        section_title: str,
        section_content: str,
        rules: str,
        keywords: str = ""
    ) -> str:
        """Build user prompt"""
        prompt = f"""Please analyze the following physics paper LaTeX section and identify violations of the style rules.

## Section Information
Title: {section_title}

## Section Content
```
{section_content[:8000]}
```

## Style Rules
{rules}
"""

        # Add keywords (if any)
        if keywords:
            prompt += f"\n{keywords}"

        prompt += "\n\nPlease carefully check if this section complies with the above style rules and return the review results in JSON format.\n"
        prompt += "All comments must be in ENGLISH."

        return prompt

    def _build_detailed_prompt(
        self,
        section_title: str,
        section_content: str,
        rules: str,
        keywords: str,
        state_summary: str,
        previous_summary: str
    ) -> str:
        """Build detailed analysis prompt"""
        prompt = f"""Please analyze the following LaTeX section for style violations.

## Section: {section_title}

## Content
```
{section_content[:8000]}
```

{rules}
{keywords}

## Progress Summary (From Other Sections)
{state_summary if state_summary else "(No previous data available)"}

## This Section's Scan Summary
{previous_summary if previous_summary else "(No scan available)"}

IMPORTANT for Consistency:
- Check if issues you find have already been reported in other sections
- Use consistent terminology for similar concepts
- Avoid duplicating issues that follow the same pattern
- Focus on NEW issues unique to this section

Return JSON with violations found in this section.
"""
        return prompt

    def _get_simplified_rules(self, full_rules: str) -> str:
        """Extract simplified category list from full rules"""
        lines = full_rules.split('\n')
        simplified = []
        current_category = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detect category title (e.g., "## Language")
            if line.startswith('##'):
                current_category = line.replace('##', '').strip()
                simplified.append(line)
            # Detect rule (e.g., "1.1. Use ...")
            elif current_category and re.match(r'^\d+\.\d+\.', line):
                simplified.append(f"- {line}")

        return "\n".join(simplified) if simplified else "## Available Style Categories\nSee full rules for details."

    def _parse_response(self, response_content: str, section_title: str, section_number: str = "") -> List[ReviewItem]:
        """Parse LLM response"""
        from .json_parser import extract_review_items, JSONParseError

        try:
            violations = extract_review_items(
                response_content,
                section_title=section_title,
                section_number=section_number
            )

            review_items = []
            for v in violations:
                item = ReviewItem(
                    rule_id=v.get("rule_id", "unknown"),
                    category=v.get("category", "Other"),
                    location=v.get("location", f"{section_title}"),
                    context=v.get("context", ""),
                    comment=v.get("comment", ""),
                    suggested_revision=v.get("suggested_revision", ""),
                    severity=v.get("severity", "medium")
                )
                review_items.append(item)

            return review_items

        except JSONParseError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error parsing response: {e}")
            return []

    def _prepare_and_save_response(
        self,
        response: Any,
        section_title: str,
        prompt: str,
        phase: str = "",
        **extra_metadata
    ) -> None:
        """Prepare and save response data using provider-specific extractors"""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from config.settings import settings

        response_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "provider": self._get_provider_name(),
                "model": self.model,
                "section_title": section_title,
                "section_length": extra_metadata.get("section_length", 0),
                "phase": phase or "analysis"
            },
            "request": {
                "system_prompt": self._get_system_prompt(),
                "user_prompt": prompt,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                **{k: v for k, v in extra_metadata.items() if k not in ["section_length"]}
            },
            "response": {
                "raw": response.model_dump() if hasattr(response, 'model_dump') else str(response),
                "content": self._extract_content(response),
                "usage": self._extract_usage(response)
            }
        }
        self._save_response(response_data, section_title, self._get_provider_name(), settings.cache_dir)

    # ========== Abstract Methods for Provider-Specific Operations ==========

    @abstractmethod
    def _get_provider_name(self) -> str:
        """Return provider name for logging/cache (e.g., 'deepseek', 'openai')"""
        pass

    @abstractmethod
    def _make_api_call(self, messages: List[Dict], system_prompt: str, **kwargs) -> Any:
        """Execute provider-specific API call and return raw response"""
        pass

    @abstractmethod
    def _extract_content(self, response: Any) -> str:
        """Extract text content from provider-specific response"""
        pass

    @abstractmethod
    def _extract_usage(self, response: Any) -> Dict[str, int]:
        """Return dict with 'prompt_tokens', 'completion_tokens', 'total_tokens'"""
        pass
