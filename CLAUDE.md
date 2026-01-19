# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered CRM system for a construction materials company ("СтройАссортимент"). Full-stack sales automation platform with:
- AI sales consultant/chatbot (LangChain ReAct agent)
- **1C ERP integration** - real-time product catalog, prices, inventory
- Lead management and pipeline tracking
- Telegram and Email (Gmail) channel integrations
- Knowledge base management
- CRM dashboard with analytics

**Tech Stack:**
- Backend: Python 3.11+ (FastAPI, LangChain, SQLAlchemy async, aiogram)
- Frontend: Next.js 16 with React 19, TypeScript, Tailwind CSS
- Database: PostgreSQL 16, Redis 7
- LLM: OpenRouter (GPT-5-mini primary, Gemini 2.5-flash fallback)

## Commands

### Docker Compose (Recommended)
```bash
docker-compose up -d              # Start all services
docker-compose down               # Stop services
docker-compose logs -f            # View logs
docker-compose logs -f api        # Logs for specific service
docker-compose build --no-cache   # Rebuild after changes
```

### Local Development (Backend)
```bash
cd backend
uv sync                           # Install dependencies
source .venv/bin/activate         # Activate venv

# Run individual services
uv run uvicorn api:app --host 0.0.0.0 --port 5537 --reload
uv run bot.py                     # Telegram bot
uv run gmail_service.py           # Email service

# Or use the convenience script from project root
./run.sh --all                    # All services
./run.sh --ai                     # API only
./run.sh --bot                    # Bot only
./run.sh --gmail                  # Email only
```

### Local Development (Frontend)
```bash
cd frontend
npm install
npm run dev                       # Dev server on :3000
npm run build                     # Production build
npm run lint
```

### Database
```bash
# Via Docker
docker-compose exec api python -m db.init_db      # Initialize DB
docker-compose exec api python -m db.create_admin # Create admin user

# Local
python -m db.init_db
python -m db.create_admin
```

## Architecture

```
consultant/
├── backend/
│   ├── api.py        # FastAPI app entry (imports from api.py)
│   ├── api.py               # FastAPI app setup, middleware, CORS
│   ├── agent.py             # LangChain agent creation and execution
│   ├── bot.py               # Telegram bot (aiogram 3.x)
│   ├── gmail_service.py     # Email polling (IMAP) and sending (SMTP)
│   ├── auth.py              # JWT auth, password hashing, RBAC
│   ├── params_manager.py    # Singleton for prompt/KB caching
│   ├── services/
│   │   ├── ai_router.py     # /chat endpoint - agent processing
│   │   └── crm_router.py    # CRM API (leads, auth, stats, settings)
│   ├── db/
│   │   ├── models.py        # SQLAlchemy models (Lead, Thread, Message, etc.)
│   │   ├── repository.py    # Database access layer
│   │   └── session.py       # Async session factory
│   ├── tools/               # LangChain tools for agent
│   ├── schemas/             # Pydantic models
│   └── data/                # KB JSON, mock data
│
├── frontend/
│   ├── app/                 # Next.js App Router pages
│   │   ├── dashboard/       # Main metrics dashboard
│   │   ├── leads/           # Lead management
│   │   └── sales-manager/   # Agent config (prompt, KB editor)
│   ├── components/          # React components
│   ├── lib/                 # API client (axios), auth utils
│   └── hooks/               # Custom React hooks
│
└── docker-compose.yml       # Service orchestration
```

## Key Patterns

**Backend:**
- Async-first: all DB operations use SQLAlchemy async with `asyncpg`
- `ParamsManager` singleton loads prompt/KB from DB, call `reload()` after changes
- JWT auth with 7-day expiry, RBAC via `require_roles()` decorator
- Agent uses structured output (`AgentStructuredResponse`) with category/reasoning
- LLM fallback: main model fails → backup model automatically

**Frontend:**
- App Router with middleware auth protection
- Axios interceptors handle token injection and 401 logout
- React Query for server state, Zustand for client state

**API Endpoints:**
- `/chat` - AI agent processing
- `/api/auth/*` - Authentication
- `/api/leads/*` - Lead CRUD
- `/api/stats/*` - Dashboard metrics
- `/api/settings/*` - KB and prompt management

**1C Integration:**
- See [docs/1C_API_QUICK_REFERENCE.md](docs/1C_API_QUICK_REFERENCE.md) for API quick reference
- See [docs/1C_INTEGRATION_DESIGN.md](docs/1C_INTEGRATION_DESIGN.md) for full integration architecture
- Agent tools: `search_product_groups`, `get_category_items`, `get_product_details`
- Catalog cached in Redis (TTL 1 hour) for performance

## Port Mapping
- Frontend: 3000
- Backend API: 5537 (localhost:15537 in Docker)
- PostgreSQL: 5433 (internal 5432)
- Redis: 6379 (internal only)

## Environment Variables

Copy `.env.example` to `.env` and configure:
- `BOT_TOKEN` - Telegram bot token
- `OPENAI_API_KEY` - OpenRouter API key
- `SMTP_USER`, `SMTP_PASSWORD` - Gmail credentials (app password)
- `JWT_SECRET` - Change in production
- `ADMIN_USERNAME`, `ADMIN_PASSWORD` - Initial admin credentials
- `ONEC_BASE_URL` - 1C API base URL
- `ONEC_USERNAME`, `ONEC_PASSWORD` - 1C authentication credentials
