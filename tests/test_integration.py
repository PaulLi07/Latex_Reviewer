"""
Integration tests for LaTeX AI Reviewer

Tests the full workflow with real input files but mocked LLM clients.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.workflow import DocumentAnalyzer, AnalysisConfig, AnalysisResult
from config.settings import settings


class TestDocumentAnalyzerIntegration:
    """Integration tests for DocumentAnalyzer"""

    def test_analyze_workflow_with_mock_llm(self):
        """
        Test the full analysis workflow with mocked LLM client.

        This test verifies:
        - Style rules are parsed correctly from comments.txt
        - LaTeX document is parsed from draft_example/draft.tex
        - Keywords are parsed from keywords.txt
        - Mock LLM responses are handled correctly
        - Output file is generated
        """
        # Mock review items that LLM would return
        # Return just 2 reviews total across all sections
        mock_reviews = [
            Mock(
                rule_id="1.1",
                category="Language",
                location="1 Introduction, beginning",
                context="This is a test context.",
                comment="Test comment.",
                suggested_revision="This is the revision.",
                severity="medium"
            ),
            Mock(
                rule_id="3.0",
                category="Typography",
                location="2 BESIII DETECTOR, middle",
                context="Another test context.",
                comment="Spacing issue found.",
                suggested_revision="Fixed spacing.",
                severity="low"
            )
        ]

        # Create temporary output file
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "test_review.tex"

            # Create analysis configuration
            config = AnalysisConfig(
                draft_file=Path("draft_example/draft.tex"),
                comments_file=Path("comments.txt"),
                output_file=output_file,
                template_file=Path("output_template/review_template.tex"),
                keywords_file=Path("keywords.txt"),
                llm_provider="test",
                api_key="test_key",
                model="test-model",
                max_tokens=3000,
                temperature=0.3,
                request_timeout=60,
                max_retries=3,
                cache_enabled=False,  # Disable caching for tests
                concise_mode=True,
                two_pass_mode=False  # Use single-pass for simpler testing
            )

            # Mock the LLM client (patch at the source)
            with patch('src.llm.create_client') as mock_create_client:
                mock_llm = MagicMock()
                mock_create_client.return_value = mock_llm

                # Mock analyze_section to return reviews only for first 2 sections
                # This simulates finding 2 issues across the document
                def side_effect_analyze(*args, **kwargs):
                    # Return 1 review for first 2 calls, empty for rest
                    call_count = mock_llm.analyze_section.call_count
                    if call_count == 1:
                        return [mock_reviews[0]]
                    elif call_count == 2:
                        return [mock_reviews[1]]
                    else:
                        return []

                mock_llm.analyze_section = Mock(side_effect=side_effect_analyze)

                # Mock analyze_document_two_pass (in case two_pass is enabled)
                mock_llm.analyze_document_two_pass = Mock(return_value=mock_reviews)

                # Create analyzer and run analysis
                analyzer = DocumentAnalyzer(config)
                result = analyzer.analyze()

                # Verify the workflow completed
                assert result is not None
                assert isinstance(result, AnalysisResult)
                assert len(result.reviews) == 2
                assert isinstance(result.summary, str)

                # Verify LLM client was created with correct parameters
                mock_create_client.assert_called_once()
                call_kwargs = mock_create_client.call_args[1]
                assert call_kwargs['provider'] == "test"
                assert call_kwargs['api_key'] == "test_key"
                assert call_kwargs['model'] == "test-model"

                # Verify analyze_section was called for each section
                # (because two_pass_mode=False in our test config)
                assert mock_llm.analyze_section.call_count > 0

                # Verify output file was created
                assert output_file.exists()
                content = output_file.read_text()

                # Verify output contains expected LaTeX structure
                assert r'\begin{reviewer}' in content
                assert r'\end{reviewer}' in content
                assert 'Category: [Language]' in content or 'Category: [Typography]' in content

    def test_parse_integration(self):
        """
        Test that parsers work correctly with real files.
        """
        from src.parsers.comments_parser import CommentsParser
        from src.parsers.tex_parser import TeXParser
        from src.parsers.keywords_parser import KeywordsParser

        # Test comments parser
        comments_parser = CommentsParser(Path("comments.txt"))
        rules = comments_parser.parse()
        assert len(rules) > 0, "Should parse rules from comments.txt"
        assert "1.1" in [r.id for r in rules], "Should have rule 1.1"

        # Test LaTeX parser
        tex_parser = TeXParser(Path("draft_example/draft.tex"))
        structure = tex_parser.parse()
        assert structure is not None, "Should parse draft.tex"
        assert len(structure.sections) > 0, "Should have sections"
        assert structure.title is not None, "Should have title"

        # Test keywords parser
        keywords_parser = KeywordsParser(Path("keywords.txt"))
        keywords_text = keywords_parser.format_for_prompt()
        # Should not crash even if file has no keywords
        assert keywords_text is not None

    def test_analysis_config_validation(self):
        """Test that AnalysisConfig holds correct values"""
        config = AnalysisConfig(
            draft_file=Path("draft_example/draft.tex"),
            comments_file=Path("comments.txt"),
            output_file=Path("review.tex"),
            template_file=Path("output_template/review_template.tex"),
            keywords_file=Path("keywords.txt"),
            llm_provider="test",
            api_key="test_key",
            model="test-model",
            max_tokens=3000,
            temperature=0.3,
            request_timeout=60,
            max_retries=3,
            cache_enabled=False,
            concise_mode=True,
            two_pass_mode=False
        )

        assert config.draft_file == Path("draft_example/draft.tex")
        assert config.llm_provider == "test"
        assert config.two_pass_mode is False
        assert config.cache_enabled is False
