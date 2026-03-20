"""
配置管理模块

管理API密钥、文件路径和分析参数
"""
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()


@dataclass
class Settings:
    """应用配置"""

    # LLM 提供商配置
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "deepseek"))
    deepseek_api_key: Optional[str] = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY"))
    deepseek_model: str = field(default_factory=lambda: os.getenv("DEEPSEEK_MODEL", "deepseek-chat"))
    openai_api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4"))
    anthropic_api_key: Optional[str] = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
    anthropic_model: str = field(default_factory=lambda: os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"))
    zhipu_api_key: Optional[str] = field(default_factory=lambda: os.getenv("ZHIPU_API_KEY"))
    zhipu_model: str = field(default_factory=lambda: os.getenv("ZHIPU_MODEL", "glm-4-flash"))

    # API 设置
    max_tokens: int = field(default_factory=lambda: int(os.getenv("MAX_TOKENS", "4000")))
    temperature: float = field(default_factory=lambda: float(os.getenv("TEMPERATURE", "0.3")))
    request_timeout: int = field(default_factory=lambda: int(os.getenv("REQUEST_TIMEOUT", "180")))  # 60 -> 180
    max_retries: int = field(default_factory=lambda: int(os.getenv("MAX_RETRIES", "5")))  # 3 -> 5

    # 文件路径
    project_root: Path = field(default_factory=lambda: Path(__file__).parent.parent)
    comments_file: Path = field(default_factory=lambda: Path(os.getenv("COMMENTS_FILE", "./comments.txt")))
    draft_file: Path = field(default_factory=lambda: Path(os.getenv("DRAFT_FILE", "./draft_example/draft.tex")))
    output_file: Path = field(default_factory=lambda: Path(os.getenv("OUTPUT_FILE", "./review.tex")))
    template_file: Path = field(default_factory=lambda: Path(os.getenv("TEMPLATE_FILE", "./output_template/review_template.tex")))

    # 响应缓存设置
    cache_responses: bool = field(default_factory=lambda: os.getenv("CACHE_RESPONSES", "true").lower() == "true")
    cache_dir: Path = field(default_factory=lambda: Path(os.getenv("CACHE_DIR", "./responses_cache")))

    # 分析模式设置
    two_pass_mode: bool = field(default_factory=lambda: os.getenv("TWO_PASS_MODE", "true").lower() == "true")
    concise_mode: bool = field(default_factory=lambda: os.getenv("CONCISE_MODE", "true").lower() == "true")
    max_output_tokens: int = field(default_factory=lambda: int(os.getenv("MAX_OUTPUT_TOKENS", "3000")))

    # 关键词文件
    keywords_file: Path = field(default_factory=lambda: Path(os.getenv("KEYWORDS_FILE", "./keywords.txt")))

    def __post_init__(self):
        """将相对路径转换为绝对路径"""
        if not self.comments_file.is_absolute():
            self.comments_file = self.project_root / self.comments_file
        if not self.draft_file.is_absolute():
            self.draft_file = self.project_root / self.draft_file
        if not self.output_file.is_absolute():
            self.output_file = self.project_root / self.output_file
        if not self.template_file.is_absolute():
            self.template_file = self.project_root / self.template_file

        # 确保缓存目录存在
        if self.cache_responses:
            if not self.cache_dir.is_absolute():
                self.cache_dir = self.project_root / self.cache_dir
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 处理关键词文件路径
        if not self.keywords_file.is_absolute():
            self.keywords_file = self.project_root / self.keywords_file

    def validate(self) -> None:
        """验证配置"""
        if self.llm_provider == "deepseek" and not self.deepseek_api_key:
            raise ValueError("使用 DeepSeek 时必须设置 DEEPSEEK_API_KEY")
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise ValueError("使用 OpenAI 时必须设置 OPENAI_API_KEY")
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("使用 Anthropic 时必须设置 ANTHROPIC_API_KEY")
        if self.llm_provider == "zhipu" and not self.zhipu_api_key:
            raise ValueError("使用智谱 GLM 时必须设置 ZHIPU_API_KEY")

        if not self.comments_file.exists():
            raise FileNotFoundError(f"找不到文件: {self.comments_file}")
        if not self.draft_file.exists():
            raise FileNotFoundError(f"找不到文件: {self.draft_file}")
        if not self.template_file.exists():
            raise FileNotFoundError(f"找不到文件: {self.template_file}")


# 全局配置实例
settings = Settings()
