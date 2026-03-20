"""
Review 生成器

将审查结果生成 LaTeX 格式的 review.tex 文件
"""
import re
from pathlib import Path
from typing import List
from ..llm.base_client import ReviewItem


class ReviewGenerator:
    """Review 生成器"""

    # LaTeX 特殊字符转义映射（用于普通文本字段）
    # 注意：反斜杠 \ 在 _escape_latex() 方法中单独处理
    # 核心 10 个特殊字符 + 防御性转义字符
    LATEX_ESCAPE_MAP = {
        # 核心 LaTeX 特殊字符（必须转义）
        '&': r'\&',                    # 表格/对齐分隔符
        '%': r'\%',                    # 注释
        '#': r'\#',                    # 参数
        '_': r'\_',                    # 下标
        '{': r'\{',                    # 左大括号
        '}': r'\}',                    # 右大括号
        '^': r'\^{}',                  # 上标
        '~': r'\textasciitilde{}',     # 不换行空格
        '$': r'\$',                    # 美元符号
        # 防御性转义（某些包可能有特殊含义）
        '"': r'\textquotedbl{}',       # 双引号
        '|': r'\textbar{}',            # 竖线
        '<': r'\textless{}',           # 小于号
        '>': r'\textgreater{}',        # 大于号
    }

    def __init__(self, template_file: Path):
        self.template_file = template_file
        self.template_content = self._load_template()

    def _load_template(self) -> str:
        """加载模板文件"""
        with open(self.template_file, 'r', encoding='utf-8') as f:
            return f.read()

    def _escape_latex(self, text: str) -> str:
        """
        全面转义 LaTeX 特殊字符，用于普通文本字段

        LaTeX 核心 10 个特殊字符（必须全部转义）：
        - \\ (backslash): 命令开始
        - { }: 分组和参数
        - $: 数学模式
        - &: 表格/对齐分隔符
        - #: 参数
        - _: 下标
        - ^: 上标
        - ~: 不换行空格
        - %: 注释

        额外防御性转义（某些包可能有特殊含义）：
        - " (双引号): 某些包如 csquotes
        - | (竖线): 某些包中的分隔符
        - < > (尖括号): 某些包中重定义

        策略：
        1. 保护配对的数学模式 $...$（使用不包含特殊字符的占位符）
        2. 转义所有反斜杠（自动处理任何 LaTeX 命令）
        3. 转义所有核心特殊字符（跳过占位符中的字符）
        4. 防御性转义额外字符（跳过占位符中的字符）
        5. 恢复数学模式

        此方法用于转义 category, rule_id, severity, comment 等字段。
        context 和 suggested_revision 放在 lstlisting 中，不需要转义。

        Args:
            text: 原始文本

        Returns:
            转义后的文本，可在 LaTeX 普通文本中安全使用
        """
        result = text

        # 第一步：保护配对的数学模式 $...$
        # 使用非贪婪匹配，支持多个 $x$ 和 $y$ 同时出现
        # 占位符使用@@@MATH0@@@格式，避免与被转义的字符冲突
        math_pattern = re.compile(r'\$[^$]+\$')

        # 收集所有数学表达式并替换为占位符
        math_matches = list(math_pattern.finditer(result))
        placeholder_to_content = {}

        # 从后往前替换（避免位置偏移）
        for i, match in enumerate(reversed(math_matches)):
            placeholder = f'@@@MATH{len(math_matches) - 1 - i}@@@'
            placeholder_to_content[placeholder] = match.group()
            result = result[:match.start()] + placeholder + result[match.end():]

        # 第二步：转义反斜杠（必须在最前面，处理所有 LaTeX 命令）
        # 跳过占位符中的 @ 字符
        # \\ -> \\textbackslash{}
        result = result.replace('\\', r'\textbackslash{}')

        # 第三步：转义 LaTeX 核心 10 个特殊字符（除了已处理的 \\）
        # 对于 < > 等字符，需要跳过占位符中的字符
        # 先分割出占位符，分别处理
        parts = result.split('@@@')
        escaped_parts = []
        for i, part in enumerate(parts):
            # 偶数索引是占位符之间的内容，奇数索引是占位符本身
            if i % 2 == 1:  # 这是占位符内容（MATH0, MATH1等）
                escaped_parts.append('@@@' + part + '@@@')
            else:  # 这是普通文本，需要转义
                for char, escaped in self.LATEX_ESCAPE_MAP.items():
                    part = part.replace(char, escaped)
                escaped_parts.append(part)

        result = ''.join(escaped_parts)

        # 第四步：恢复数学模式内容
        for placeholder, math_content in placeholder_to_content.items():
            result = result.replace(placeholder, math_content)

        return result

    def _format_location(self, item: ReviewItem) -> str:
        """
        格式化位置信息为友好的英文描述

        Args:
            item: 审查条目

        Returns:
            格式化后的位置字符串，如 "1.3, toward the back"
        """
        location = item.location

        # 位置描述映射（中英文对照）
        position_mapping = {
            "beginning": "beginning",
            "靠前": "toward the front",
            "start": "beginning",
            "middle": "middle",
            "中间": "middle",
            "end": "toward the back",
            "靠后": "toward the back",
            "toward the end": "toward the back",
        }

        # 提取章节编号和位置描述
        # location 格式可能是: "1.2 Section Title, beginning" 或 "Section Title, end"
        parts = location.split(",", 1)
        section_part = parts[0].strip()
        position_part = parts[1].strip() if len(parts) > 1 else ""

        # 检查是否已有编号（通过是否有数字判断）
        has_number = any(c.isdigit() for c in section_part.split()[0])

        # 格式化位置描述
        formatted_position = position_part.lower()
        for key, value in position_mapping.items():
            if key in formatted_position:
                formatted_position = value
                break

        # 如果已经有编号，提取并使用
        if has_number:
            # 提取编号部分（如 "1.2" 或 "1 Introduction" 中的 "1"）
            number_match = re.match(r'([\d.]+)', section_part)
            if number_match:
                section_num = number_match.group(1)
                return f"{section_num}, {formatted_position}"
            # 如果没找到数字但有编号，直接使用
            return f"{section_part}, {formatted_position}"

        # 没有编号的情况
        if formatted_position:
            return formatted_position
        return location

    def _format_severity(self, severity: str) -> str:
        """
        为严重性添加颜色

        Args:
            severity: 严重性级别 (low, medium, high)

        Returns:
            带颜色的 LaTeX 代码
        """
        severity_colors = {
            "low": r"low",                           # 黑色
            "medium": r"\textcolor{blue}{medium}",  # 蓝色
            "high": r"\textcolor{red}{high}",       # 红色
        }
        return severity_colors.get(severity.lower(), severity)

    def _format_review_entry(self, item: ReviewItem) -> str:
        """
        格式化单个审查条目（使用 lstlisting 环境）

        Args:
            item: 审查条目

        Returns:
            LaTeX 格式的审查条目
        """
        # 转义类别和规则ID中的特殊字符
        category = self._escape_latex(item.category)
        rule_id = self._escape_latex(item.rule_id)

        # 为严重性添加颜色（不需要转义，因为已经是 LaTeX 代码）
        severity = self._format_severity(item.severity)

        # 转义评论文本
        comment = self._escape_latex(item.comment)

        # 格式化位置信息
        location_text = self._format_location(item)

        # context 和 suggested_revision 放在 lstlisting 环境中
        # lstlisting 不需要转义，但需要保留缩进
        context_lines = item.context.strip().split('\n')
        context_indented = '\n'.join(['\t' + line for line in context_lines])

        revision_lines = item.suggested_revision.strip().split('\n')
        revision_indented = '\n'.join(['\t' + line for line in revision_lines])

        # 使用新的模板格式（包含位置行）
        # 注意：{{ 和 }} 是转义的 { 和 }，不是占位符
        entry = r'''\begin{{reviewer}}
\noindent \textbf{{Category: [{cat}] [{rid}] [{sev}]}}

{loc}
\begin{{lstlisting}}[breaklines=true]
{ctx}
\end{{lstlisting}}

\textbf{{Reviewer Comment:}}

{cmt}

\textbf{{Suggested Revision:}}

\begin{{lstlisting}}[breaklines=true]
{rev}
\end{{lstlisting}}

\end{{reviewer}}
'''.format(
            cat=category,
            rid=rule_id,
            sev=severity,
            loc=location_text,  # 位置信息
            ctx=context_indented,
            cmt=comment,
            rev=revision_indented
        )
        return entry

    def generate(
        self,
        review_items: List[ReviewItem],
        output_file: Path,
        draft_file: str = ""
    ) -> None:
        """
        生成 review.tex 文件

        Args:
            review_items: 审查条目列表
            output_file: 输出文件路径
            draft_file: 原稿文件名（可选）
        """
        # 按类别和位置排序
        sorted_items = self._sort_reviews(review_items)

        # 生成审查条目
        review_content = "\n".join([
            self._format_review_entry(item)
            for item in sorted_items
        ])

        # 插入到模板中
        output_content = self._insert_into_template(
            review_content,
            draft_file,
            len(review_items)
        )

        # 写入文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output_content)

    def _sort_reviews(self, items: List[ReviewItem]) -> List[ReviewItem]:
        """
        对审查条目排序

        排序规则：
        1. 按类别排序
        2. 在同一类别内按严重程度排序（high > medium > low）
        3. 相同严重程度按位置排序
        """
        severity_order = {"high": 0, "medium": 1, "low": 2}

        return sorted(
            items,
            key=lambda x: (
                x.category,
                severity_order.get(x.severity, 1),
                x.location
            )
        )

    def _insert_into_template(
        self,
        review_content: str,
        draft_file: str,
        count: int
    ) -> str:
        """
        将审查内容插入到模板中

        Args:
            review_content: 审查条目内容
            draft_file: 原稿文件名
            count: 审查条目数量

        Returns:
            完整的 LaTeX 文档
        """
        # 查找 \\maketitle 标签
        maketitle_pos = self.template_content.find('\\maketitle')

        if maketitle_pos == -1:
            # 如果没有 \maketitle，查找 \\begin{document}
            doc_start = self.template_content.find('\\begin{document}')
            if doc_start == -1:
                # 如果也没有 document 环境，直接追加内容
                return self.template_content + "\n" + review_content + "\n\\end{document}\n"
            insert_pos = doc_start + len('\\begin{document}')
        else:
            # 在 \maketitle 之后插入
            insert_pos = maketitle_pos + len('\\maketitle')

        # 查找 \\end{document} 标签
        doc_end = self.template_content.find('\\end{document}')

        # 构建输出：从模板开始到插入位置 + 审查内容 + 从插入位置之后到模板结束
        before = self.template_content[:insert_pos]
        after = self.template_content[insert_pos:]

        # 移除模板中的示例内容（从 \maketitle 到 \end{document} 之间的示例 reviewer）
        # 查找第一个 \begin{reviewer} 和最后一个 \end{reviewer}
        first_reviewer = after.find('\\begin{reviewer}')
        last_reviewer = after.rfind('\\end{reviewer}')

        if first_reviewer != -1 and last_reviewer != -1:
            # 移除模板中的示例 reviewer，保留其他内容
            # 但如果只有示例内容，就直接替换整个从 \maketitle 后到 \end{document} 前的部分
            last_reviewer_end = last_reviewer + len('\\end{reviewer}')
            # 检查 \end{reviewer} 之后是否只有空白字符和 \end{document}
            remaining = after[last_reviewer_end:].strip()
            if remaining.startswith('\\end{document}'):
                # 只有示例内容，直接替换
                after = after[last_reviewer_end:]
            else:
                # 保留其他内容
                after = after[:first_reviewer] + after[last_reviewer_end:]

        # 移除 after 开头的空白行
        after = after.lstrip('\n')

        return before + "\n\n" + review_content + "\n" + after

    def generate_summary(self, items: List[ReviewItem]) -> str:
        """
        生成审查摘要

        Args:
            items: 审查条目列表

        Returns:
            摘要文本
        """
        if not items:
            return "No issues found. The document complies with all style rules."

        # 按类别统计
        category_count = {}
        severity_count = {"high": 0, "medium": 0, "low": 0}

        for item in items:
            category_count[item.category] = category_count.get(item.category, 0) + 1
            severity_count[item.severity] = severity_count.get(item.severity, 0) + 1

        summary = ["Review Summary:", ""]

        summary.append("Issues by Category:")
        for category, count in sorted(category_count.items()):
            summary.append(f"  - {category}: {count}")

        summary.append("")
        summary.append("Issues by Severity:")
        for severity, count in severity_count.items():
            if count > 0:
                summary.append(f"  - {severity}: {count}")

        return "\n".join(summary)
