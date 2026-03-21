"""
Workflow Layer

Orchestrates the document analysis pipeline, separating business logic from CLI interface.
"""
from dataclasses import dataclass
from typing import List
from pathlib import Path


@dataclass
class AnalysisConfig:
    """Configuration for document analysis"""
    draft_file: Path
    comments_file: Path
    output_file: Path
    template_file: Path
    keywords_file: Path
    llm_provider: str
    api_key: str
    model: str
    max_tokens: int
    temperature: float
    request_timeout: int
    max_retries: int
    cache_enabled: bool
    concise_mode: bool
    two_pass_mode: bool


class DocumentAnalyzer:
    """Orchestrates the document analysis workflow"""

    def __init__(self, config: AnalysisConfig):
        self.config = config
        self._llm_client = None
        self._generator = None

    def analyze(self) -> 'AnalysisResult':
        """
        Execute full analysis workflow

        Returns:
            AnalysisResult with review items and summary
        """
        # Step 1: Parse style rules
        rules, rules_text = self._parse_rules()

        # Step 2: Parse LaTeX document
        document = self._parse_document()

        # Step 3: Parse keywords
        keywords_text = self._parse_keywords()

        # Step 4: Create LLM client and analyze
        reviews = self._analyze_document(document, rules_text, keywords_text)

        # Step 5: Generate output
        self._generate_output(reviews)

        return AnalysisResult(
            reviews=reviews,
            summary=self._generate_summary(reviews)
        )

    # Private methods
    def _parse_rules(self):
        """Parse style rules file"""
        from src.parsers.comments_parser import CommentsParser
        parser = CommentsParser(self.config.comments_file)
        rules = parser.parse()
        rules_text = parser.format_rules_for_prompt()
        return rules, rules_text

    def _parse_document(self):
        """Parse LaTeX document"""
        from src.parsers.tex_parser import TeXParser
        parser = TeXParser(self.config.draft_file)
        return parser.parse()

    def _parse_keywords(self):
        """Parse keywords file"""
        from src.parsers.keywords_parser import KeywordsParser
        parser = KeywordsParser(self.config.keywords_file)
        return parser.format_for_prompt()

    def _analyze_document(self, document, rules_text, keywords_text):
        """Analyze document using LLM"""
        from src.llm import create_client

        # Create client on first use
        if self._llm_client is None:
            self._llm_client = create_client(
                provider=self.config.llm_provider,
                api_key=self.config.api_key,
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                request_timeout=self.config.request_timeout,
                max_retries=self.config.max_retries,
                cache_enabled=self.config.cache_enabled,
                concise_mode=self.config.concise_mode
            )

        sections = document.get_sections_for_analysis()

        if self.config.two_pass_mode:
            return self._llm_client.analyze_document_two_pass(
                sections=sections,
                rules_text=rules_text,
                keywords=keywords_text
            )
        else:
            reviews = []
            for section in sections:
                section_reviews = self._llm_client.analyze_section(
                    section_title=section["title"],
                    section_content=section["content"],
                    rules=rules_text
                )
                reviews.extend(section_reviews)
            return reviews

    def _generate_output(self, reviews):
        """Generate LaTeX review file"""
        from src.generators import ReviewGenerator

        if self._generator is None:
            self._generator = ReviewGenerator(self.config.template_file)

        self._generator.generate(
            review_items=reviews,
            output_file=self.config.output_file,
            draft_file=str(self.config.draft_file)
        )

    def _generate_summary(self, reviews):
        """Generate analysis summary"""
        from src.generators import ReviewGenerator
        if self._generator is None:
            self._generator = ReviewGenerator(self.config.template_file)
        return self._generator.generate_summary(reviews)


@dataclass
class AnalysisResult:
    """Result of document analysis"""
    reviews: List
    summary: str
