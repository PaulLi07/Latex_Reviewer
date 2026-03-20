"""
LaTeX 文档解析器

解析 LaTeX 文档，提取章节、方程、表格等结构
"""
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple


@dataclass
class Section:
    """文档章节"""
    title: str
    level: int  # 0=section, 1=subsection, 2=subsubsection
    line_number: int
    number: str = ""  # 章节编号，如 "1", "1.1", "1.2"
    content: str = ""
    subsections: List['Section'] = field(default_factory=list)


@dataclass
class Equation:
    """方程"""
    content: str
    line_number: int
    environment: str  # equation, align, eqnarray, etc.


@dataclass
class Table:
    """表格"""
    content: str
    line_number: int
    caption: Optional[str] = None


@dataclass
class DocumentStructure:
    """文档结构"""
    sections: List[Section] = field(default_factory=list)
    equations: List[Equation] = field(default_factory=list)
    tables: List[Table] = field(default_factory=list)
    abstract: Optional[str] = None
    acknowledgments: Optional[str] = None
    title: Optional[str] = None
    authors: Optional[str] = None

    def get_sections_for_analysis(self) -> List[Dict]:
        """
        获取用于分析的章节列表
        返回格式: [{"title": "...", "content": "...", "line": ..., "number": ...}, ...]
        """
        result = []

        def traverse_sections(sections: List[Section], prefix: str = ""):
            for section in sections:
                # 构建完整的章节标题
                full_title = f"{prefix}{section.title}" if prefix else section.title

                # 如果章节有内容，添加到结果中
                if section.content.strip():
                    result.append({
                        "title": full_title,
                        "content": section.content,
                        "line": section.line_number,
                        "number": section.number  # 添加编号
                    })

                # 递归处理子章节
                if section.subsections:
                    new_prefix = f"{full_title} > "
                    traverse_sections(section.subsections, new_prefix)

        traverse_sections(self.sections)

        # 如果没有章节但有内容，返回整个文档
        if not result and self.abstract:
            result.append({
                "title": "Abstract",
                "content": self.abstract,
                "line": 0,
                "number": ""  # Abstract 没有编号
            })

        return result


