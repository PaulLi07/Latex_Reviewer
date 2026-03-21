"""
LaTeX Document Parser

Parses LaTeX documents, extracting sections, equations, tables, and other structures
"""
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple


@dataclass
class Section:
    """Document section"""
    title: str
    level: int  # 0=section, 1=subsection, 2=subsubsection
    line_number: int
    number: str = ""  # Section number, e.g., "1", "1.1", "1.2"
    content: str = ""
    subsections: List['Section'] = field(default_factory=list)


@dataclass
class Equation:
    """Equation"""
    content: str
    line_number: int
    environment: str  # equation, align, eqnarray, etc.


@dataclass
class Table:
    """Table"""
    content: str
    line_number: int
    caption: Optional[str] = None


@dataclass
class DocumentStructure:
    """Document structure"""
    sections: List[Section] = field(default_factory=list)
    equations: List[Equation] = field(default_factory=list)
    tables: List[Table] = field(default_factory=list)
    abstract: Optional[str] = None
    acknowledgments: Optional[str] = None
    title: Optional[str] = None
    authors: Optional[str] = None

    def get_sections_for_analysis(self) -> List[Dict]:
        """
        Get list of sections for analysis
        Returns format: [{"title": "...", "content": "...", "line": ..., "number": ...}, ...]
        """
        result = []

        def traverse_sections(sections: List[Section], prefix: str = ""):
            for section in sections:
                # Build complete section title
                full_title = f"{prefix}{section.title}" if prefix else section.title

                # If section has content, add to result
                if section.content.strip():
                    result.append({
                        "title": full_title,
                        "content": section.content,
                        "line": section.line_number,
                        "number": section.number  # Add number
                    })

                # Recursively process subsections
                if section.subsections:
                    new_prefix = f"{full_title} > "
                    traverse_sections(section.subsections, new_prefix)

        traverse_sections(self.sections)

        # If no sections but has content, return entire document
        if not result and self.abstract:
            result.append({
                "title": "Abstract",
                "content": self.abstract,
                "line": 0,
                "number": ""  # Abstract has no number
            })

        return result


