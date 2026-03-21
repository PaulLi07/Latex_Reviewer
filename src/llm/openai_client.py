"""
OpenAI LLM Client
"""
import json
import logging
import re
from typing import List
from datetime import datetime
from openai import OpenAI
from .base_client import BaseLLMClient, ReviewItem, RateLimiter

logger = logging.getLogger(__name__)


class OpenAIClient(BaseLLMClient):
    """OpenAI API client"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = OpenAI(api_key=self.api_key)
        # Add rate limiter (minimum interval of 1 second between requests)
        self._rate_limiter = RateLimiter(min_interval=1.0)

    def analyze_section(
        self,
        section_title: str,
        section_content: str,
        rules: str
    ) -> List[ReviewItem]:
        """
        Analyze document section using OpenAI API

        Args:
            section_title: Section title
            section_content: Section content
            rules: Style rules (formatted text)

        Returns:
            List of review items
        """
        prompt = self._build_prompt(section_title, section_content, rules)

        def make_request():
            # Rate limiting
            self._rate_limiter.wait_if_needed()

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                timeout=self.request_timeout
            )
            return response

        response = self._retry_with_backoff(make_request)

        # === Save response ===
        # Dynamically import settings to avoid relative import issues
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from config.settings import settings

        response_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "provider": "openai",
                "model": self.model,
                "section_title": section_title,
                "section_length": len(section_content),
            },
            "request": {
                "system_prompt": self._get_system_prompt(),
                "user_prompt": prompt,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            },
            "response": {
                "raw": response.model_dump() if hasattr(response, 'model_dump') else str(response),
                "content": response.choices[0].message.content,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                }
            }
        }
        self._save_response(response_data, section_title, "openai", settings.cache_dir)
        # ================

        # Parse response
        content = response.choices[0].message.content
        return self._parse_response(content, section_title, "")

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

    def _parse_response(self, response_content: str, section_title: str, section_number: str = "") -> List[ReviewItem]:
        """Parse LLM response"""
        try:
            # Try to extract JSON (handle possible surrounding text)
            json_start = response_content.find('{')
            json_end = response_content.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_content[json_start:json_end]
                data = json.loads(json_str)

                violations = data.get("violations", [])
                review_items = []

                for v in violations:
                    # Build complete location information
                    llm_location = v.get('location', '')

                    # If section number exists, format as "number title, location"
                    if section_number:
                        location = f"{section_number} {section_title}, {llm_location}"
                    else:
                        location = f"{section_title}, {llm_location}"

                    item = ReviewItem(
                        rule_id=v.get("rule_id", "unknown"),
                        category=v.get("category", "Other"),
                        location=location,
                        context=v.get("context", ""),
                        comment=v.get("comment", ""),
                        suggested_revision=v.get("suggested_revision", ""),
                        severity=v.get("severity", "medium")
                    )
                    review_items.append(item)

                return review_items
            else:
                logger.warning(f"Unable to find valid JSON in response: {response_content[:200]}")
                return []

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.debug(f"Response content: {response_content[:500]}")
            return []
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            return []

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
            # Rate limiting
            self._rate_limiter.wait_if_needed()

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a document scanner. Extract key information briefly and concisely."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=500,  # Short output
                temperature=0.1,
                timeout=self.request_timeout
            )
            return response

        try:
            response = self._retry_with_backoff(make_request)
            content = response.choices[0].message.content

            # Debug output
            print(f"  Scan response: {len(content)} chars")
            if response.usage:
                print(f"  Tokens: {response.usage.total_tokens} (prompt: {response.usage.prompt_tokens} + completion: {response.usage.completion_tokens})")

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

        # Debug output
        print(f"  Section content length: {len(section_content)}")
        print(f"  State summary length: {len(state_summary)}")
        print(f"  Total prompt length: {len(prompt)}")

        def make_request():
            # Rate limiting
            self._rate_limiter.wait_if_needed()

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                timeout=self.request_timeout
            )
            return response

        response = self._retry_with_backoff(make_request)

        # === Save response ===
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from config.settings import settings

        response_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "provider": "openai",
                "model": self.model,
                "section_title": section_title,
                "section_length": len(section_content),
                "phase": "detailed_analysis"
            },
            "request": {
                "system_prompt": self._get_system_prompt(),
                "user_prompt": prompt,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "state_summary": state_summary,
                "previous_summary": previous_summary
            },
            "response": {
                "raw": response.model_dump() if hasattr(response, 'model_dump') else str(response),
                "content": response.choices[0].message.content,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                }
            }
        }
        self._save_response(response_data, section_title, "openai", settings.cache_dir)
        # ================

        content = response.choices[0].message.content

        # Token usage statistics
        if response.usage:
            print(f"  Tokens: {response.usage.total_tokens} (prompt: {response.usage.prompt_tokens} + completion: {response.usage.completion_tokens})")

        return self._parse_response(content, section_title, section_number)

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
        # Simplification: only keep category titles and numbers
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
