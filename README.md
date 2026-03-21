# LaTeX Paper AI Reviewer

An AI-powered LaTeX paper reviewer for physics papers. The tool parses LaTeX documents, analyzes them using LLMs against style rules, and generates structured review reports in LaTeX format.

## Features

### Core Features
- Parse LaTeX document structures (sections, equations, tables, etc.)
- Process long documents in sections split by `\section{}`
- Support multiple LLM providers (**DeepSeek**, OpenAI GPT-4, Anthropic Claude)
- Generate review.tex files that conform to templates
- Use "section/subsection + context" format to locate issues

### Advanced Features
- **Two-pass analysis mode**: Ensures global consistency, avoids terminology conflicts and duplicate suggestions
- **Custom keywords**: Supports domain-specific terminology for more professional reviews
- **Concise comment mode**: Configurable output length to control token consumption
- **Response caching**: Automatically saves API responses for debugging and reuse

## Installation

### 1. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env` file:

```bash
# LLM Provider (deepseek, openai, anthropic)
LLM_PROVIDER=deepseek

# DeepSeek Configuration (default, cost-effective)
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
TWO_PASS_MODE=true         # Two-pass analysis (recommended)
CONCISE_MODE=true          # Concise mode
MAX_OUTPUT_TOKENS=1000     # Output token limit

# Keywords File
KEYWORDS_FILE=./keywords.txt

# File Paths
COMMENTS_FILE=./comments.txt
DRAFT_FILE=./draft_example/draft.tex
OUTPUT_FILE=./review.tex
TEMPLATE_FILE=./output_template/review_template.tex
```

## Usage

### Basic Usage

```bash
python -m src.cli analyze
```

### Specify Files

```bash
python -m src.cli analyze \
  --draft my_paper.tex \
  --comments my_rules.txt \
  --output my_review.tex
```

### Specify LLM Provider

```bash
# DeepSeek (default)
python -m src.cli analyze --provider deepseek --model deepseek-chat

# OpenAI
python -m src.cli analyze --provider openai --model gpt-4

# Anthropic
python -m src.cli analyze --provider anthropic --model claude-3-5-sonnet-20241022
```

### Analysis Mode Selection

```bash
# Two-pass analysis (recommended, ensures global consistency)
TWO_PASS_MODE=true python -m src.cli analyze

# Single-pass analysis (original mode, faster but may lack consistency)
TWO_PASS_MODE=false python -m src.cli analyze
```

### Other Commands

Parse LaTeX document structure:

```bash
python -m src.cli parse --draft draft_example/draft.tex
```

Parse style rules:

```bash
python -m src.cli parse-comments --comments comments.txt
```

## Customizing Keywords

Edit `keywords.txt` file to add domain-specific terms you want the AI to focus on:

```
# Physics terminology
chi_cJ
psi(3686)
branching fraction
invariant mass

# Experiment terminology
BESIII detector
systematic uncertainty
statistical significance
```

## Project Structure

```
latex_reviewer/
├── config/
│   └── settings.py              # Configuration management
├── src/
│   ├── cli.py                   # Command line interface
│   ├── parsers/
│   │   ├── tex_parser.py        # LaTeX parser
│   │   ├── comments_parser.py   # Style rules parser
│   │   └── keywords_parser.py   # Keywords parser
│   ├── llm/
│   │   ├── base_client.py       # LLM client base class
│   │   ├── analysis_state.py    # Global state management (two-pass analysis)
│   │   ├── deepseek_client.py   # DeepSeek implementation
│   │   ├── openai_client.py     # OpenAI implementation
│   │   └── anthropic_client.py  # Anthropic implementation
│   └── generators/
│       └── review_generator.py  # Review generator
├── comments.txt                 # Style rules
├── keywords.txt                 # User-defined keywords
├── draft_example/               # Example paper
├── output_template/             # Output template
├── responses_cache/             # API response cache
└── requirements.txt             # Dependencies
```

## Workflow

### Single-Pass Mode (TWO_PASS_MODE=false)

```
Parse style rules → Parse document → Analyze each section → Generate report
```

### Two-Pass Mode (TWO_PASS_MODE=true, recommended)

```
Phase 1: Lightweight scan → Global state accumulation (terminology, issue summaries) → Phase 2: Detailed section-by-section analysis → Generate review report
```

**Two-pass mode advantages:**
- Global consistency: Terminology handled consistently across all sections
- Avoid duplicates: Same pattern issues reported only once
- Resumability: Phase 1 results can be cached, Phase 2 can be executed in segments
- Stability: Smaller requests reduce failure risk

## Output Format

Generated `review.tex` contains the following structure:

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

Where:
- **Category name**: Rule violation category (e.g., Language, Typography)
- **Rule id**: Rule number (e.g., 1.1, 3.0)
- **Severity**: Severity level (high, medium, low)

## Response Caching

API responses are automatically saved to `responses_cache/{provider}/` directory:

```
responses_cache/
└── deepseek/
    ├── 20260320_154733_Introduction.json
    ├── 20260320_154941_BESIII_DETECTOR.json
    └── ...
```

Each cache file contains:
- Metadata (timestamp, model, section)
- Request content (system prompt, user prompt)
- Response content (raw response, parsed content, token usage statistics)

## Configuration Options

| Option | Default | Description |
|------|--------|------|
| `TWO_PASS_MODE` | true | Enable two-pass analysis |
| `CONCISE_MODE` | true | Concise comment mode |
| `MAX_OUTPUT_TOKENS` | 3000 | Output token limit |
| `CACHE_RESPONSES` | true | Whether to cache responses |
| `TEMPERATURE` | 0.3 | AI generation temperature (lower = more deterministic) |

## License

MIT License
