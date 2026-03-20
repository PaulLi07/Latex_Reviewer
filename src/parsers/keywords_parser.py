"""
关键词解析器

解析用户自定义的关键词文件，用于引导AI关注特定领域或术语
"""
from pathlib import Path
from typing import List
import logging

logger = logging.getLogger(__name__)


class KeywordsParser:
    """解析 keywords.txt 文件"""

    def __init__(self, keywords_file: Path):
        self.keywords_file = keywords_file

    def parse(self) -> List[str]:
        """解析关键词文件"""
        keywords = []

        if not self.keywords_file.exists():
            logger.debug(f"关键词文件不存在: {self.keywords_file}")
            return keywords

        try:
            with open(self.keywords_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # 跳过空行和注释
                    if not line or line.startswith('#'):
                        continue

                    keywords.append(line)

            logger.info(f"解析到 {len(keywords)} 个关键词")
            return keywords

        except Exception as e:
            logger.warning(f"解析关键词文件失败: {e}")
            return []

    def format_for_prompt(self) -> str:
        """将关键词格式化为 prompt 文本"""
        keywords = self.parse()

        if not keywords:
            return ""

        # 格式化为可读的列表
        keyword_list = "\n".join(f"- {kw}" for kw in keywords)

        return f"""
## Additional Focus Areas

Please pay special attention to the following keywords and topics:
{keyword_list}

Note: These are the areas the user specifically wants reviewed carefully.
"""

    def get_keywords_summary(self) -> str:
        """获取关键词摘要（用于调试）"""
        keywords = self.parse()
        if not keywords:
            return "No keywords defined"

        return f"{len(keywords)} keywords: {', '.join(keywords[:5])}{'...' if len(keywords) > 5 else ''}"
