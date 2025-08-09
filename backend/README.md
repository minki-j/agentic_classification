## Backend (FastAPI + LangGraph)

The backend exposes a REST and WebSocket API for taxonomy creation, item classification, and structure evolution.

### Key features
- Google OAuth login and JWT issuance
- User‑scoped items and taxonomies in MongoDB
- Classification flows powered by LangGraph (multi‑model voting)
- Examination flows to improve weak nodes
- Real‑time progress via WebSockets

### Run locally
1. Create `.env`:

```env
LOG_LEVEL=info
SECRET_KEY=change-me
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=taxonomy_agent
BACKEND_CORS_ORIGINS=["http://localhost:3000"]
FRONTEND_URL=http://localhost:3000

GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback

OPENAI_API_KEY=
ANTHROPIC_API_KEY=
```

2. Install and run:

```bash
uv sync
uv run python main.py
# http://localhost:8000 | Swagger: http://localhost:8000/docs
```

### Important modules
- `app/main.py`: FastAPI app, CORS, sessions, router includes, lifespan DB init/close.
- `app/core/config.py`: Settings via `pydantic-settings`. Reads `.env`.
- `app/core/security.py`: JWT create/verify, password hashing.
- `app/db/database.py`: Motor/Mongo init, collection helpers, indexes.
- `app/api/v1/endpoints/*`: REST endpoints for auth, users, taxonomies, items, nodes, classification.
- `app/websocket/manager.py` and `app/api/v1/endpoints/websocket.py`: WebSocket connection management and endpoint.
- `app/services/classifier_service.py`: Orchestrates LangGraph runs, DB updates, and WebSocket events.
- `agents/*`: LangGraph graphs and shared state/models.

### Classification lifecycle (high‑level)
1. Initialize nodes: `/api/v1/nodes/initial` builds a first taxonomy from sample items.
2. Classify: `/api/v1/classification/classify` batches unclassified items; multiple LLMs vote; aggregates to nodes; writes back to DB.
3. Human feedback: verify/unverify, add/remove classifications, curate few‑shot examples.

### WebSockets
- Connect: `ws://localhost:8000/api/v1/ws/connect?token=ACCESS_TOKEN`
- Server emits message types: `initialization_update`, `classification_update`, `examination_update`, `dspy_update`, `error`, plus periodic `ping`.

### Tests
Run with:
```bash
uv run pytest -q
```

