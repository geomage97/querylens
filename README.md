# QueryLens

**Chat with your database.** Connect a MongoDB database (PostgreSQL coming next), let QueryLens discover its schema automatically, and ask questions in plain language — get back answers, the exact query that ran, and chart-ready data.

> Built with FastAPI + Claude (`claude-opus-4-8`) with prompt caching, streaming responses, and strict read-only query enforcement.

## Quick start

```bash
cp .env.example .env          # add your ANTHROPIC_API_KEY
docker compose --profile seed up seed   # seed the demo e-commerce database (first time only)
docker compose up backend
```

Then ask a question:

```bash
curl -s localhost:8000/chat -X POST -H "Content-Type: application/json" \
  -d '{"question": "What is the average order value per country?"}'
```

Or stream it (Server-Sent Events):

```bash
curl -N localhost:8000/chat/stream -X POST -H "Content-Type: application/json" \
  -d '{"question": "Top 5 products by revenue"}'
```

## What it does

- **Automatic schema discovery** — samples documents from every collection and infers field paths, types, example values, and enum-like fields. No manual schema metadata.
- **Read-only by design** — every generated query passes a validator before execution; write operations, dangerous operators (`$where`, `$out`, `$merge`, ...), and unknown collections are blocked.
- **Self-correction** — if a generated query fails validation or execution, the error is fed back to the model for one corrected attempt.
- **Streaming** — `/chat/stream` emits SSE events: pipeline status, the generated query, answer tokens as they're written, then the full result.
- **Prompt caching** — the schema-aware system prompt is sent as a cached content block, cutting cost and latency on repeated questions.
- **Multiple connections** — register any reachable MongoDB instance via `POST /connections`; a seeded demo e-commerce database ships in the compose file.
- **Observability** — every interaction is logged with tokens, latency, and outcome; `/health` reports aggregate stats. A 50-case evaluation suite measures pass rates per category.

## API

| Method | Path | Description |
|---|---|---|
| POST | `/chat` | Ask a question (JSON response) |
| POST | `/chat/stream` | Ask a question (SSE: `status`, `query`, `delta`, `result`, `done`) |
| GET | `/connections` | List registered connections (credentials masked) |
| POST | `/connections` | Register + test a new connection |
| POST | `/connections/{id}/test` | Re-test a connection |
| DELETE | `/connections/{id}` | Remove a connection |
| GET | `/connections/{id}/schema` | The auto-discovered schema (`?refresh=true` to re-infer) |
| GET | `/sessions` | Recent conversations |
| DELETE | `/sessions/{id}` | Delete a conversation |
| GET | `/health` | Service health + query stats |

## Architecture

```
backend/app/
├── connectors/        # The core abstraction: one class per database engine
│   ├── base.py        #   discover_schema / validate_query / execute / prompt material
│   ├── mongodb.py     #   MongoDB: schema inference by $sample, read-only validator
│   └── registry.py    #   Connection store + connector/schema caches
├── llm/
│   ├── pipeline.py    # question -> query -> validate -> execute -> streamed answer
│   ├── prompts.py     # engine-agnostic prompt templates
│   └── json_parser.py # strict JSON extraction from model output
├── api/               # FastAPI routes + Pydantic models
└── store/             # conversations + query logs (app's own MongoDB)
```

The LLM pipeline never touches a database directly — everything goes through the connector interface, so adding PostgreSQL (Phase 2) means implementing one class.

## Evaluation

With the backend running:

```bash
cd backend && python -m eval.run_eval
```

50 test cases across categories (basic queries, aggregations, time series, memory/follow-ups, multilingual, security, edge cases), reporting per-category pass rates, p50/p95 latency, and cache hit ratio.

## Local development

```bash
cd backend
pip install -r requirements.txt
python seed/seed_ecommerce.py --drop        # needs a local MongoDB
uvicorn app.main:app --reload --port 8000
```

## Roadmap

- [x] **Phase 1** — MongoDB connector, schema inference, SSE streaming, self-correction, eval suite
- [ ] **Phase 2** — PostgreSQL connector (SQL generation + `information_schema` discovery)
- [ ] **Phase 3** — Next.js frontend: chat, connections manager, schema explorer, query inspector
- [ ] **Phase 4** — Charts (Recharts), pin-to-dashboard, saved queries
- [ ] **Phase 5** — CI, tests, demo GIF, v1.0
