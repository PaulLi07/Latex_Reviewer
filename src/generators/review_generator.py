"""
Review Generator

Generates LaTeX format review.tex file from review results
"""
import re
from pathlib import Path
from typing import List
from ..llm.base_client import ReviewItem


class ReviewGenerator:
    """Review generator"""

    # LaTeX special character escape mapping (for normal text fields)
    # Note: backslash \ is handled separately in _escape_latex() method
    # Core 10 special characters + defensive escape characters
    LATEX_ESCAPE_MAP = {
        # Core LaTeX special characters (must escape)
        '&': r'\&',                    # Table/alignment separator
        '%': r'\%',                    # Comment
        '#': r'\#',                    # Parameter
        '_': r'\_',                    # Subscript
        '{': r'\{',                    # Left brace
        '}': r'\}',                    # Right brace
        '^': r'\^{}',                  # Superscript
        '~': r'\textasciitilde{}',     # Non-breaking space
        '$': r'\$',                    # Dollar sign
        # Defensive escaping (some packages may have special meaning)
        '"': r'\textquotedbl{}',       # Double quote
        '|': r'\textbar{}',            # Vertical bar
        '<': r'\textless{}',           # Less than
        '>': r'\textgreater{}',        # Greater than
    }

    def __init__(self, template_file: Path):
        self.template_file = template_file
        self.template_content = self._load_template()

    def _load_template(self) -> str:
        """Load template file"""
        with open(self.template_file, 'r', encoding='utf-8') as f:
            return f.read()

    def _escape_latex(self, text: str) -> str:
        """
        Comprehensively escape LaTeX special characters for normal text fields

        LaTeX core 10 special characters (all must be escaped):
        - \\ (backslash): Command start
        - { }: Grouping and parameters
        - $: Math mode
        - &: Table/alignment separator
        - #: Parameter
        - _: Subscript
        - ^: Superscript
        - ~: Non-breaking space
        - %: Comment

        Additional defensive escaping (some packages may have special meaning):
        - " (double quote): Some packages like csquotes
        - | (vertical bar): Separator in some packages
        - < > (angle brackets): Redefined in some packages

        Strategy:
        1. Protect paired math mode $...$ (use placeholders without special characters)
        2. Escape all backslashes (automatically handles any LaTeX commands)
        3. Escape all core special characters (skip characters in placeholders)
        4. Defensively escape additional characters (skip characters in placeholders)
        5. Restore math mode

        This method is used to escape category, rule_id, severity, comment fields.
        context and suggested_revision are placed in lstlisting and don't need escaping.

        Args:
            text: Original text

        Returns:
            Escaped text, safe to use in LaTeX normal text
        """
        result = text

        # Step 1: Protect paired math mode $...$
        # Use non-greedy matching, supports multiple $x$ and $y$ appearing simultaneously
        # Placeholders use @@@MATH0@@@ format to avoid conflict with escaped characters
        math_pattern = re.compile(r'\$[^$]+\$')

        # Collect all math expressions and replace with placeholders
        math_matches = list(math_pattern.finditer(result))
        placeholder_to_content = {}

        # Replace from back to front (avoid position offset)
        for i, match in enumerate(reversed(math_matches)):
            placeholder = f'@@@MATH{len(math_matches) - 1 - i}@@@'
            placeholder_to_content[placeholder] = match.group()
            result = result[:match.start()] + placeholder + result[match.end():]

        # Step 2: Escape backslashes (must be first, handles all LaTeX commands)
        # Skip @ characters in placeholders
        # \\ -> \\textbackslash{}
        result = result.replace('\\', r'\textbackslash{}')

        # Step 3: Escape LaTeX core 10 special characters (except already processed \\)
        # For characters like < >, need to skip characters in placeholders
        # Split out placeholders first, process separately
        parts = result.split('@@@')
        escaped_parts = []
        for i, part in enumerate(parts):
            # Even indices are content between placeholders, odd indices are placeholder themselves
            if i % 2 == 1:  # This is placeholder content (MATH0, MATH1, etc.)
                escaped_parts.append('@@@' + part + '@@@')
            else:  # This is normal text, needs escaping
                for char, escaped in self.LATEX_ESCAPE_MAP.items():
                    part = part.replace(char, escaped)
                escaped_parts.append(part)

        result = ''.join(escaped_parts)

        # Step 4: Restore math mode content
        for placeholder, math_content in placeholder_to_content.items():
            result = result.replace(placeholder, math_content)

        return result

    def _format_location(self, item: ReviewItem) -> str:
        """
        Format location information as friendly English description

        Args:
            item: Review item

        Returns:
            Formatted location string, e.g., "1.3, toward the back"
        """
        location = item.location

        # Location description mapping (Chinese-English correspondence)
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

        # Extract section number and location description
        # location format may be: "1.2 Section Title, beginning" or "Section Title, end"
        parts = location.split(",", 1)
        section_part = parts[0].strip()
        position_part = parts[1].strip() if len(parts) > 1 else ""

        # Check if already has number (determined by presence of digits)
        has_number = any(c.isdigit() for c in section_part.split()[0])

        # Format location description
        formatted_position = position_part.lower()
        for key, value in position_mapping.items():
            if key in formatted_position:
                formatted_position = value
                break

        # If already has number, extract and use
        if has_number:
            # Extract number part (e.g., "1.2" or "1" in "1 Introduction")
            number_match = re.match(r'([\d.]+)', section_part)
            if number_match:
                section_num = number_match.group(1)
                return f"{section_num}, {formatted_position}"
            # If no number found but has numbering, use directly
            return f"{section_part}, {formatted_position}"

        # No number case
        if formatted_position:
            return formatted_position
        return location

    def _format_severity(self, severity: str) -> str:
        """
        Add color to severity

        Args:
            severity: Severity level (low, medium, high)

        Returns:
            LaTeX code with color
        """
        severity_colors = {
            "low": r"low",                           # Black
            "medium": r"\textcolor{blue}{medium}",  # Blue
            "high": r"\textcolor{red}{high}",       # Red
        }
        return severity_colors.get(severity.lower(), severity)

    def _format_review_entry(self, item: ReviewItem) -> str:
        """
        Format single review entry (using lstlisting environment)

        Args:
            item: Review item

        Returns:
            LaTeX format review entry
        """
        # Escape special characters in category and rule ID
        category = self._escape_latex(item.category)
        rule_id = self._escape_latex(item.rule_id)

        # Add color to severity (no need to escape, already LaTeX code)
        severity = self._format_severity(item.severity)

        # Escape comment text
        comment = self._escape_latex(item.comment)

        # Format and escape location information
        location_raw = self._format_location(item)
        location_text = self._escape_latex(location_raw)

        # context and suggested_revision go in lstlisting environment
        # lstlisting doesn't need escaping, but needs to preserve indentation
        context_lines = item.context.strip().split('\n')
        context_indented = '\n'.join(['\t' + line for line in context_lines])

        revision_lines = item.suggested_revision.strip().split('\n')
        revision_indented = '\n'.join(['\t' + line for line in revision_lines])

        # Use new template format (includes location line with brackets)
        # Note: {{ and }} are escaped { and }, not placeholders
        entry = r'''\begin{{reviewer}}
\noindent \textbf{{Category: [{cat}] [{rid}] [{sev}]}}

\noindent \textbf{{Location: [{loc}]}}

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
            loc=location_text,  # Location information
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
        Generate review.tex file

        Args:
            review_items: List of review items
            output_file: Output file path
            draft_file: Draft file name (optional)
        """
        # Sort by category and location
        sorted_items = self._sort_reviews(review_items)

        # Generate review entries
        review_content = "\n".join([
            self._format_review_entry(item)
            for item in sorted_items
        ])

        # Insert into template
        output_content = self._insert_into_template(
            review_content,
            draft_file,
            len(review_items)
        )

        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output_content)

    def _sort_reviews(self, items: List[ReviewItem]) -> List[ReviewItem]:
        """
        Sort review items

        Sorting rules:
        1. Sort by category
        2. Within same category sort by severity (high > medium > low)
        3. Same severity sort by location
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
        Insert review content into template

        Args:
            review_content: Review entry content
            draft_file: Draft file name
            count: Number of review items

        Returns:
            Complete LaTeX document
        """
        # Find \\maketitle tag
        maketitle_pos = self.template_content.find('\\maketitle')

        if maketitle_pos == -1:
            # If no \maketitle, find \\begin{document}
            doc_start = self.template_content.find('\\begin{document}')
            if doc_start == -1:
                # If also no document environment, directly append content
                return self.template_content + "\n" + review_content + "\n\\end{document}\n"
            insert_pos = doc_start + len('\\begin{document}')
        else:
            # Insert after \maketitle
            insert_pos = maketitle_pos + len('\\maketitle')

        # Find \\end{document} tag
        doc_end = self.template_content.find('\\end{document}')

        # Build output: from template start to insert position + review content + from insert position after to template end
        before = self.template_content[:insert_pos]
        after = self.template_content[insert_pos:]

        # Remove sample content from template (sample reviewer between \maketitle and \end{document})
        # Find first \begin{reviewer} and last \end{reviewer}
        first_reviewer = after.find('\\begin{reviewer}')
        last_reviewer = after.rfind('\\end{reviewer}')

        if first_reviewer != -1 and last_reviewer != -1:
            # Remove sample reviewer from template, keep other content
            # But if only sample content, directly replace entire section from after \maketitle to before \end{document}
            last_reviewer_end = last_reviewer + len('\\end{reviewer}')
            # Check if only whitespace and \end{document} after \end{reviewer}
            remaining = after[last_reviewer_end:].strip()
            if remaining.startswith('\\end{document}'):
                # Only sample content, directly replace
                after = after[last_reviewer_end:]
            else:
                # Keep other content
                after = after[:first_reviewer] + after[last_reviewer_end:]

        # Remove leading blank lines from after
        after = after.lstrip('\n')

        return before + "\n\n" + review_content + "\n" + after

    def generate_summary(self, items: List[ReviewItem]) -> str:
        """
        Generate review summary

        Args:
            items: List of review items

        Returns:
            Summary text
        """
        if not items:
            return "No issues found. The document complies with all style rules."

        # Statistics by category
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
