"""
comments.txt Parser

Parses style rules from comments.txt file
"""
import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class Rule:
    """Style rule"""
    id: str
    category: str
    description: str
    priority: str = "medium"
    examples: List[str] = None

    def __post_init__(self):
        if self.examples is None:
            self.examples = []


class CommentsParser:
    """comments.txt parser"""

    # Main category mapping
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
        """Parse comments.txt file"""
        with open(self.comments_file, 'r', encoding='utf-8') as f:
            content = f.read()

        return self._parse_content(content)

    def _parse_content(self, content: str) -> List[Rule]:
        """Parse file content"""
        lines = content.split('\n')
        rules = []
        current_category = None

        for line in lines:
            line = line.rstrip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Detect category line (e.g., "Language:" or "        1.1.")
            category_match = re.match(r'^([a-zA-Z].+?):$', line)
            if category_match:
                current_category = category_match.group(1)
                continue

            # Detect rule line (e.g., "        1.1.  Use ', respectively.' correctly.")
            rule_match = re.match(r'^\s+(\d+)\.(\d+)\.\s+(.+)$', line)
            if rule_match:
                main_id, sub_id, description = rule_match.groups()
                rule_id = f"{main_id}.{sub_id}"

                # Get category name
                category = self._get_category_name(main_id)

                # Determine priority
                priority = self._determine_priority(description, category)

                rule = Rule(
                    id=rule_id,
                    category=category,
                    description=description,
                    priority=priority
                )
                rules.append(rule)
                continue

            # Detect sub-item (e.g., "(1) Jargon and the Possible replacement")
            subitem_match = re.match(r'^\s+\((\d+)\)\s+(.+)$', line)
            if subitem_match and rules:
                # Add sub-item to current rule's description
                sub_num, sub_desc = subitem_match.groups()
                if rules:
                    rules[-1].description += f" [{sub_num}] {sub_desc}"
                continue

            # Detect example line (e.g., '            "good photon" -> "candidate photon"')
            example_match = re.match(r'^\s+"(.+?)"\s*->\s*"(.+?)"$', line)
            if example_match and rules:
                before, after = example_match.groups()
                rules[-1].examples.append(f"{before} -> {after}")
                continue

        self.rules = rules
        return rules

    def _get_category_name(self, main_id: str) -> str:
        """Get category name by main ID"""
        return self.CATEGORIES.get(main_id, "Other")

    def _determine_priority(self, description: str, category: str) -> str:
        """Determine priority by description"""
        description_lower = description.lower()

        # High priority keywords
        high_priority_keywords = ["do not", "avoid", "must", "required", "incorrect"]
        if any(keyword in description_lower for keyword in high_priority_keywords):
            return "high"

        # Low priority keywords
        low_priority_keywords = ["consider", "may", "optional", "suggest"]
        if any(keyword in description_lower for keyword in low_priority_keywords):
            return "low"

        # Specific categories default to high priority
        if category in ["Language", "Typography"]:
            return "high"

        return "medium"

    def get_rules_by_category(self, category: str) -> List[Rule]:
        """Get rules by category"""
        return [rule for rule in self.rules if rule.category == category]

    def get_all_categories(self) -> List[str]:
        """Get all categories"""
        return list(set(rule.category for rule in self.rules))

    def get_rule_by_id(self, rule_id: str) -> Optional[Rule]:
        """Get rule by ID"""
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None

    def format_rules_for_prompt(self) -> str:
        """Format rules as text suitable for LLM prompt"""
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
    """Test function"""
    import sys
    from pathlib import Path

    # Test parsing comments.txt
    comments_file = Path(__file__).parent.parent.parent / "comments.txt"
    parser = CommentsParser(comments_file)
    rules = parser.parse()

    print(f"Parsed {len(rules)} rules")
    print(f"Categories: {parser.get_all_categories()}")

    # Print first few rules
    for rule in rules[:5]:
        print(f"\n{rule.id}. [{rule.category}] {rule.description}")


if __name__ == "__main__":
    main()
