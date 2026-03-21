"""
Keywords Parser

Parses user-defined domain terminology from keywords.txt file
"""
from pathlib import Path
from typing import List
import logging

logger = logging.getLogger(__name__)


class KeywordsParser:
    """Parse keywords.txt file"""

    def __init__(self, keywords_file: Path):
        self.keywords_file = keywords_file

    def parse(self) -> List[str]:
        """Parse keywords file"""
        keywords = []

        if not self.keywords_file.exists():
            logger.debug(f"Keywords file does not exist: {self.keywords_file}")
            return keywords

        try:
            with open(self.keywords_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue

                    keywords.append(line)

            logger.info(f"Parsed {len(keywords)} keywords")
            return keywords

        except Exception as e:
            logger.warning(f"Failed to parse keywords file: {e}")
            return []

    def format_for_prompt(self) -> str:
        """Format keywords as text for prompt"""
        keywords = self.parse()

        if not keywords:
            return ""

        # Format as readable list
        keyword_list = "\n".join(f"- {kw}" for kw in keywords)

        return f"""
## Additional Focus Areas

Please pay special attention to the following keywords and topics:
{keyword_list}

Note: These are the areas the user specifically wants reviewed carefully.
"""

    def get_keywords_summary(self) -> str:
        """Get keywords summary (for debugging)"""
        keywords = self.parse()
        if not keywords:
            return "No keywords defined"

        return f"{len(keywords)} keywords: {', '.join(keywords[:5])}{'...' if len(keywords) > 5 else ''}"