class TeXParser:
    """LaTeX document parser"""

    def __init__(self, tex_file: Path):
        self.tex_file = tex_file
        self.structure = DocumentStructure()

    def parse(self) -> DocumentStructure:
        """Parse LaTeX document"""
        with open(self.tex_file, 'r', encoding='utf-8') as f:
            content = f.read()

        return self._parse_content(content)

    def _parse_content(self, content: str) -> DocumentStructure:
        """Parse document content"""
        self._extract_abstract(content)
        self._extract_title_and_authors(content)
        self._extract_sections(content)
        self._extract_equations(content)
        self._extract_tables(content)
        self._extract_acknowledgments(content)

        # Assign numbers to sections
        self._assign_section_numbers(self.structure.sections)

        return self.structure

    def _assign_section_numbers(self, sections: List[Section], parent_number: str = "") -> None:
        """
        Assign numbers to sections

        Args:
            sections: List of sections
            parent_number: Parent number (used for subsections)
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

            # Recursively process subsections
            if section.subsections:
                self._assign_section_numbers(section.subsections, section.number)

    def _extract_abstract(self, content: str) -> None:
        """Extract abstract"""
        # Match \begin{abstract} ... \end{abstract}
        pattern = r'\\begin\{abstract\}(.*?)\\end\{abstract\}'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            self.structure.abstract = match.group(1).strip()

    def _extract_title_and_authors(self, content: str) -> None:
        """Extract title and authors"""
        # Extract title
        title_match = re.search(r'\\title\{([^}]+)\}', content)
        if title_match:
            self.structure.title = title_match.group(1).strip()

        # Extract authors
        author_match = re.search(r'\\author\{([^}]+)\}', content, re.DOTALL)
        if author_match:
            self.structure.authors = author_match.group(1).strip()

    def _extract_sections(self, content: str) -> None:
        """Extract section structure"""
        lines = content.split('\n')
        current_sections: List[Section] = []  # Nested level stack
        current_content: List[str] = []
        current_line_number = 0

        # Section command patterns
        section_patterns = [
            (r'\\section\*?\{([^}]+)\}', 0),
            (r'\\subsection\*?\{([^}]+)\}', 1),
            (r'\\subsubsection\*?\{([^}]+)\}', 2),
        ]

        for i, line in enumerate(lines):
            line_number = i + 1
            matched = False

            # Check if it's a section command
            for pattern, level in section_patterns:
                match = re.search(pattern, line)
                if match:
                    matched = True

                    # Save previous section's content
                    if current_sections and current_content:
                        current_sections[-1].content = '\n'.join(current_content).strip()
                        current_content = []

                    title = match.group(1).strip()
                    new_section = Section(
                        title=title,
                        level=level,
                        line_number=line_number
                    )

                    # Adjust level
                    # Remove sections deeper than current level
                    while current_sections and current_sections[-1].level >= level:
                        current_sections.pop()

                    # Add to parent section or root
                    if current_sections:
                        current_sections[-1].subsections.append(new_section)
                    else:
                        self.structure.sections.append(new_section)

                    current_sections.append(new_section)
                    break

            if not matched and current_sections:
                # Collect section content
                current_content.append(line)

        # Save last section's content
        if current_sections and current_content:
            current_sections[-1].content = '\n'.join(current_content).strip()

    def _extract_equations(self, content: str) -> None:
        """Extract equations"""
        # Equation environment list
        equation_envs = ['equation', 'align', 'eqnarray', 'gather', 'multline']

        for env in equation_envs:
            pattern = r'\\begin\{' + env + r'\}(.*?)\\end\{' + env + r'\}'
            for match in re.finditer(pattern, content, re.DOTALL):
                # Calculate line number
                line_number = content[:match.start()].count('\n') + 1
                equation = Equation(
                    content=match.group(1).strip(),
                    line_number=line_number,
                    environment=env
                )
                self.structure.equations.append(equation)

    def _extract_tables(self, content: str) -> None:
        """Extract tables"""
        pattern = r'\\begin\{table\}(.*?)\\end\{table\}'
        for match in re.finditer(pattern, content, re.DOTALL):
            table_content = match.group(0)
            line_number = content[:match.start()].count('\n') + 1

            # Extract caption
            caption_match = re.search(r'\\caption\{([^}]+)\}', table_content)
            caption = caption_match.group(1).strip() if caption_match else None

            table = Table(
                content=table_content.strip(),
                line_number=line_number,
                caption=caption
            )
            self.structure.tables.append(table)

    def _extract_acknowledgments(self, content: str) -> None:
        """Extract acknowledgments"""
        # Match \section{Acknowledgements} or \section*{Acknowledgements}
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
        """Get section content by title"""
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
        """Get full document text (without LaTeX commands)"""
        with open(self.tex_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Remove comments
        content = re.sub(r'%.*$', '', content, flags=re.MULTILINE)

        # Remove LaTeX commands (keep text)
        # This is a simple implementation, can be further optimized
        content = re.sub(r'\\[a-zA-Z]+\{[^}]*\}', '', content)
        content = re.sub(r'\\[a-zA-Z]+', '', content)

        # Clean extra whitespace
        content = re.sub(r'\s+', ' ', content)

        return content.strip()


def main():
    """Test function"""
    import sys
    from pathlib import Path

    # Test parsing draft.tex
    tex_file = Path(__file__).parent.parent.parent / "draft_example" / "draft.tex"
    parser = TeXParser(tex_file)
    structure = parser.parse()

    print(f"Title: {structure.title}")
    print(f"\nNumber of sections: {len(structure.sections)}")

    for section in structure.sections:
        print(f"\n- {section.title} (line {section.line_number})")
        print(f"  Subsection count: {len(section.subsections)}")
        if section.content:
            preview = section.content[:100].replace('\n', ' ')
            print(f"  Content preview: {preview}...")

    print(f"\nNumber of equations: {len(structure.equations)}")
    print(f"Number of tables: {len(structure.tables)}")

    # Get sections for analysis
    sections_for_analysis = structure.get_sections_for_analysis()
    print(f"\nNumber of sections for analysis: {len(sections_for_analysis)}")


if __name__ == "__main__":
    main()