class TeXParser:
    """LaTeX 文档解析器"""

    def __init__(self, tex_file: Path):
        self.tex_file = tex_file
        self.structure = DocumentStructure()

    def parse(self) -> DocumentStructure:
        """解析 LaTeX 文档"""
        with open(self.tex_file, 'r', encoding='utf-8') as f:
            content = f.read()

        return self._parse_content(content)

    def _parse_content(self, content: str) -> DocumentStructure:
        """解析文档内容"""
        self._extract_abstract(content)
        self._extract_title_and_authors(content)
        self._extract_sections(content)
        self._extract_equations(content)
        self._extract_tables(content)
        self._extract_acknowledgments(content)

        # 为章节分配编号
        self._assign_section_numbers(self.structure.sections)

        return self.structure

    def _assign_section_numbers(self, sections: List[Section], parent_number: str = "") -> None:
        """
        为章节分配编号

        Args:
            sections: 章节列表
            parent_number: 父级编号（用于 subsection）
        """
        section_counter = 0
        for section in sections:
            section_counter += 1
            if section.level == 0:  # section
                section.number = str(section_counter)
            elif section.level == 1:  # subsection
                section.number = f"{parent_number}.{section_counter}"
            elif section.level == 2:  # subsubsection
                section.number = f"{parent_number}.{section_counter}"

            # 递归处理子章节
            if section.subsections:
                self._assign_section_numbers(section.subsections, section.number)

    def _extract_abstract(self, content: str) -> None:
        """提取摘要"""
        # 匹配 \begin{abstract} ... \end{abstract}
        pattern = r'\\begin\{abstract\}(.*?)\\end\{abstract\}'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            self.structure.abstract = match.group(1).strip()

    def _extract_title_and_authors(self, content: str) -> None:
        """提取标题和作者"""
        # 提取标题
        title_match = re.search(r'\\title\{([^}]+)\}', content)
        if title_match:
            self.structure.title = title_match.group(1).strip()

        # 提取作者
        author_match = re.search(r'\\author\{([^}]+)\}', content, re.DOTALL)
        if author_match:
            self.structure.authors = author_match.group(1).strip()

    def _extract_sections(self, content: str) -> None:
        """提取章节结构"""
        lines = content.split('\n')
        current_sections: List[Section] = []  # 嵌套层级栈
        current_content: List[str] = []
        current_line_number = 0

        # 章节命令模式
        section_patterns = [
            (r'\\section\*?\{([^}]+)\}', 0),
            (r'\\subsection\*?\{([^}]+)\}', 1),
            (r'\\subsubsection\*?\{([^}]+)\}', 2),
        ]

        for i, line in enumerate(lines):
            line_number = i + 1
            matched = False

            # 检查是否是章节命令
            for pattern, level in section_patterns:
                match = re.search(pattern, line)
                if match:
                    matched = True

                    # 保存上一个章节的内容
                    if current_sections and current_content:
                        current_sections[-1].content = '\n'.join(current_content).strip()
                        current_content = []

                    title = match.group(1).strip()
                    new_section = Section(
                        title=title,
                        level=level,
                        line_number=line_number
                    )

                    # 调整层级
                    # 移除比当前层级深的章节
                    while current_sections and current_sections[-1].level >= level:
                        current_sections.pop()

                    # 添加到父章节或根
                    if current_sections:
                        current_sections[-1].subsections.append(new_section)
                    else:
                        self.structure.sections.append(new_section)

                    current_sections.append(new_section)
                    break

            if not matched and current_sections:
                # 收集章节内容
                current_content.append(line)

        # 保存最后一个章节的内容
        if current_sections and current_content:
            current_sections[-1].content = '\n'.join(current_content).strip()

    def _extract_equations(self, content: str) -> None:
        """提取方程"""
        # 方程环境列表
        equation_envs = ['equation', 'align', 'eqnarray', 'gather', 'multline']

        for env in equation_envs:
            pattern = r'\\begin\{' + env + r'\}(.*?)\\end\{' + env + r'\}'
            for match in re.finditer(pattern, content, re.DOTALL):
                # 计算行号
                line_number = content[:match.start()].count('\n') + 1
                equation = Equation(
                    content=match.group(1).strip(),
                    line_number=line_number,
                    environment=env
                )
                self.structure.equations.append(equation)

    def _extract_tables(self, content: str) -> None:
        """提取表格"""
        pattern = r'\\begin\{table\}(.*?)\\end\{table\}'
        for match in re.finditer(pattern, content, re.DOTALL):
            table_content = match.group(0)
            line_number = content[:match.start()].count('\n') + 1

            # 提取标题
            caption_match = re.search(r'\\caption\{([^}]+)\}', table_content)
            caption = caption_match.group(1).strip() if caption_match else None

            table = Table(
                content=table_content.strip(),
                line_number=line_number,
                caption=caption
            )
            self.structure.tables.append(table)

    def _extract_acknowledgments(self, content: str) -> None:
        """提取致谢"""
        # 匹配 \section{Acknowledgements} 或 \section*{Acknowledgements}
        patterns = [
            r'\\section\*?\{[Aa]cknowledg?[^\}]*\}(.*?)\\section\{',
            r'\\section\*?\{[Aa]cknowledg?[^\}]*\}(.*?)\\begin\{thebibliography\}',
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                self.structure.acknowledgments = match.group(1).strip()
                break

    def get_section_content_by_title(self, title: str) -> Optional[str]:
        """根据标题获取章节内容"""
        def search_sections(sections: List[Section]) -> Optional[str]:
            for section in sections:
                if title.lower() in section.title.lower():
                    return section.content
                if section.subsections:
                    result = search_sections(section.subsections)
                    if result:
                        return result
            return None

        return search_sections(self.structure.sections)

    def get_full_text(self) -> str:
        """获取文档全文（不含LaTeX命令）"""
        with open(self.tex_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 移除注释
        content = re.sub(r'%.*$', '', content, flags=re.MULTILINE)

        # 移除LaTeX命令（保留文本）
        # 这是一个简单的实现，可以进一步优化
        content = re.sub(r'\\[a-zA-Z]+\{[^}]*\}', '', content)
        content = re.sub(r'\\[a-zA-Z]+', '', content)

        # 清理多余空白
        content = re.sub(r'\s+', ' ', content)

        return content.strip()


def main():
    """测试函数"""
    import sys
    from pathlib import Path

    # 测试解析 draft.tex
    tex_file = Path(__file__).parent.parent.parent / "draft_example" / "draft.tex"
    parser = TeXParser(tex_file)
    structure = parser.parse()

    print(f"标题: {structure.title}")
    print(f"\n章节数量: {len(structure.sections)}")

    for section in structure.sections:
        print(f"\n- {section.title} (行 {section.line_number})")
        print(f"  子章节数量: {len(section.subsections)}")
        if section.content:
            preview = section.content[:100].replace('\n', ' ')
            print(f"  内容预览: {preview}...")

    print(f"\n方程数量: {len(structure.equations)}")
    print(f"表格数量: {len(structure.tables)}")

    # 获取用于分析的章节
    sections_for_analysis = structure.get_sections_for_analysis()
    print(f"\n用于分析的章节数量: {len(sections_for_analysis)}")


if __name__ == "__main__":
    main()
