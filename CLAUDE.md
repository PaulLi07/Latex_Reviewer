# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

This project is an AI-powered LaTeX paper reviewer.

It parses LaTeX documents, applies rule-based and LLM-based analysis, and generates structured LaTeX review output.

The system follows a strict pipeline:

```
CLI → Workflow → Parsers → LLM Analysis → Generator (LaTeX)
```

This pipeline is a core design principle and must be preserved.

---

## Core Architecture Constraints (MUST FOLLOW)

The system consists of four core layers:

- **CLI** (`cli.py`) - User interface only
- **Workflow** (`workflow/`) - Business logic orchestration
- **Parsers** (`parsers/`) - Input processing
- **LLM Analysis** (`llm/`) - Reasoning
- **Generator** (`generators/`) - LaTeX output

These layers are REQUIRED and MUST NOT be:

- Removed
- Bypassed
- Merged together

Each layer must:
- Remain independent
- Preserve its responsibility

---

## Workflow Layer (IMPORTANT)

The `DocumentAnalyzer` class in `src/workflow/document_analyzer.py` orchestrates the analysis pipeline.

**Responsibilities:**
- Parse style rules, documents, and keywords
- Create LLM client with proper configuration
- Execute single-pass or two-pass analysis
- Generate LaTeX output

**CLI responsibilities (NOT workflow):**
- Command-line argument parsing
- User-facing progress messages
- Configuration updates from CLI options
- Result display formatting

---

## Generator (LaTeX Output) Constraints

The Generator is responsible for producing the final LaTeX output.

You MAY:
- Fix LaTeX compilation issues
- Improve formatting robustness
- Refactor internal implementation
- Improve escaping and structure handling

You MUST NOT:
- Remove the Generator layer
- Move LaTeX generation into LLM prompts
- Replace LaTeX output with another format (e.g., Markdown/JSON)
- Break compatibility with the existing review.tex structure

The Generator must remain the single source of truth for output formatting.

---

## Output Contract (STRICT)

The final output must:

- Be a valid and compilable LaTeX document
- Use the existing reviewer block structure:
  ```latex
  \begin{reviewer}
  \noindent \textbf{Location: ["Section and location"]}
  ...
  \end{reviewer}
  ```
- Preserve compatibility with existing LaTeX templates

When improving the Generator, prioritize:

- Eliminating compilation errors
- Correct escaping of LaTeX special characters
- Structural correctness of environments

---

## LLM Analysis Constraints

The LLM layer is responsible for analysis ONLY.

You MUST NOT:
- Perform output formatting in LLM responses
- Generate LaTeX directly inside prompts
- Bypass structured processing

You SHOULD:
- Return structured intermediate results where possible
- Separate reasoning from formatting

---

## LLM Client Architecture

All LLM providers inherit from `BaseLLMClient` which contains:

**Shared Methods (in base class):**
- `_get_system_prompt()` - System prompt with concise mode support
- `_build_prompt()` - User prompt for single-section analysis
- `_build_detailed_prompt()` - Prompt for two-pass detailed analysis
- `_parse_response()` - Response parsing using json_parser
- `_get_simplified_rules()` - Rule simplification for lightweight scan

**Abstract Methods (provider-specific):**
- `_get_provider_name()` - Returns provider identifier (e.g., "deepseek", "openai")
- `_make_api_call()` - Executes provider-specific API calls
- `_extract_content()` - Extracts text from responses
- `_extract_usage()` - Standardizes token usage data (prompt_tokens, completion_tokens, total_tokens)

**Helper:**
- `_prepare_and_save_response()` - Handles response caching using provider-specific extractors

Provider implementations only need to implement the 4 abstract methods - all other logic is inherited.

---

## JSON Parser

The `src/llm/json_parser.py` module provides robust JSON extraction from LLM responses.

**Features:**
- Handles markdown code blocks (```json ... ```)
- Handles extra text before/after JSON
- Uses bracket counting for nested structures (not `find('{')`/`rfind('}')`)
- Explicit validation with `JSONParseError` exceptions

**Key functions:**
- `extract_json()` - Generic JSON extraction with validation
- `extract_review_items()` - Extracts violations array with location formatting
- `extract_scan_summary()` - Extracts scan results for two-pass analysis

---

## Parser Constraints

Parsers are responsible for structured extraction.

You MUST:
- Use parser outputs as the source of truth
- Keep parsing logic separate from analysis

You MUST NOT:
- Re-parse LaTeX inside LLM prompts
- Mix parsing logic into other layers

---

## Two-Pass Analysis Constraints

The system uses a two-pass analysis mode:

Phase 1:
- Lightweight scan
- Extract terminology and global signals

Phase 2:
- Detailed analysis using global context

You MUST NOT:
- Remove the two-pass structure
- Collapse it into a single-pass system

You MAY:
- Improve intermediate data structures
- Improve how global context is stored and used

---

## Architectural Evolution (IMPORTANT)

The system is expected to evolve and improve over time.

You are encouraged to propose improvements in:

- Introducing structured intermediate representations between parsing and LLM analysis
- Converting rule definitions (comments.txt) into structured formats
- Improving analysis pipeline design (while preserving two-pass structure)
- Improving modularity and separation of concerns

All improvements MUST:

- Preserve the core pipeline (CLI → Workflow → Parsers → LLM → Generator)
- Preserve the LaTeX output contract
- Maintain backward compatibility unless explicitly approved

---

