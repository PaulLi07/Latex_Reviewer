"""
LLM 客户端基类

定义 LLM 提供商的通用接口
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
    """审查条目"""
    rule_id: str
    category: str
    location: str
    context: str
    comment: str
    suggested_revision: str
    severity: str = "medium"


class RateLimiter:
    """简单的速率限制器"""

    def __init__(self, min_interval: float = 1.0):
        """
        Args:
            min_interval: 两次请求之间的最小间隔（秒）
        """
        self.min_interval = min_interval
        self.last_request_time = 0
        self.lock = Lock()

    def wait_if_needed(self):
        """如果需要，等待以符合速率限制"""
        with self.lock:
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time

            if time_since_last_request < self.min_interval:
                wait_time = self.min_interval - time_since_last_request
                logger.debug(f"速率限制：等待 {wait_time:.2f} 秒")
                time.sleep(wait_time)

            self.last_request_time = time.time()


class BaseLLMClient(ABC):
    """LLM 客户端基类"""

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
        分析文档章节

        Args:
            section_title: 章节标题
            section_content: 章节内容
            rules: 样式规则（格式化后的文本）

        Returns:
            审查条目列表
        """
        pass

    def _retry_with_backoff(self, func, *args, **kwargs):
        """带退避的重试逻辑（增强版）"""
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                # 获取错误类型名称
                error_type = type(e).__name__
                error_module = type(e).__module__
                full_error_name = f"{error_module}.{error_type}" if error_module != "builtins" else error_type

                if attempt < self.max_retries - 1:
                    # 更长的退避时间：2^(attempt+1) + 1，最少2秒
                    wait_time = (2 ** (attempt + 1)) + 1
                    logger.warning(f"{full_error_name}: {wait_time}秒后重试... (尝试 {attempt + 1}/{self.max_retries})")
                    logger.debug(f"错误详情: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"{full_error_name}: 已达最大重试次数 ({self.max_retries})")

        raise last_exception

    def _count_tokens_estimate(self, text: str) -> int:
        """
        估算 token 数量（粗略估计：1 token ≈ 4 字符）
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
        保存 API 响应到文件

        Args:
            response_data: 包含请求和响应的完整数据
            section_title: 章节标题
            provider: LLM 提供商名称
            cache_dir: 缓存目录路径

        Returns:
            保存的文件路径，如果缓存禁用则返回 None
        """
        if not self.cache_enabled or cache_dir is None:
            return None

        try:
            # 创建提供商目录
            provider_dir = cache_dir / provider
            provider_dir.mkdir(parents=True, exist_ok=True)

            # 生成文件名：时间戳_章节标题.json
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = re.sub(r'[^\w\-_]', '_', section_title)[:50]
            filename = f"{timestamp}_{safe_title}.json"
            filepath = provider_dir / filename

            # 保存到文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(response_data, f, ensure_ascii=False, indent=2)

            logger.info(f"响应已保存到: {filepath}")
            return filepath

        except Exception as e:
            logger.warning(f"保存响应失败: {e}")
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
        轻量级扫描章节（阶段1）

        Args:
            section_title: 章节标题
            section_content: 章节内容
            rules: 样式规则
            keywords: 用户关键词

        Returns:
            扫描摘要（JSON 字符串）
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
        pass

    def analyze_document_two_pass(
        self,
        sections: List[Dict],
        rules_text: str,
        keywords: str = ""
    ) -> List[ReviewItem]:
        """
        两阶段文档分析（确保全局一致性）

        Args:
            sections: 章节列表
            rules_text: 样式规则文本
            keywords: 用户关键词

        Returns:
            所有审查条目列表
        """
        from .analysis_state import AnalysisState

        all_reviews = []

        print("=" * 60)
        print("PHASE 1: Lightweight Scan")
        print("=" * 60)

        # 阶段 1：快速扫描
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

            # 解析扫描结果，更新状态
            self._update_state_from_scan(state, section["title"], summary)

        # 显示统计信息
        stats = state.get_statistics()
        print(f"\nScan Complete: {stats['total_terms']} terms, {stats['total_issues']} potential issues")

        print("\n" + "=" * 60)
        print("PHASE 2: Detailed Analysis")
        print("=" * 60)

        # 阶段 2：详细分析
        for i, section in enumerate(sections):
            print(f"\n[{i+1}/{len(sections)}] Analyzing: {section['title'][:50]}")

            # 构建包含全局状态的 prompt
            state_summary = state.get_summary_for_prompt()

            # 获取当前章节的摘要
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
                # 更新状态
                for review in reviews:
                    state.add_issue(review.category, review.rule_id, review.location)

            print(f"  Found {len(reviews)} issues")

        print(f"\n{'=' * 60}")
        print(f"Analysis Complete: {len(all_reviews)} total issues")
        print("=" * 60)

        return all_reviews

    def _update_state_from_scan(self, state: 'AnalysisState', section_title: str, summary: str) -> None:
        """从扫描摘要更新状态"""
        try:
            import json

            # 提取 JSON（处理可能的markdown代码块）
            json_start = summary.find('{')
            json_end = summary.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = summary[json_start:json_end]
                data = json.loads(json_str)

                # 提取术语
                if "terms" in data:
                    for term in data["terms"]:
                        state.add_term(term, section_title)

                # 提取潜在问题
                if "potential_issues" in data:
                    for issue in data["potential_issues"]:
                        category = issue.get("category", "Other")
                        count = issue.get("count", 0)
                        for _ in range(count):
                            # 创建一个虚拟位置用于统计
                            state.add_issue(category, "scan", section_title)

        except (json.JSONDecodeError, KeyError) as e:
            logger.debug(f"解析扫描摘要失败: {e}")
