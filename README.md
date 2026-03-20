# LaTeX 论文 AI 审稿工具

基于 Python 的 AI 驱动物理学论文审稿工具。该工具解析 LaTeX 论文，使用大语言模型根据样式规则进行分析，并生成结构化的审稿报告。

## 功能特点

### 核心功能
- 解析 LaTeX 文档结构（章节、方程、表格等）
- 按 `\section{}` 分块处理长文档
- 支持多种 LLM 提供商（**DeepSeek**、OpenAI GPT-4、Anthropic Claude）
- 生成符合模板的 review.tex 文件
- 使用 "章节/子章节 + 上下文" 格式定位问题

### 高级功能
- **两阶段分析模式**：确保全局一致性，避免术语冲突和重复建议
- **关键词自定义**：支持领域特定术语，提高审核专业性
- **简洁评论模式**：可配置输出长度，控制 token 消耗
- **响应缓存**：自动保存 API 响应，便于调试和复用

## 安装

### 1. 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env` 并配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# LLM Provider (deepseek, openai, anthropic)
LLM_PROVIDER=deepseek

# DeepSeek Configuration (默认，性价比高)
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_MODEL=deepseek-chat

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4

# Anthropic Configuration
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# API Settings
MAX_TOKENS=3000
TEMPERATURE=0.3
REQUEST_TIMEOUT=300
MAX_RETRIES=3

# Response Cache Settings
CACHE_RESPONSES=true
CACHE_DIR=./responses_cache

# Analysis Mode Settings
TWO_PASS_MODE=true         # 两阶段分析（推荐）
CONCISE_MODE=true          # 简洁模式
MAX_OUTPUT_TOKENS=1000     # 输出 token 限制

# Keywords File
KEYWORDS_FILE=./keywords.txt

# File Paths
COMMENTS_FILE=./comments.txt
DRAFT_FILE=./draft_example/draft.tex
OUTPUT_FILE=./review.tex
TEMPLATE_FILE=./output_template/review_template.tex
```

## 使用方法

### 基本用法

```bash
python -m src.cli analyze
```

### 指定文件

```bash
python -m src.cli analyze \
  --draft my_paper.tex \
  --comments my_rules.txt \
  --output my_review.tex
```

### 指定 LLM 提供商

```bash
# DeepSeek (默认)
python -m src.cli analyze --provider deepseek --model deepseek-chat

# OpenAI
python -m src.cli analyze --provider openai --model gpt-4

# Anthropic
python -m src.cli analyze --provider anthropic --model claude-3-5-sonnet-20241022
```

### 分析模式选择

```bash
# 两阶段分析（推荐，确保全局一致性）
TWO_PASS_MODE=true python -m src.cli analyze

# 单阶段分析（原有模式，速度更快但可能缺乏一致性）
TWO_PASS_MODE=false python -m src.cli analyze
```

### 其他命令

解析 LaTeX 文档结构：

```bash
python -m src.cli parse --draft draft_example/draft.tex
```

解析样式规则：

```bash
python -m src.cli parse-comments --comments comments.txt
```

## 自定义关键词

编辑 `keywords.txt` 文件，添加你希望 AI 特别关注的领域术语：

```
# 粒子物理相关术语
chi_cJ
psi(3686)
branching fraction
invariant mass

# 实验相关术语
BESIII detector
systematic uncertainty
statistical significance
```

## 项目结构

```
latex_reviewer/
├── config/
│   └── settings.py              # 配置管理
├── src/
│   ├── cli.py                   # 命令行界面
│   ├── parsers/
│   │   ├── tex_parser.py        # LaTeX 解析器
│   │   ├── comments_parser.py   # 样式规则解析器
│   │   └── keywords_parser.py   # 关键词解析器
│   ├── llm/
│   │   ├── base_client.py       # LLM 客户端基类
│   │   ├── analysis_state.py    # 全局状态管理（两阶段分析）
│   │   ├── deepseek_client.py   # DeepSeek 实现
│   │   ├── openai_client.py     # OpenAI 实现
│   │   └── anthropic_client.py  # Anthropic 实现
│   └── generators/
│       └── review_generator.py  # Review 生成器
├── comments.txt                 # 样式规则
├── keywords.txt                 # 用户自定义关键词
├── draft_example/               # 示例论文
├── output_template/             # 输出模板
├── responses_cache/             # API 响应缓存
└── requirements.txt             # 依赖
```

## 工作流程

### 单阶段模式（TWO_PASS_MODE=false）

```
解析样式规则 → 解析文档 → 逐节分析 → 生成报告
```

### 两阶段模式（TWO_PASS_MODE=true，推荐）

```
┌─────────────────────────────────────────────────────┐
│                    阶段 1：轻量级扫描                  │
├─────────────────────────────────────────────────────┤
│  • 快速扫描每个章节                                    │
│  • 提取关键术语                                       │
│  • 识别潜在问题模式                                    │
│  • 输出简化的 JSON 摘要                               │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│              全局状态累积（术语、问题摘要）              │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│                  阶段 2：详细分析                     │
├─────────────────────────────────────────────────────┤
│  • 基于阶段1的全局状态                                 │
│  • 详细分析每个章节                                    │
│  • 避免重复建议                                       │
│  • 确保术语一致性                                      │
│  • 输出完整的审查条目                                  │
└─────────────────────────────────────────────────────┘
                          ↓
                    生成审稿报告
```

**两阶段模式的优势：**
- 全局一致性：术语在所有章节中处理一致
- 避免重复：相同模式的问题只报告一次
- 可恢复性：阶段1结果可缓存，阶段2可分段执行
- 稳定性：更小的请求，降低失败风险

## 输出格式

生成的 `review.tex` 包含以下结构：

```latex
\begin{reviewer}
\noindent \textbf{Category: [Category name] [Rule id] [Severity]}

\textbf{Source Context:}
\begin{lstlisting}[breaklines=true]
"Problem text fragment"
\end{lstlisting}

\textbf{Reviewer Comment:}

"Explanation"

\textbf{Suggested Revision:}
\begin{lstlisting}[breaklines=true]
"Suggested revision"
\end{lstlisting}
\end{reviewer}
```

其中：
- **Category name**: 违反规则的类别（如 Language, Typography）
- **Rule id**: 规则编号（如 1.1, 3.0）
- **Severity**: 严重程度（high, medium, low）

## 响应缓存

API 响应自动保存到 `responses_cache/{provider}/` 目录：

```
responses_cache/
└── deepseek/
    ├── 20260320_154733_Introduction.json
    ├── 20260320_154941_BESIII_DETECTOR.json
    └── ...
```

每个缓存文件包含：
- 元数据（时间戳、模型、章节）
- 请求内容（system prompt、user prompt）
- 响应内容（原始响应、解析后内容、token 使用统计）

## 配置选项说明

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `TWO_PASS_MODE` | true | 启用两阶段分析 |
| `CONCISE_MODE` | true | 简洁评论模式 |
| `MAX_OUTPUT_TOKENS` | 3000 | 输出 token 限制 |
| `CACHE_RESPONSES` | true | 是否缓存响应 |
| `TEMPERATURE` | 0.3 | AI 生成温度（越低越确定性） |

## 许可证

MIT License
