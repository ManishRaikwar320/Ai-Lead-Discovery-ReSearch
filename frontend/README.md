# LeadFinder AI — Frontend

Dark, LeadFinder-style dashboard (React + Vite + TypeScript) for the FastAPI backend in `../backend`.

## Run

```bash
# terminal 1 — backend (from ../backend)
uvicorn app.main:app --reload

# terminal 2 — frontend (this folder)
npm install
npm run dev
```

Opens at http://localhost:5173. Other scripts: `npm run build`, `npm run lint`, `npm run preview`.

> Scripts invoke `node ./node_modules/...` directly instead of the `.bin` shims because the project path contains `&`, which breaks cmd-based npm shims on Windows.

## Configuration

The API base URL defaults to `http://127.0.0.1:8000` and can be overridden with an env var:

```bash
# .env.local
VITE_API_BASE_URL=http://localhost:8000
```

CORS is allowed for `localhost:5173` / `4173` by the backend middleware in `backend/app/main.py`.

## Layout

| Path | Purpose |
|---|---|
| `src/api/types.ts` | Types mirroring the Pydantic schemas (`LeadDiscoveryRequest`, `Lead`, `LeadDiscoveryResponse`, `Funnel`) |
| `src/api/client.ts` | `discoverLeads()` / `checkHealth()`, 422 field-error parsing, API base override (`localStorage: leadfinder.apiBase`) |
| `src/validation.ts` | Client-side validation mirroring backend constraints |
| `src/utils.ts` | Avatar/initials helpers, CSV + JSON export |
| `src/components/Sidebar.tsx` | Brand, 6 working nav sections, saved-leads badge, API health card |
| `src/components/TopBar.tsx` | Live search, pipeline status pill, API health pill, docs link |
| `src/components/DiscoveryForm.tsx` | Hero discover bar (industry + location + CTA), quick-filter chips, brief card (ICP, services, limit 1–20) |
| `src/components/StatsRow.tsx` | 4 stat cards computed from the last response (leads, avg match, opportunities, outreach ready) |
| `src/components/ProgressPanel.tsx` | Cancellable loading state for the long-running request |
| `src/components/ResultsTable.tsx` | Tabs (All / High Match 90%+ / Tier A / Saved), row select, save, view summary, export |
| `src/components/LeadPanel.tsx` | Inline right panel: AI summary, signals, pain points, score rationale, outreach draft + copy |
| `src/components/FunnelChart.tsx` | 12-stage pipeline funnel |

## Notes

- `POST /api/leads/discover` is synchronous and can take 30 s–several minutes; the UI shows a cancellable progress state (AbortController).
- Stage warnings arrive in `errors[]` even on HTTP 200 (`status: completed_with_errors`) and are rendered as a warning banner.
- Saved leads persist in `localStorage` (`leadfinder.saved`); exports are generated client-side (CSV/JSON).
- Responsive: the inline right panel becomes an overlay below 1240px; the sidebar collapses to an icon bar below 900px.
