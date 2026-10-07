# AI Lead Discovery & Research Agent

FastAPI service that discovers, researches, qualifies and drafts outreach for B2B
leads using Groq (LLM stages) and Tavily (web search), then returns only the leads
that pass validation.

## Stack

- **API:** FastAPI + Uvicorn
- **Agents:** LangGraph (11-node pipeline)
- **LLM:** Groq (`langchain-groq`)
- **Search:** Tavily
- **Page research:** httpx + BeautifulSoup

## Pipeline

```text
POST /api/leads/discover
  ├─ generate_search_queries   Groq structured output, 3-5 queries
  ├─ discover_leads            Tavily fan-out (one search per query)
  ├─ deduplicate_leads         domain normalize, content-platform denylist, first-wins
  ├─ research_websites         concurrent fetch of each company homepage
  ├─ extract_companies         Groq: name, industry, location, size, summary, signals
  ├─ qualify_icp               Groq: qualified flag + 0-100 fit score
  ├─ score_leads               Groq: 0-100 score + A/B/C tier (qualified leads only)
  ├─ detect_opportunities      Groq: pain points, buying signals, recommended service
  ├─ generate_outreach         Groq: subject + personalized body (+ local fallback)
  ├─ validate_leads            drop duplicates, invalid URLs and unqualified leads
  └─ finalize_leads            sort by score, apply limit, build funnel
```

Every stage writes its output to its own state key (`candidates`,
`researched_leads`, `extracted_leads`, `qualified_leads`, `scored_leads`,
`opportunity_leads`, `outreach_leads`, `validated_leads`, `leads`), so the funnel
can be inspected at any point.

LLM stages call the model in small chunks (`LLM_BATCH_SIZE`) so each request stays
below provider token limits, and a failed stage is logged in `errors` while the
rest of the pipeline continues with sensible defaults.

## Setup

```bash
# 1. Create virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux
# Then set real GROQ_API_KEY and TAVILY_API_KEY values
```

## Run

```bash
cd backend
uvicorn app.main:app --reload
```

API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

`.env` is loaded from the project root regardless of working directory.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `GROQ_API_KEY` | – | required |
| `TAVILY_API_KEY` | – | required |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | model used by every LLM stage |
| `MAX_SEARCH_RESULTS` | `5` | Tavily results per query |
| `MAX_RETRIES` | `2` | retries per LLM call (with backoff) |
| `RETRY_BACKOFF` | `2.0` | seconds before the first retry |
| `MAX_RESEARCH_LEADS` | `12` | candidates sent to website research |
| `RESEARCH_CONCURRENCY` | `5` | parallel page fetches |
| `RESEARCH_TIMEOUT` | `10.0` | per-page fetch timeout (seconds) |
| `RESEARCH_MAX_CHARS` | `6000` | stored text per page |
| `LLM_BATCH_SIZE` | `4` | leads per LLM request |
| `LLM_CONTEXT_CHARS` | `1200` | page text per lead (extraction stage) |
| `LLM_BRIEF_CHARS` | `400` | summary per lead (later stages) |

## API

### `GET /health`

```json
{ "status": "ok", "environment": "development" }
```

### `POST /api/leads/discover`

Request:

```json
{
  "industry": "dental clinics",
  "location": "Austin, Texas",
  "ideal_customer": "Independent dental practices with 2-10 dentists looking to modernize patient intake",
  "services": ["patient intake automation", "online appointment booking"],
  "company_size": "small business",
  "limit": 5
}
```

Response:

```json
{
  "status": "completed",
  "total_leads": 5,
  "funnel": {
    "search_queries": 4,
    "search_results": 20,
    "deduplicated": 16,
    "research_pool": 12,
    "researched": 12,
    "extracted": 12,
    "icp_qualified": 5,
    "scored": 5,
    "opportunities": 5,
    "outreach_ready": 5,
    "validated": 5,
    "final": 5
  },
  "errors": [],
  "leads": [
    {
      "domain": "smileaustindental.com",
      "company_name": "Smile Austin Dental",
      "website": "https://smileaustindental.com",
      "source_url": "https://smileaustindental.com/about",
      "industry": "dental clinic",
      "location": "Austin, Texas",
      "company_size": "small business",
      "summary": "Family dental practice offering ...",
      "technologies": ["Dentrix"],
      "signals": ["online booking"],
      "qualified": true,
      "fit_score": 88,
      "qualification_reason": "Matches size, industry and location.",
      "score": 91,
      "tier": "A",
      "score_rationale": "Strong ICP fit with clear booking pain points.",
      "pain_points": ["manual appointment intake"],
      "buying_signals": ["online booking form"],
      "recommended_service": "online appointment booking",
      "opportunity_summary": "...",
      "outreach_subject": "Idea for Smile Austin Dental",
      "outreach_body": "Hi Smile Austin Dental team, ...",
      "personalization_hook": "Noticed your online booking form."
    }
  ]
}
```

`status` is `completed`, `completed_with_errors` (partial run, some leads) or
`failed` (no leads and at least one error). `funnel` shows how many leads survived
each stage. `errors` lists per-stage failures.

Validation: `industry`/`location` min 2 chars, `ideal_customer` min 10 chars,
`services` 1-10 non-empty strings, `limit` 1-20 (default 10).

## Tests

```bash
cd backend
pytest
```

Offline tests cover schema validation, domain normalization, deduplication,
validation/finalization, the full graph with mocked LLM + search + fetch, and the
HTTP routes (no live API calls).

## Project Layout

```text
backend/app/
├── main.py                 # FastAPI entry
├── config.py               # pydantic-settings (loads project-root .env)
├── agents/
│   ├── state.py            # Request/response models + LeadDiscoveryState
│   ├── schemas.py          # Structured-output schemas for the LLM stages
│   ├── graph.py            # Cached LangGraph pipeline (11 stages)
│   ├── nodes.py            # Node logic (all 11 stages)
│   └── llm.py              # Cached Groq client + retry/backoff helper
├── api/
│   ├── routes.py           # POST /api/leads/discover
│   └── schemas.py          # Re-exports from agents.state
└── tools/
    ├── tavily_search.py    # Tavily web search wrapper
    └── fetch_page.py       # Concurrent page fetch + text extraction
```
