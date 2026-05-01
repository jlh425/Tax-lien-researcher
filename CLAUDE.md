# Aloha — Tax Lien/Deed Research Platform

## Quick Start
```bash
make install        # Install deps + pre-commit hooks + playwright
make dev            # Start all services via docker-compose
make test           # Run pytest
make lint           # ruff + mypy
```

## Architecture
- **Backend**: Python 3.12+ / FastAPI / SQLAlchemy async / PostgreSQL / Redis / Qdrant
- **Frontend**: React + TypeScript + Vite + TanStack Query
- **AI Agents**: 12 Pydantic AI agents orchestrated via queue system (LLM-agnostic)
- **LLM**: Configurable — Anthropic, OpenAI, Ollama (local), Groq, or any OpenAI-compatible API
- **Scraping**: 3-tier architecture (API → vendor Playwright → adaptive LLM)
- **MCP Servers**: 8 Model Context Protocol servers for external data access

## Project Structure
- `src/aloha/` — Python backend (src layout, import as `aloha`)
- `frontend/` — React SPA (standalone, communicates via REST API)
- `tests/` — Mirrors `src/aloha/` structure
- `docker/` — Docker Compose for local dev and production
- `research/` — Planning/research documents

## Conventions

### Python
- Python 3.12+ features OK (type hints, match statements, etc.)
- Use `async`/`await` throughout — FastAPI, SQLAlchemy, httpx
- Pydantic models for all data validation and API schemas
- Type hints required on all function signatures
- Use `structlog` for logging, never `print()`
- Imports: standard lib → third party → local (`aloha.*`)
- Line length: 99 chars (ruff enforced)
- Use `tenacity` for retries, not hand-rolled loops

### Database
- SQLAlchemy async ORM — never raw SQL in application code
- Repository pattern: agents/API call repos, repos call models
- Alembic for all migrations — never modify DB schema manually
- All models in `src/aloha/db/models/`, one file per domain entity

### Agents
- Each agent is a package: `agent.py`, `tools.py`, `prompts.py`
- Agents use Pydantic AI framework with configurable LLM backend
- Global default set via `LLM_PROVIDER` + `LLM_MODEL` env vars
- Per-agent overrides via `LLM_AGENT_<NAME>=provider:model` (see `.env.example`)
- `BaseAgent` auto-resolves via `aloha.core.llm.get_agent_model(name)`
- Mix providers freely — e.g. Claude for orchestrator, Ollama for database agent
- Agents communicate via the research queue, not direct calls
- All agent tools must be idempotent

### API
- FastAPI routes in `src/aloha/api/routes/`
- Pydantic schemas in `src/aloha/api/schemas/` (separate from DB models)
- Business logic in `src/aloha/services/`, not in route handlers
- Use dependency injection via `src/aloha/api/deps.py`

### Testing
- pytest + pytest-asyncio
- Test files mirror source: `tests/agents/test_orchestrator.py`
- Use factory-boy for test data (see `tests/factories.py`)
- Use respx for mocking httpx calls
- Use recorded fixtures for scraper tests

### Environment
- All config via environment variables (see `.env.example`)
- Pydantic BaseSettings in `src/aloha/config.py` — single source of truth
- Never hardcode secrets, URLs, or API keys
- LLM provider is configurable: set `LLM_PROVIDER` and `LLM_MODEL` in `.env`

### LLM Configuration
Supported providers (set `LLM_PROVIDER` in `.env`):
| Provider | `LLM_PROVIDER` | Example `LLM_MODEL` | Install extra |
|----------|----------------|----------------------|---------------|
| Anthropic | `anthropic` | `claude-sonnet-4-20250514` | `pip install -e ".[anthropic]"` |
| OpenAI | `openai` | `gpt-4o` | `pip install -e ".[openai]"` |
| Ollama (local) | `ollama` | `llama3.1:70b` | `pip install -e ".[ollama]"` |
| Groq | `groq` | `llama-3.3-70b-versatile` | `pip install -e ".[groq]"` |
| OpenAI-compatible | `openai-compatible` | `model-name` | `pip install -e ".[openai]"` |

The `openai-compatible` provider works with vLLM, LM Studio, llama.cpp server,
Together AI, and any endpoint that implements the OpenAI chat completions API.

#### Per-Agent Overrides
Each agent can use a different provider/model. Set `LLM_AGENT_<NAME>=provider:model`:
```bash
# Global default (used by agents without an override)
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:70b

# Complex agents get a more capable model
LLM_AGENT_ORCHESTRATOR=anthropic:claude-sonnet-4-20250514
LLM_AGENT_SCORING=openai:gpt-4o
LLM_AGENT_REPORT=anthropic:claude-sonnet-4-20250514

# Fast/cheap agent for simple scheduling
LLM_AGENT_DATABASE=groq:llama-3.3-70b-versatile
```
Agents without an override use the global default. See `aloha.core.llm` for resolution logic.

## Key Commands
```bash
make migrate MSG="add parcels table"    # Create new migration
make seed                                # Seed reference data
make test-cov                            # Tests with coverage report
make format                              # Auto-fix lint issues
```

### Memory Compiler
- Conversations are auto-captured into `claude-memory-compiler/daily/` logs via Claude Code hooks
- Knowledge is compiled into `claude-memory-compiler/knowledge/` articles (concepts, connections, Q&A)
- SessionStart hook injects the knowledge base index into every new session
- After 6 PM local time, daily logs auto-compile into structured knowledge articles
- Manual commands (run from project root):
  - `uv run --directory claude-memory-compiler python scripts/compile.py` — compile daily logs
  - `uv run --directory claude-memory-compiler python scripts/query.py "question"` — query KB
  - `uv run --directory claude-memory-compiler python scripts/lint.py --structural-only` — health checks
- See `claude-memory-compiler/AGENTS.md` for full schema and technical reference

## Dependencies
- See `pyproject.toml` for full list
- `pip install -e ".[dev,anthropic]"` for development with Anthropic (default)
- `pip install -e ".[dev,openai]"` for development with OpenAI/Ollama
- `pip install -e ".[dev,all-llm]"` to install all LLM provider SDKs
- `playwright install chromium` for scraping
