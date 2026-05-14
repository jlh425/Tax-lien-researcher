# Aloha

Tax lien and deed research platform powered by AI agents.

Aloha automates the labor-intensive process of researching tax lien and tax deed
properties across US counties. It combines a multi-agent AI system with web
scraping, public records search, and structured data pipelines to produce
investment-ready research reports.

## Architecture

```
Frontend (React + TypeScript + Vite)
    |
FastAPI REST API
    |
 Services / Repositories
    |
 +-----------+-----------+-----------+
 | PostgreSQL |   Redis   |  Qdrant   |
 +-----------+-----------+-----------+
    |
 12 AI Agents (Pydantic AI, queue-orchestrated)
    |
 +--------+--------+--------+
 | Scrapers | MCP Servers | LLMs |
 +--------+--------+--------+
```

**Backend** -- Python 3.12+ / FastAPI / SQLAlchemy async / PostgreSQL / Redis / Qdrant

**Frontend** -- React + TypeScript + Vite + TanStack Query

**AI Agents** -- 12 specialized agents orchestrated via a research queue:
orchestrator, discovery, parcel research, owner research, entity research,
contact research, zoning, enrichment, scoring, report, database, and outreach.

**Scrapers** -- 3-tier architecture: API-first, vendor Playwright, adaptive LLM fallback.
Includes circuit breakers, rate limiting, and stealth capabilities.

**MCP Servers** -- 8 Model Context Protocol servers for county assessor, GIS,
court records, UCC filings, Secretary of State, people data, image capture,
and outreach integrations.

**LLM Support** -- Configurable per-agent: Anthropic, OpenAI, Ollama (local), Groq,
or any OpenAI-compatible API. Mix providers freely across agents.

## Quick Start

```bash
# Install dependencies, pre-commit hooks, and Playwright
make install

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your API keys and database credentials

# Start all services (PostgreSQL, Redis, Qdrant, API, frontend)
make dev

# Run database migrations
make migrate

# Seed reference data
make seed

# Run tests
make test
```

## Key Features

- **Automated property research** -- scan a county and get structured reports on
  tax lien/deed parcels with owner info, entity details, zoning, and scoring
- **Multi-agent pipeline** -- 12 AI agents handle different research phases,
  communicating via an async queue system
- **LLM-agnostic** -- swap providers per agent; use Claude for complex reasoning,
  local Ollama for simple tasks, Groq for speed
- **3-tier scraping** -- graceful fallback from APIs to headless browsers to
  LLM-driven adaptive scraping
- **Court records and UCC search** -- integrated lookup for liens, judgments,
  and UCC filings
- **Export and outreach** -- generate PDF/CSV reports and manage owner outreach

## Tech Stack

| Layer        | Technology                                       |
|--------------|--------------------------------------------------|
| Language     | Python 3.12+, TypeScript                         |
| Web framework| FastAPI (async)                                  |
| Frontend     | React 18, Vite, TanStack Query, Tailwind CSS     |
| ORM          | SQLAlchemy 2.x (async)                           |
| Database     | PostgreSQL + Qdrant (vector search)              |
| Cache/Queue  | Redis, Celery                                    |
| AI framework | Pydantic AI                                      |
| Scraping     | Playwright, httpx, Docling                       |
| Migrations   | Alembic                                          |
| Testing      | pytest, Vitest, React Testing Library            |

## Environment Setup

Copy `.env.example` to `.env` and configure:

- **Database**: `DATABASE_URL` (PostgreSQL connection string)
- **Redis**: `REDIS_URL`
- **Qdrant**: `QDRANT_URL`
- **LLM**: `LLM_PROVIDER` and `LLM_MODEL` for the global default
- **Per-agent LLM overrides**: `LLM_AGENT_<NAME>=provider:model`
- **API keys**: provider-specific keys (ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.)
- **CORS**: `CORS_ALLOWED_ORIGINS` (comma-separated list of allowed origins)

See `.env.example` for the full list of configuration options.

## Testing

```bash
make test           # Run backend tests (pytest)
make test-cov       # Backend tests with coverage report
make lint           # ruff + mypy
make format         # Auto-fix lint issues
```

The backend test suite includes 1300+ tests across 54 test modules covering
agents, services, scrapers, API routes, MCP servers, and core infrastructure.
The frontend includes 160+ tests across 18 test modules.

## Project Structure

```
src/aloha/
  agents/          # 12 AI agent packages (agent.py, tools.py, prompts.py)
  api/             # FastAPI routes, schemas, dependencies
  core/            # LLM config, embeddings, shared utilities
  db/              # SQLAlchemy models, repositories, migrations
  mcp_servers/     # 8 Model Context Protocol servers
  scrapers/        # 3-tier scraping architecture
  services/        # Business logic layer
frontend/          # React + TypeScript SPA
tests/             # Backend tests (mirrors src/aloha/ structure)
docker/            # Docker Compose for local dev and production
```

## Development

```bash
# Create a new migration
make migrate MSG="add parcels table"

# Seed reference data
make seed

# Format and lint
make format
make lint
```

## License

Proprietary. All rights reserved.
