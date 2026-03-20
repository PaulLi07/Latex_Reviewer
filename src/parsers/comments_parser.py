"""
comments.txt 解析器

解析 comments.txt 文件中的样式规则
"""
import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class Rule:
    """样式规则"""
    id: str
    category: str
    description: str
    priority: str = "medium"
    examples: List[str] = None

    def __post_init__(self):
        if self.examples is None:
            self.examples = []


class CommentsParser:
    """comments.txt 解析器"""

    # 主类别映射
    CATEGORIES = {
        "1": "Language",
        "2": "Title and Section Titles",
        "3": "Typography",
        "4": "Numbers",
        "5": "Abbreviations",
        "6": "Equations",
        "7": "Tables",
        "9": "References",
        "10": "Abstract",
        "11": "Miscellaneous"
    }

    def __init__(self, comments_file: Path):
        self.comments_file = comments_file
        self.rules: List[Rule] = []

    def parse(self) -> List[Rule]:
        """解析 comments.txt 文件"""
        with open(self.comments_file, 'r', encoding='utf-8') as f:
            content = f.read()

        return self._parse_content(content)

    def _parse_content(self, content: str) -> List[Rule]:
        """解析文件内容"""
        lines = content.split('\n')
        rules = []
        current_category = None

        for line in lines:
            line = line.rstrip()

            # 跳过空行和注释
            if not line or line.startswith('#'):
                continue

            # 检测类别行 (例如: "Language:" 或 "        1.1.")
            category_match = re.match(r'^([a-zA-Z].+?):$', line)
            if category_match:
                current_category = category_match.group(1)
                continue

            # 检测规则行 (例如: "        1.1.  Use ', respectively.' correctly.")
            rule_match = re.match(r'^\s+(\d+)\.(\d+)\.\s+(.+)$', line)
            if rule_match:
                main_id, sub_id, description = rule_match.groups()
                rule_id = f"{main_id}.{sub_id}"

                # 获取类别名称
                category = self._get_category_name(main_id)

                # 确定优先级
                priority = self._determine_priority(description, category)

                rule = Rule(
                    id=rule_id,
                    category=category,
                    description=description,
                    priority=priority
                )
                rules.append(rule)
                continue

            # 检测子项目 (例如: "(1) Jargon and the Possible replacement")
            subitem_match = re.match(r'^\s+\((\d+)\)\s+(.+)$', line)
            if subitem_match and rules:
                # 将子项目添加到当前规则的描述中
                sub_num, sub_desc = subitem_match.groups()
                if rules:
                    rules[-1].description += f" [{sub_num}] {sub_desc}"
                continue

            # 检测示例行 (例如: "            "good photon" -> "candidate photon"")
            example_match = re.match(r'^\s+"(.+?)"\s*->\s*"(.+?)"$', line)
            if example_match and rules:
                before, after = example_match.groups()
                rules[-1].examples.append(f"{before} -> {after}")
                continue

        self.rules = rules
        return rules

    def _get_category_name(self, main_id: str) -> str:
        """根据主ID获取类别名称"""
        return self.CATEGORIES.get(main_id, "Other")

    def _determine_priority(self, description: str, category: str) -> str:
        """根据描述确定优先级"""
        description_lower = description.lower()

        # 高优先级关键词
        high_priority_keywords = ["do not", "avoid", "must", "required", "incorrect"]
        if any(keyword in description_lower for keyword in high_priority_keywords):
            return "high"

        # 低优先级关键词
        low_priority_keywords = ["consider", "may", "optional", "suggest"]
        if any(keyword in description_lower for keyword in low_priority_keywords):
            return "low"

        # 特定类别默认高优先级
        if category in ["Language", "Typography"]:
            return "high"

        return "medium"

    def get_rules_by_category(self, category: str) -> List[Rule]:
        """按类别获取规则"""
        return [rule for rule in self.rules if rule.category == category]

    def get_all_categories(self) -> List[str]:
        """获取所有类别"""
        return list(set(rule.category for rule in self.rules))

    def get_rule_by_id(self, rule_id: str) -> Optional[Rule]:
        """根据ID获取规则"""
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None

    def format_rules_for_prompt(self) -> str:
        """将规则格式化为适合 LLM prompt 的文本"""
        categories = self.get_all_categories()
        formatted_rules = []

        for category in sorted(categories):
            category_rules = self.get_rules_by_category(category)
            formatted_rules.append(f"\n## {category}\n")
            for rule in category_rules:
                formatted_rules.append(f"{rule.id}. {rule.description}")
                if rule.examples:
                    for example in rule.examples:
                        formatted_rules.append(f"   Example: {example}")
            formatted_rules.append("")

        return "\n".join(formatted_rules)


def main():
    """测试函数"""
    import sys
    from pathlib import Path

    # 测试解析 comments.txt
    comments_file = Path(__file__).parent.parent.parent / "comments.txt"
    parser = CommentsParser(comments_file)
    rules = parser.parse()

    print(f"解析到 {len(rules)} 条规则")
    print(f"类别: {parser.get_all_categories()}")

    # 打印前几条规则
    for rule in rules[:5]:
        print(f"\n{rule.id}. [{rule.category}] {rule.description}")


if __name__ == "__main__":
    main()
