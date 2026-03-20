"""
Anthropic Claude LLM 客户端
"""
import json
import logging
import re
from typing import List
from datetime import datetime
from anthropic import Anthropic
from .base_client import BaseLLMClient, ReviewItem, RateLimiter

logger = logging.getLogger(__name__)


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude API 客户端"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = Anthropic(api_key=self.api_key)
        # 添加速率限制器（两次请求之间最少间隔1秒）
        self._rate_limiter = RateLimiter(min_interval=1.0)

    def analyze_section(
        self,
        section_title: str,
        section_content: str,
        rules: str
    ) -> List[ReviewItem]:
        """
        使用 Anthropic Claude API 分析文档章节

        Args:
            section_title: 章节标题
            section_content: 章节内容
            rules: 样式规则（格式化后的文本）

        Returns:
            审查条目列表
        """
        prompt = self._build_prompt(section_title, section_content, rules)

        def make_request():
            # 速率限制
            self._rate_limiter.wait_if_needed()

            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=self._get_system_prompt(),
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                timeout=self.request_timeout
            )
            return response

        response = self._retry_with_backoff(make_request)

        # === 保存响应 ===
        # 动态导入 settings 以避免相对导入问题
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from config.settings import settings

        response_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "provider": "anthropic",
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
                "content": response.content[0].text,
                "usage": {
                    "prompt_tokens": response.usage.input_tokens if response.usage else 0,
                    "completion_tokens": response.usage.output_tokens if response.usage else 0,
                    "total_tokens": (response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0,
                }
            }
        }
        self._save_response(response_data, section_title, "anthropic", settings.cache_dir)
        # ================

        # 解析响应
        content = response.content[0].text
        return self._parse_response(content, section_title, "")

    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
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

        # 简洁模式附加指令
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
        """构建用户提示词"""
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

        # 添加关键词（如果有）
        if keywords:
            prompt += f"\n{keywords}"

        prompt += "\n\nPlease carefully check if this section complies with the above style rules and return the review results in JSON format.\n"
        prompt += "All comments must be in ENGLISH."

        return prompt

    def _parse_response(self, response_content: str, section_title: str, section_number: str = "") -> List[ReviewItem]:
        """解析 LLM 响应"""
        try:
            # 尝试提取 JSON（处理可能的前后文本）
            json_start = response_content.find('{')
            json_end = response_content.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_content[json_start:json_end]
                data = json.loads(json_str)

                violations = data.get("violations", [])
                review_items = []

                for v in violations:
                    # 构建完整的位置信息
                    llm_location = v.get('location', '')

                    # 如果有章节编号，格式为 "编号 标题, 位置"
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
                logger.warning(f"无法在响应中找到有效的JSON: {response_content[:200]}")
                return []

        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            logger.debug(f"响应内容: {response_content[:500]}")
            return []
        except Exception as e:
            logger.error(f"解析响应时出错: {e}")
            return []

    def scan_section_lightweight(
        self,
        section_title: str,
        section_content: str,
        rules: str,
        keywords: str = ""
    ) -> str:
        """
        轻量级扫描章节（阶段1）

        Args:
            section_title: 章节标题
            section_content: 章节内容
            rules: 样式规则
            keywords: 用户关键词

        Returns:
            扫描摘要（JSON 字符串）
        """
        # 为扫描简化规则（只提供类别名称）
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
            # 速率限制
            self._rate_limiter.wait_if_needed()

            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,  # 短输出
                temperature=0.1,
                system="You are a document scanner. Extract key information briefly and concisely.",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                timeout=self.request_timeout
            )
            return response

        try:
            response = self._retry_with_backoff(make_request)
            content = response.content[0].text

            # 调试输出
            print(f"  Scan response: {len(content)} chars")
            if response.usage:
                print(f"  Tokens: {response.usage.input_tokens + response.usage.output_tokens} (prompt: {response.usage.input_tokens} + completion: {response.usage.output_tokens})")

            return content

        except Exception as e:
            logger.warning(f"扫描章节 {section_title} 失败: {e}")
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
        详细分析章节（阶段2）

        Args:
            section_title: 章节标题
            section_content: 章节内容
            rules: 样式规则
            keywords: 用户关键词
            state_summary: 全局状态摘要（术语、已发现问题）
            previous_summary: 本章节的扫描摘要
            section_number: 章节编号（如 "1", "1.1", "1.2"）

        Returns:
            审查条目列表
        """
        prompt = self._build_detailed_prompt(
            section_title,
            section_content,
            rules,
            keywords,
            state_summary,
            previous_summary
        )

        # 调试输出
        print(f"  Section content length: {len(section_content)}")
        print(f"  State summary length: {len(state_summary)}")
        print(f"  Total prompt length: {len(prompt)}")

        def make_request():
            # 速率限制
            self._rate_limiter.wait_if_needed()

            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=self._get_system_prompt(),
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                timeout=self.request_timeout
            )
            return response

        response = self._retry_with_backoff(make_request)

        # === 保存响应 ===
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from config.settings import settings

        response_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "provider": "anthropic",
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
                "content": response.content[0].text,
                "usage": {
                    "prompt_tokens": response.usage.input_tokens if response.usage else 0,
                    "completion_tokens": response.usage.output_tokens if response.usage else 0,
                    "total_tokens": (response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0,
                }
            }
        }
        self._save_response(response_data, section_title, "anthropic", settings.cache_dir)
        # ================

        content = response.content[0].text

        # Token 使用统计
        if response.usage:
            print(f"  Tokens: {response.usage.input_tokens + response.usage.output_tokens} (prompt: {response.usage.input_tokens} + completion: {response.usage.output_tokens})")

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
        """构建详细分析的 prompt"""
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
        """从完整规则中提取简化的类别列表"""
        # 简化：只保留类别标题和编号
        lines = full_rules.split('\n')
        simplified = []
        current_category = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检测类别标题（例如: "## Language"）
            if line.startswith('##'):
                current_category = line.replace('##', '').strip()
                simplified.append(line)
            # 检测规则（例如: "1.1. Use ..."）
            elif current_category and re.match(r'^\d+\.\d+\.', line):
                simplified.append(f"- {line}")

        return "\n".join(simplified) if simplified else "## Available Style Categories\nSee full rules for details."