## Change Process (MANDATORY)

Before making architectural or structural changes:

1. Propose a design plan
2. Clearly explain:
   - What problem it solves
   - What components are affected
   - Why it does not violate core constraints
3. Wait for confirmation before implementing

Do NOT directly implement large or cross-module changes.

---

## Allowed Improvements

You are encouraged to:

- Improve parsing robustness
- Improve LLM interaction quality
- Introduce intermediate representations
- Improve rule handling and validation
- Improve LaTeX generation reliability
- Refactor code for readability and maintainability (within module boundaries)

All improvements must preserve external behavior.

---

## Behavior Rules for Claude

- Prefer minimal, incremental changes
- Do NOT refactor unrelated parts of the system
- Do NOT redesign architecture unless explicitly requested
- If unsure about impact, ask before modifying
- Explain non-trivial changes before implementing

---

## Anti-Patterns (MUST AVOID)

- Generating LaTeX directly in LLM outputs
- Mixing parsing, analysis, and generation logic
- Hardcoding rules instead of using configuration files
- Bypassing the Generator layer
- Large-scale rewrites without justification

---

## Development Commands

### Running the Tool
```bash

# Activate virtual environment
source .venv/bin/activate

# Main analysis command
python -m src.cli analyze

# With custom files
python -m src.cli analyze --draft my_paper.tex --comments my_rules.txt --output my_review.tex

# Specify LLM provider
python -m src.cli analyze --provider deepseek --model deepseek-chat
python -m src.cli analyze --provider openai --model gpt-4
python -m src.cli analyze --provider anthropic --model claude-3-5-sonnet-20241022
python -m src.cli analyze --provider zhipu --model glm-4-flash

# Parse utilities
python -m src.cli parse --draft draft_example/draft.tex
python -m src.cli parse-comments --comments comments.txt
```

### Environment Setup
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Testing
```bash
# Run tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_integration.py -v
pytest tests/test_json_parser.py -v
```

## Architecture (Reference)

### Entry Point
- [src/cli.py](src/cli.py) - Click-based CLI with main `analyze` command
- [src/main.py](src/main.py) - Alternative direct entry point

### Workflow Layer
- [src/workflow/document_analyzer.py](src/workflow/document_analyzer.py) - Business logic orchestration

### Core Modules

**Parsers** ([src/parsers/](src/parsers/))
- [tex_parser.py](src/parsers/tex_parser.py) - Extracts sections, equations, tables from LaTeX
- [comments_parser.py](src/parsers/comments_parser.py) - Parses style rules from comments.txt
- [keywords_parser.py](src/parsers/keywords_parser.py) - Parses user-defined terminology

**LLM Clients** ([src/llm/](src/llm/))
- [base_client.py](src/llm/base_client.py) - Abstract base class with shared methods and abstract interface
- [json_parser.py](src/llm/json_parser.py) - Robust JSON extraction from LLM responses
- [deepseek_client.py](src/llm/deepseek_client.py) - DeepSeek implementation
- [openai_client.py](src/llm/openai_client.py) - OpenAI implementation
- [anthropic_client.py](src/llm/anthropic_client.py) - Anthropic implementation
- [zhipu_client.py](src/llm/zhipu_client.py) - Zhipu implementation
- [analysis_state.py](src/llm/analysis_state.py) - Global state for two-pass analysis

**Generators** ([src/generators/](src/generators/))
- [review_generator.py](src/generators/review_generator.py) - Generates LaTeX review.tex output

**Configuration** ([config/](config/))
- [settings.py](config/settings.py) - Environment-based settings dataclass

### Analysis Modes

**Two-Pass Mode** (TWO_PASS_MODE=true, recommended)
1. **Phase 1**: Lightweight scan of all sections to extract terminology and potential issues
2. **Phase 2**: Detailed analysis with global context (terminology consistency, duplicate detection)

**Single-Pass Mode** (TWO_PASS_MODE=false)
- Direct section-by-section analysis (faster but may lack global consistency)

### Output Format

Generated [review.tex](review.tex) uses `\begin{reviewer}...\end{reviewer}` blocks with:
- Category, Rule ID, Severity
- Location (section number + position)
- Source context (lstlisting)
- Reviewer comment
- Suggested revision (lstlisting)

## Key Configuration Files

- [.env](.env) - API keys, model selection, analysis mode settings
- [comments.txt](comments.txt) - Style rules (Language, Typography, Equations, etc.)
- [keywords.txt](keywords.txt) - Domain-specific terms for AI focus
- [draft_example/draft.tex](draft_example/draft.tex) - Example input paper
- [output_template/review_template.tex](output_template/review_template.tex) - LaTeX output template

## Adding a New LLM Provider

1. Create client class in [src/llm/](src/llm/) inheriting from `BaseLLMClient`
2. Implement the 4 abstract methods:
   - `_get_provider_name()` - Return provider name string
   - `_make_api_call()` - Execute provider-specific API call
   - `_extract_content()` - Extract text from response
   - `_extract_usage()` - Return standardized token usage dict
3. Add import and factory entry in [src/llm/__init__.py](src/llm/__init__.py)
4. Add config fields in [config/settings.py](config/settings.py)
5. Add to CLI choices in [src/cli.py](src/cli.py)

## Important Patterns
- Response caching (responses_cache/)
- Rate limiting with retry
- LaTeX escaping via ReviewGenerator
- Automatic section numbering
- JSON parsing with explicit error handling
