# AI-Financer

**Production-grade NLQ-to-SQL Agent for Mortgage & Credit Analytics**

A retrieval-augmented Natural Language Query (NLQ) → SQL system that helps analysts answer mortgage and credit analytics questions using plain English. Built for Bayview Asset Management-style mortgage investment workflows.

**Author:** Sai Santhosh V C  
**License:** MIT

### 📚 [**Full API Documentation**](docs/API.md) — Production-grade reference with examples

---

## Overview

AI-Financer accepts natural language questions, selects the appropriate dataset (CPFB delinquency, FRED mortgage rates, FHFA House Price Index), generates validated SQL, executes against SQLite, and returns results with explanations.

### Key Features

- **Multi-Source Routing**: Semantic retrieval over metadata to pick the right dataset
- **Disambiguation Flow**: When multiple datasets fit, presents top-3 choices for user selection
- **SQL Guardrails**: Read-only, whitelisted tables, required LIMIT
- **Real Data**: CFPB mortgage delinquency, FRED rates, FHFA HPI (open-source, no sampling)
- **Production Stack**: FastAPI backend, React+TypeScript UI, LangChain orchestration

---

## Architecture

```
┌─────────────────────────────────────┐
│   React + TypeScript UI             │
│   (Vite, port 5173)                 │
└─────────────────┬───────────────────┘
                  │ HTTP /api
                  ▼
┌─────────────────────────────────────┐
│   FastAPI NLQ-to-SQL API            │
│   - /nlq/query                      │
│   - /nlq/disambiguate               │
│   - /nlq/datasets                   │
└─────────────────┬───────────────────┘
                  │
    ┌─────────────┼─────────────┐
    ▼             ▼             ▼
┌──────────┐ ┌──────────┐ ┌──────────────┐
│ Retrieval │ │ LangChain│ │ SQL Guardrails│
│ (ChromaDB │ │ + OpenAI │ │ + Executor   │
│ + embed)  │ │ GPT-4o   │ │              │
└─────┬─────┘ └────┬─────┘ └──────┬───────┘
      │            │              │
      └────────────┴──────────────┘
                   │
                   ▼
         ┌──────────────────┐
         │ SQLite Database  │
         │ - CFPB data      │
         │ - FRED rates     │
         │ - FHFA HPI       │
         │ - Metadata reg.  │
         └──────────────────┘
```

### Data Flow

1. **User Question** → POST /nlq/query
2. **Retrieval** → Embed question, search metadata store (ChromaDB or keyword fallback)
3. **Dataset Selection** → Top-1 if clear winner, else return needs_selection with top-3
4. **Grounding** → Build schema payload (tables, columns, definitions) for selected dataset
5. **SQL Generation** → LangChain + GPT-4o-mini with system prompt + context
6. **Validation** → Block DML/DDL, whitelist tables, add LIMIT
7. **Execution** → Run against SQLite, return rows + columns

### Data Sources

| Source | Content | Refresh |
|--------|---------|---------|
| CFPB | State & metro % mortgages 30-89 and 90+ days delinquent | `scripts/ingest_data.py` |
| FRED | 30yr, 15yr, 5yr ARM mortgage rates (requires API key) | `scripts/ingest_data.py` |
| FHFA | House Price Index by state | `scripts/ingest_data.py` |

---

## Quick Start

### 1. Clone & Install

```bash
cd AI-Financer

# Backend
pip install -r requirements.txt

# Frontend
cd frontend && npm install
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env:
#   OPENAI_API_KEY=sk-...     # Required for full LLM SQL generation (falls back to templates without)
#   FRED_API_KEY=...          # Optional; get at https://fred.stlouisfed.org/docs/api/api_key.html
```

**Note:** Without `OPENAI_API_KEY`, the agent uses template-based SQL for common patterns (delinquency, rates, HPI). Add your key for natural language → SQL generation.

### 3. Initialize Database & Load Data

```bash
# Create schema + metadata registry
python scripts/init_db.py

# Ingest real mortgage data from CFPB, FRED, FHFA
python scripts/ingest_data.py
```

### 4. Run

```bash
# Terminal 1: API
python run.py

# Terminal 2: UI
cd frontend && npm run dev
```

- **API:** http://localhost:8000  
- **UI:** http://localhost:5173  
- **Interactive API docs:** http://localhost:8000/docs  

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/nlq/query` | POST | Main NLQ—convert question to SQL + execute |
| `/nlq/disambiguate` | POST | Continue after dataset selection |
| `/nlq/datasets` | GET | List available datasets |
| `/nlq/history` | GET | Query history (stub) |

👉 **[Full API Documentation](docs/API.md)** — Request/response schemas, error codes, cURL/Python/JS examples, OpenAPI

---

## Project Structure

```
AI-Financer/
├── app/
│   ├── main.py         # FastAPI app
│   ├── agent.py        # NLQ agent (LangChain + retrieval)
│   ├── retrieval.py    # Metadata retriever + ChromaDB
│   ├── sql_guardrails.py
│   └── config.py
├── docs/
│   └── API.md          # Production API documentation
├── scripts/
│   ├── init_db.py      # Create schema + metadata
│   └── ingest_data.py   # Fetch CFPB, FRED, FHFA
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   └── components/
│   └── ...
├── data/               # Created at runtime
│   ├── analytics.db
│   └── chroma_db/
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Deployment

### Docker

```bash
# Build and run
docker-compose up --build

# Set env vars for LLM + FRED
export OPENAI_API_KEY=sk-...
export FRED_API_KEY=...
docker-compose up
```

### Production Notes

- Use a proper secret manager for `OPENAI_API_KEY` and `FRED_API_KEY`
- For production, replace SQLite with PostgreSQL/Redshift and update connection in `app/config.py`
- Frontend: build with `npm run build` and serve static files via nginx or API static mount

---

## Example Questions

- "What is the delinquency rate in California in 2024?"
- "Show mortgage rates for the last 6 months"
- "Average 90+ days delinquent by state in Q3 2023"
- "House price index change in Texas"

---

## License

MIT License. See [LICENSE](LICENSE) for details.
