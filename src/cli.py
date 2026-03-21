"""
Command Line Interface
"""
import click
import logging
from pathlib import Path
import sys

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.workflow import DocumentAnalyzer, AnalysisConfig
# Import parsers for parse and parse-comments commands
from src.parsers.comments_parser import CommentsParser
from src.parsers.tex_parser import TeXParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """LaTeX Paper AI Reviewer"""
    pass


@cli.command()
@click.option(
    '--draft',
    type=click.Path(exists=True),
    default=None,
    help='LaTeX draft file path'
)
@click.option(
    '--comments',
    type=click.Path(exists=True),
    default=None,
    help='Style rules file path (comments.txt)'
)
@click.option(
    '--output',
    type=click.Path(),
    default=None,
    help='Output review.tex file path'
)
@click.option(
    '--provider',
    type=click.Choice(['deepseek', 'openai', 'anthropic', 'zhipu']),
    default=None,
    help='LLM provider'
)
@click.option(
    '--model',
    type=str,
    default=None,
    help='LLM model name'
)
@click.option(
    '--verbose',
    is_flag=True,
    help='Show verbose logging'
)
@click.option(
    '--debug',
    is_flag=True,
    help='Show debug information (including prompt length, token usage, etc.)'
)
def analyze(draft, comments, output, provider, model, verbose, debug):
    """
    Analyze LaTeX paper and generate review report

    Uses project-configured file paths and LLM settings by default.
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Update configuration
    if draft:
        settings.draft_file = Path(draft)
    if comments:
        settings.comments_file = Path(comments)
    if output:
        settings.output_file = Path(output)
    if provider:
        settings.llm_provider = provider
    if model:
        if settings.llm_provider == "deepseek":
            settings.deepseek_model = model
        elif settings.llm_provider == "openai":
            settings.openai_model = model
        elif settings.llm_provider == "anthropic":
            settings.anthropic_model = model
        elif settings.llm_provider == "zhipu":
            settings.zhipu_model = model

    # Validate configuration
    try:
        settings.validate()
    except (ValueError, FileNotFoundError) as e:
        click.echo(f"Configuration error: {e}", err=True)
        return

    click.echo(f"Starting analysis...")
    click.echo(f"Draft: {settings.draft_file}")
    click.echo(f"Style rules: {settings.comments_file}")
    click.echo(f"Output: {settings.output_file}")
    # Display model name
    model_name = {
        "deepseek": settings.deepseek_model,
        "openai": settings.openai_model,
        "anthropic": settings.anthropic_model,
        "zhipu": settings.zhipu_model
    }.get(settings.llm_provider, "unknown")
    click.echo(f"LLM: {settings.llm_provider} ({model_name})")
    click.echo("")

    # Get API key and model
    if settings.llm_provider == "deepseek":
        api_key = settings.deepseek_api_key
        model = settings.deepseek_model
    elif settings.llm_provider == "openai":
        api_key = settings.openai_api_key
        model = settings.openai_model
    elif settings.llm_provider == "anthropic":
        api_key = settings.anthropic_api_key
        model = settings.anthropic_model
    else:  # zhipu
        api_key = settings.zhipu_api_key
        model = settings.zhipu_model

    # Create configuration for workflow
    config = AnalysisConfig(
        draft_file=settings.draft_file,
        comments_file=settings.comments_file,
        output_file=settings.output_file,
        template_file=settings.template_file,
        keywords_file=settings.keywords_file,
        llm_provider=settings.llm_provider,
        api_key=api_key,
        model=model,
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
        request_timeout=settings.request_timeout,
        max_retries=settings.max_retries,
        cache_enabled=settings.cache_responses,
        concise_mode=settings.concise_mode,
        two_pass_mode=settings.two_pass_mode
    )

    # Create analyzer and run workflow
    analyzer = DocumentAnalyzer(config)

    # Display progress messages
    click.echo("Step 1/4: Parsing style rules...")
    click.echo("Step 2/4: Parsing LaTeX document...")
    click.echo("Step 3/4: Analyzing document with LLM...")
    if settings.two_pass_mode:
        click.echo("  Using two-pass analysis mode (ensures global consistency)")
    click.echo("Step 4/4: Generating review report...")

    # Execute analysis
    result = analyzer.analyze()

    # Display results
    click.echo(f"  Found {len(result.reviews)} issues")
    click.echo(f"  Review report saved to: {settings.output_file}")
    click.echo("\n" + result.summary)


@cli.command()
@click.option(
    '--draft',
    type=click.Path(exists=True),
    default=None,
    help='LaTeX draft file path'
)
def parse(draft):
    """Parse LaTeX document and display structure"""
    draft_file = Path(draft) if draft else settings.draft_file

    click.echo(f"Parsing file: {draft_file}")

    parser = TeXParser(draft_file)
    structure = parser.parse()

    click.echo(f"\nTitle: {structure.title}")
    click.echo(f"\nNumber of sections: {len(structure.sections)}")

    for section in structure.sections:
        click.echo(f"\n- {section.title} (line {section.line_number})")
        if section.subsections:
            for subsection in section.subsections:
                click.echo(f"  - {subsection.title} (line {subsection.line_number})")

    click.echo(f"\nNumber of equations: {len(structure.equations)}")
    click.echo(f"Number of tables: {len(structure.tables)}")


@cli.command()
@click.option(
    '--comments',
    type=click.Path(exists=True),
    default=None,
    help='Style rules file path'
)
def parse_comments(comments):
    """Parse style rules file"""
    comments_file = Path(comments) if comments else settings.comments_file

    click.echo(f"Parsing file: {comments_file}")

    parser = CommentsParser(comments_file)
    rules = parser.parse()

    click.echo(f"\nParsed {len(rules)} rules")
    click.echo(f"\nCategories: {parser.get_all_categories()}")

    # Display rules by category
    for category in parser.get_all_categories():
        category_rules = parser.get_rules_by_category(category)
        click.echo(f"\n{category} ({len(category_rules)} rules):")
        for rule in category_rules[:5]:  # Only show first 5
            click.echo(f"  {rule.id}. {rule.description[:60]}...")
        if len(category_rules) > 5:
            click.echo(f"  ... and {len(category_rules) - 5} more")


def main():
    """Main entry point"""
    cli()


if __name__ == "__main__":
    main()
