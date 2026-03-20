"""
全局分析状态管理

用于两阶段分析中维护全局信息，确保术语一致性和避免重复建议
"""
from dataclasses import dataclass, field
from typing import Dict, List, Set
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class AnalysisState:
    """全局分析状态

    跟踪整个文档分析过程中的信息：
    - 术语及其使用位置
    - 已发现的问题（用于去重）
    - 各类别的问题统计
    - 各章节的摘要
    """

    # 已发现的术语及其用法
    terminology: Dict[str, List[str]] = field(default_factory=dict)
    # 术语 -> 出现位置列表

    # 已发现的问题摘要（用于去重）
    found_issues: Dict[str, Set[str]] = field(default_factory=dict)
    # (category, rule_id) -> {位置描述}

    # 每个类别的问题统计
    issue_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # 章节级别的摘要
    section_summaries: Dict[str, str] = field(default_factory=dict)
    # section_title -> summary_text

    # 扫描阶段的原始摘要（未解析）
    raw_summaries: Dict[str, str] = field(default_factory=dict)
    # section_title -> raw JSON string

    def add_term(self, term: str, location: str) -> None:
        """添加术语及其位置"""
        if term not in self.terminology:
            self.terminology[term] = []
        self.terminology[term].append(location)
        logger.debug(f"添加术语: {term} @ {location}")

    def add_issue(self, category: str, rule_id: str, location: str) -> None:
        """添加已发现的问题"""
        key = f"{category}_{rule_id}"
        if key not in self.found_issues:
            self.found_issues[key] = set()
        self.found_issues[key].add(location)
        self.issue_counts[category] += 1
        logger.debug(f"添加问题: {category}.{rule_id} @ {location}")

    def is_duplicate_issue(self, category: str, rule_id: str, location: str) -> bool:
        """检查是否重复问题"""
        key = f"{category}_{rule_id}"
        if key in self.found_issues:
            # 检查是否在相同位置附近
            return any(
                self._locations_close(location, existing)
                for existing in self.found_issues[key]
            )
        return False

    def _locations_close(self, loc1: str, loc2: str, threshold: int = 50) -> bool:
        """判断两个位置描述是否接近"""
        # 简化实现：检查字符串相似度
        if loc1 == loc2:
            return True
        if loc2 in loc1 or loc1 in loc2:
            return True
        return False

    def get_summary_for_prompt(self) -> str:
        """生成用于 prompt 的状态摘要"""
        summary_parts = []

        # 术语摘要
        if self.terminology:
            summary_parts.append("## Terminology Found So Far")
            for term, locations in list(self.terminology.items())[:20]:  # 限制数量
                summary_parts.append(f"- {term}: used in {len(locations)} location(s)")
            if len(self.terminology) > 20:
                summary_parts.append(f"- ... and {len(self.terminology) - 20} more terms")

        # 已发现问题摘要
        if self.issue_counts and sum(self.issue_counts.values()) > 0:
            summary_parts.append("\n## Issues Found So Far")
            for category, count in sorted(self.issue_counts.items()):
                if count > 0:
                    summary_parts.append(f"- {category}: {count} issues")

        return "\n".join(summary_parts) if summary_parts else ""

    def get_statistics(self) -> Dict[str, any]:
        """获取统计信息"""
        return {
            "total_terms": len(self.terminology),
            "total_issues": sum(self.issue_counts.values()),
            "categories_with_issues": len([k for k, v in self.issue_counts.items() if v > 0]),
            "sections_scanned": len(self.raw_summaries)
        }
