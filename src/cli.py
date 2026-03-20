"""
命令行界面
"""
import click
import logging
from pathlib import Path
import sys
from tqdm import tqdm

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.parsers.comments_parser import CommentsParser
from src.parsers.tex_parser import TeXParser
from src.parsers.keywords_parser import KeywordsParser
from src.llm import create_client
from src.generators import ReviewGenerator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """LaTeX 论文 AI 审稿工具"""
    pass


@cli.command()
@click.option(
    '--draft',
    type=click.Path(exists=True),
    default=None,
    help='LaTeX 原稿文件路径'
)
@click.option(
    '--comments',
    type=click.Path(exists=True),
    default=None,
    help='样式规则文件路径 (comments.txt)'
)
@click.option(
    '--output',
    type=click.Path(),
    default=None,
    help='输出 review.tex 文件路径'
)
@click.option(
    '--provider',
    type=click.Choice(['deepseek', 'openai', 'anthropic', 'zhipu']),
    default=None,
    help='LLM 提供商'
)
@click.option(
    '--model',
    type=str,
    default=None,
    help='LLM 模型名称'
)
@click.option(
    '--verbose',
    is_flag=True,
    help='显示详细日志'
)
@click.option(
    '--debug',
    is_flag=True,
    help='显示调试信息（包括 prompt 长度、token 使用等）'
)
def analyze(draft, comments, output, provider, model, verbose, debug):
    """
    分析 LaTeX 论文并生成审稿报告

    默认使用项目配置的文件路径和 LLM 设置。
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # 更新配置
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

    # 验证配置
    try:
        settings.validate()
    except (ValueError, FileNotFoundError) as e:
        click.echo(f"配置错误: {e}", err=True)
        return

    click.echo(f"开始分析...")
    click.echo(f"原稿: {settings.draft_file}")
    click.echo(f"样式规则: {settings.comments_file}")
    click.echo(f"输出: {settings.output_file}")
    # 显示模型名称
    model_name = {
        "deepseek": settings.deepseek_model,
        "openai": settings.openai_model,
        "anthropic": settings.anthropic_model,
        "zhipu": settings.zhipu_model
    }.get(settings.llm_provider, "unknown")
    click.echo(f"LLM: {settings.llm_provider} ({model_name})")
    click.echo("")

    # 步骤 1: 解析样式规则
    click.echo("步骤 1/4: 解析样式规则...")
    comments_parser = CommentsParser(settings.comments_file)
    rules = comments_parser.parse()
    click.echo(f"  解析到 {len(rules)} 条样式规则")

    # 格式化规则用于 prompt
    rules_text = comments_parser.format_rules_for_prompt()

    # 步骤 2: 解析 LaTeX 文档
    click.echo("步骤 2/4: 解析 LaTeX 文档...")
    tex_parser = TeXParser(settings.draft_file)
    structure = tex_parser.parse()
    click.echo(f"  解析到 {len(structure.sections)} 个章节")

    # 获取用于分析的章节
    sections = structure.get_sections_for_analysis()
    click.echo(f"  将分析 {len(sections)} 个章节")

    # 步骤 2.5: 解析关键词（如果存在）
    keywords_parser = KeywordsParser(settings.keywords_file)
    keywords_text = keywords_parser.format_for_prompt()
    if keywords_text:
        keywords_summary = keywords_parser.get_keywords_summary()
        click.echo(f"  关键词: {keywords_summary}")

    # 步骤 3: 创建 LLM 客户端并分析
    click.echo("步骤 3/4: 使用 LLM 分析文档...")

    # 获取 API 密钥和模型
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

    # 创建客户端
    llm_client = create_client(
        provider=settings.llm_provider,
        api_key=api_key,
        model=model,
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
        request_timeout=settings.request_timeout,
        max_retries=settings.max_retries,
        cache_enabled=settings.cache_responses,
        concise_mode=settings.concise_mode
    )

    # 分析每个章节
    all_reviews = []

    # 根据配置选择分析模式
    if settings.two_pass_mode:
        # 两阶段分析模式（确保全局一致性）
        click.echo("  使用两阶段分析模式（确保全局一致性）")
        all_reviews = llm_client.analyze_document_two_pass(
            sections=sections,
            rules_text=rules_text,
            keywords=keywords_text
        )
    else:
        # 单阶段分析模式（原有模式）
        with tqdm(sections, desc="  分析进度") as pbar:
            for section in pbar:
                pbar.set_description(f"  分析: {section['title'][:30]}")

                reviews = llm_client.analyze_section(
                    section_title=section["title"],
                    section_content=section["content"],
                    rules=rules_text
                )

                all_reviews.extend(reviews)
                pbar.set_postfix({"发现": len(all_reviews)})

    click.echo(f"  发现 {len(all_reviews)} 个问题")

    # 步骤 4: 生成 review.tex
    click.echo("步骤 4/4: 生成审稿报告...")

    generator = ReviewGenerator(settings.template_file)
    generator.generate(
        review_items=all_reviews,
        output_file=settings.output_file,
        draft_file=str(settings.draft_file)
    )

    click.echo(f"  审稿报告已保存到: {settings.output_file}")

    # 显示摘要
    summary = generator.generate_summary(all_reviews)
    click.echo("\n" + summary)


@cli.command()
@click.option(
    '--draft',
    type=click.Path(exists=True),
    default=None,
    help='LaTeX 原稿文件路径'
)
def parse(draft):
    """解析 LaTeX 文档并显示结构"""
    draft_file = Path(draft) if draft else settings.draft_file

    click.echo(f"解析文件: {draft_file}")

    parser = TeXParser(draft_file)
    structure = parser.parse()

    click.echo(f"\n标题: {structure.title}")
    click.echo(f"\n章节数量: {len(structure.sections)}")

    for section in structure.sections:
        click.echo(f"\n- {section.title} (行 {section.line_number})")
        if section.subsections:
            for subsection in section.subsections:
                click.echo(f"  - {subsection.title} (行 {subsection.line_number})")

    click.echo(f"\n方程数量: {len(structure.equations)}")
    click.echo(f"表格数量: {len(structure.tables)}")


@cli.command()
@click.option(
    '--comments',
    type=click.Path(exists=True),
    default=None,
    help='样式规则文件路径'
)
def parse_comments(comments):
    """解析样式规则文件"""
    comments_file = Path(comments) if comments else settings.comments_file

    click.echo(f"解析文件: {comments_file}")

    parser = CommentsParser(comments_file)
    rules = parser.parse()

    click.echo(f"\n解析到 {len(rules)} 条规则")
    click.echo(f"\n类别: {parser.get_all_categories()}")

    # 按类别显示规则
    for category in parser.get_all_categories():
        category_rules = parser.get_rules_by_category(category)
        click.echo(f"\n{category} ({len(category_rules)} 条规则):")
        for rule in category_rules[:5]:  # 只显示前5条
            click.echo(f"  {rule.id}. {rule.description[:60]}...")
        if len(category_rules) > 5:
            click.echo(f"  ... 还有 {len(category_rules) - 5} 条")


def main():
    """主入口"""
    cli()


if __name__ == "__main__":
    main()
