## Frontend (React + Vite + TypeScript)

Modern UI for building and evolving taxonomies with live feedback.

### Run locally
1. Create `.env`:

```env
VITE_API_URL=http://localhost:8000
```

2. Install and run:

```bash
npm install
npm run dev
# http://localhost:3000
```

### Important pieces
- `src/contexts/AuthContext.tsx`: Auth state, Google login redirect, token handling.
- `src/lib/api.ts`: Axios client, token refresh, REST APIs, WebSocket client (`WSConnection`).
- `src/pages/*`: App screens (Login, Home, Manage Items/Taxonomies, Initialize Nodes, etc.).
- `src/components/*`: Visualization and control components (live updates panel, node and item details, etc.).
- `src/components/ui/*`: shadcn/ui primitives.

### Authentication flow
- Clicking "Continue with Google" redirects to `VITE_API_URL/api/v1/auth/google/login/redirect`.
- Backend completes OAuth and redirects back to the frontend with tokens at `/auth/callback`.
- Tokens are stored via `TokenManager`; API client adds `Authorization` headers and proactively refreshes access tokens.

### WebSockets
- Frontend connects to `ws://localhost:8000/api/v1/ws/connect?token=ACCESS_TOKEN`.
- Events drive live UI: initialization, classification, examination, and DSPy optimization updates.

### Lint & Build
```bash
npm run lint
npm run build
npm run preview
```

