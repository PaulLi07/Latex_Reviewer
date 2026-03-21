"""
Zhipu ChatGLM Client

Zhipu API is compatible with OpenAI format
"""
import logging
from typing import List, Dict, Any
from openai import OpenAI
from .base_client import BaseLLMClient, ReviewItem, RateLimiter

logger = logging.getLogger(__name__)


class ZhipuClient(BaseLLMClient):
    """Zhipu ChatGLM API client"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Zhipu API is compatible with OpenAI format
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://open.bigmodel.cn/api/paas/v4/"
        )
        # Add rate limiter
        self._rate_limiter = RateLimiter(min_interval=1.0)

    # ========== Abstract Method Implementations ==========

    def _get_provider_name(self) -> str:
        return "zhipu"

    def _make_api_call(self, messages: List[Dict], system_prompt: str, **kwargs) -> Any:
        """Execute Zhipu API call"""
        self._rate_limiter.wait_if_needed()
        return self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": messages[0]["content"]}
            ],
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            temperature=kwargs.get("temperature", self.temperature),
            timeout=self.request_timeout
        )

    def _extract_content(self, response: Any) -> str:
        return response.choices[0].message.content

    def _extract_usage(self, response: Any) -> Dict[str, int]:
        if not response.usage:
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        return {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }

    # ========== Public Methods ==========

    def analyze_section(
        self,
        section_title: str,
        section_content: str,
        rules: str
    ) -> List[ReviewItem]:
        """
        Analyze document section using Zhipu API

        Args:
            section_title: Section title
            section_content: Section content
            rules: Style rules (formatted text)

        Returns:
            List of review items
        """
        prompt = self._build_prompt(section_title, section_content, rules)
        system_prompt = self._get_system_prompt()

        def make_request():
            return self._make_api_call(
                [{"role": "user", "content": prompt}],
                system_prompt
            )

        response = self._retry_with_backoff(make_request)

        # Save response
        self._prepare_and_save_response(
            response,
            section_title,
            prompt,
            section_length=len(section_content)
        )

        # Parse response
        content = self._extract_content(response)
        return self._parse_response(content, section_title, "")

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
        # Simplify rules for scanning (only provide category names)
        simplified_rules = self._get_simplified_rules(rules)

        prompt = f"""Please quickly scan the following LaTeX section and provide a brief summary.

## Section: {section_title}

## Content (first 5000 characters)
```
{section_content[:5000]}
```

{simplified_rules}

{keywords}

Please provide a JSON summary with the following structure:
{{
  "terms": ["term1", "term2", ...],  // Key scientific terms found (max 10)
  "potential_issues": [
    {{"category": "Language", "count": 3}},
    {{"category": "Typography", "count": 5}}
  ]
}}

Keep it brief - this is just a scan, not a detailed review. Focus on identifying patterns, not detailed violations.
"""

        def make_request():
            return self._make_api_call(
                [{"role": "user", "content": prompt}],
                "You are a document scanner. Extract key information briefly and concisely.",
                max_tokens=500,
                temperature=0.1
            )

        try:
            response = self._retry_with_backoff(make_request)
            content = self._extract_content(response)
            usage = self._extract_usage(response)

            # Debug output
            print(f"  Scan response: {len(content)} chars")
            if usage.get("total_tokens", 0) > 0:
                print(f"  Tokens: {usage['total_tokens']} (prompt: {usage['prompt_tokens']} + completion: {usage['completion_tokens']})")

            return content

        except Exception as e:
            logger.warning(f"Section scan failed for {section_title}: {e}")
            return '{"terms": [], "potential_issues": []}'

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
        prompt = self._build_detailed_prompt(
            section_title,
            section_content,
            rules,
            keywords,
            state_summary,
            previous_summary
        )
        system_prompt = self._get_system_prompt()

        # Debug output
        print(f"  Section content length: {len(section_content)}")
        print(f"  State summary length: {len(state_summary)}")
        print(f"  Total prompt length: {len(prompt)}")

        def make_request():
            return self._make_api_call(
                [{"role": "user", "content": prompt}],
                system_prompt
            )

        response = self._retry_with_backoff(make_request)

        # Save response
        self._prepare_and_save_response(
            response,
            section_title,
            prompt,
            phase="detailed_analysis",
            section_length=len(section_content),
            state_summary=state_summary,
            previous_summary=previous_summary
        )

        content = self._extract_content(response)
        usage = self._extract_usage(response)

        # Token usage statistics
        if usage.get("total_tokens", 0) > 0:
            print(f"  Tokens: {usage['total_tokens']} (prompt: {usage['prompt_tokens']} + completion: {usage['completion_tokens']})")

        return self._parse_response(content, section_title, section_number)
