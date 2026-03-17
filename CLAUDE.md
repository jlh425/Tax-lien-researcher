# Aloha — Tax Lien/Deed Research Platform

## Quick Start
```bash
make install        # Install deps + pre-commit hooks + playwright
make dev            # Start all services via docker-compose
make test           # Run pytest
make lint           # ruff + mypy
```

## Architecture
- **Backend**: Python 3.12+ / FastAPI / SQLAlchemy async / PostgreSQL / Redis
- **Frontend**: React + TypeScript + Vite + TanStack Query
- **AI Agents**: 12 Pydantic AI agents orchestrated via queue system
- **Scraping**: 3-tier architecture (API → vendor Playwright → adaptive Claude)
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
- Agents use Pydantic AI framework
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

## Key Commands
```bash
make migrate MSG="add parcels table"    # Create new migration
make seed                                # Seed reference data
make test-cov                            # Tests with coverage report
make format                              # Auto-fix lint issues
```

## Dependencies
- See `pyproject.toml` for full list
- `pip install -e ".[dev]"` for development
- `playwright install chromium` for scraping
