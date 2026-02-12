# AI-Financer API Documentation

> **Production-grade Natural Language to SQL API for Mortgage & Credit Analytics**

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## Table of Contents

- [Overview](#overview)
- [Base URL & Environment](#base-url--environment)
- [Authentication](#authentication)
- [Response Format](#response-format)
- [Error Handling](#error-handling)
- [Endpoints](#endpoints)
- [Code Examples](#code-examples)
- [OpenAPI / Swagger](#openapi--swagger)

---

## Overview

The AI-Financer API converts natural language questions into SQL queries against mortgage and credit analytics data. It supports:

| Capability | Description |
|------------|-------------|
| **Multi-dataset routing** | Automatically selects CFPB delinquency, FRED rates, or FHFA HPI |
| **Disambiguation** | When ambiguous, returns top-3 dataset choices for user selection |
| **SQL guardrails** | Read-only, whitelisted schemas, enforced `LIMIT` |
| **Real data** | CFPB, FRED, FHFA open-source datasets |

**Interactive docs:** When the API is running, visit `/docs` (Swagger UI) or `/redoc` (ReDoc).

---

## Base URL & Environment

| Environment | Base URL |
|-------------|----------|
| **Local** | `http://localhost:8001` |
| **Production** | `https://your-domain.com` (configure as deployed) |

All endpoints return **JSON**. Send `Content-Type: application/json` for POST requests.

---

## Authentication

Currently, the API does **not** require authentication. For production deployments:

- Use API keys, JWT, or OAuth as needed
- Restrict CORS origins
- Place behind a reverse proxy (nginx, etc.) with TLS

---

## Response Format

### Success (200 OK)

Responses follow the schema defined for each endpoint. Common fields:

```json
{
  "status": "ok",
  "dataset_id": "string",
  "sql": "string",
  "results": { "columns": [], "rows": [] },
  "explanation": { "tables": [], "assumptions": [], "notes": "string" }
}
```

### Error (4xx / 5xx)

```json
{
  "detail": "Error message or validation details"
}
```

---

## Error Handling

| Status Code | Meaning |
|-------------|---------|
| `200` | Success |
| `400` | Bad request (invalid JSON, validation error) |
| `422` | Validation error (e.g., empty `question`) |
| `500` | Internal server error (SQL execution failed, LLM error) |
| `503` | Service unavailable (database not initialized) |

---

## Endpoints

### `GET /health`

Health check for load balancers and monitoring.

**Response:** `200 OK`

```json
{
  "status": "ok",
  "service": "ai-financer"
}
```

---

### `GET /nlq/datasets`

List available datasets (CPFB, FRED, FHFA) and their metadata.

**Response:** `200 OK`

```json
{
  "datasets": [
    {
      "id": "cpfb_delinquency",
      "name": "CPFB Mortgage Delinquency",
      "domain": "delinquency",
      "description": "Consumer Financial Protection Bureau mortgage performance data..."
    },
    {
      "id": "fred_rates",
      "name": "FRED Mortgage Rates",
      "domain": "rates",
      "description": "Federal Reserve Economic Data - 30-year and 15-year fixed mortgage rates..."
    },
    {
      "id": "fhfa_hpi",
      "name": "FHFA House Price Index",
      "domain": "housing",
      "description": "FHFA House Price Index - measures single-family home price changes..."
    }
  ]
}
```

---

### `POST /nlq/query`

**Main NLQ endpoint.** Converts a natural language question into SQL and returns results.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `question` | string | **Yes** | Natural language question (min 1 char) |
| `preferred_dataset` | string \| null | No | Pre-selected dataset ID (skips disambiguation) |
| `user_id` | string | No | Optional user identifier for analytics |
| `time_zone` | string | No | User timezone (e.g., `America/New_York`) |

**Example Request:**

```json
{
  "question": "What is the average delinquency rate in Texas in 2024?",
  "preferred_dataset": null,
  "user_id": "user_123"
}
```

**Response (Success) – `status: "ok"`**

```json
{
  "status": "ok",
  "dataset_id": "cpfb_delinquency",
  "sql": "SELECT date, state_name, pct_30_89_days_late FROM main.cpfb_state_delinquency_30_89 WHERE state_name = 'Texas' AND date LIKE '2024-%' ORDER BY date LIMIT 1000",
  "results": {
    "columns": ["date", "state_name", "pct_30_89_days_late"],
    "rows": [
      { "date": "2024-01", "state_name": "Texas", "pct_30_89_days_late": 2.1 },
      { "date": "2024-02", "state_name": "Texas", "pct_30_89_days_late": 2.3 }
    ]
  },
  "explanation": {
    "tables": ["cpfb_state_delinquency_30_89"],
    "assumptions": ["Used 30-89 days delinquent metric", "Filtered to 2024"],
    "notes": "Query completed"
  }
}
```

**Response (Disambiguation) – `status: "needs_selection"`**

When multiple datasets match, the API returns choices instead of executing:

```json
{
  "status": "needs_selection",
  "choices": [
    {
      "dataset_id": "cpfb_delinquency",
      "label": "CPFB Mortgage Delinquency",
      "why": "Official internal definition; state + monthly grain"
    },
    {
      "dataset_id": "fred_rates",
      "label": "FRED Mortgage Rates",
      "why": "Wider coverage; weekly"
    }
  ],
  "message": "Which data source should I use?"
}
```

**Response (Clarification) – `status: "needs_clarification"`**

When the question is ambiguous:

```json
{
  "status": "needs_clarification",
  "clarifying_question": "Do you mean 30-89 days delinquent or 90+ days delinquent?"
}
```

**Response (Error) – `status: "error"`**

```json
{
  "status": "error",
  "message": "SQL execution failed: no such column: xyz",
  "sql": "SELECT ...",
  "dataset_id": "cpfb_delinquency"
}
```

---

### `POST /nlq/disambiguate`

Continue after the user selects a dataset from a `needs_selection` response.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `question` | string | **Yes** | Same question from the previous `/nlq/query` call |
| `dataset_id` | string | **Yes** | Selected dataset ID from `choices` |
| `user_id` | string | No | Optional user identifier |

**Example Request:**

```json
{
  "question": "Show delinquency by state",
  "dataset_id": "cpfb_delinquency"
}
```

**Response:** Same as `POST /nlq/query` success response.

---

### `GET /nlq/history`

Query history (stub). Returns empty array; extend with persistence for your use case.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_id` | string | — | Filter by user |
| `limit` | int | 20 | Max items to return |

**Response:** `200 OK`

```json
{
  "history": []
}
```

---

## Code Examples

### cURL

```bash
# Health check
curl http://localhost:8001/health

# List datasets
curl http://localhost:8001/nlq/datasets

# NLQ query
curl -X POST http://localhost:8001/nlq/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Show delinquency in California 2024"}'

# Disambiguate
curl -X POST http://localhost:8001/nlq/disambiguate \
  -H "Content-Type: application/json" \
  -d '{"question": "delinquency by state", "dataset_id": "cpfb_delinquency"}'
```

### Python

```python
import requests

BASE = "http://localhost:8001"

# Query
r = requests.post(f"{BASE}/nlq/query", json={
    "question": "What is the delinquency rate in Texas in 2024?",
})
data = r.json()

if data.get("status") == "ok":
    for row in data["results"]["rows"]:
        print(row)
elif data.get("status") == "needs_selection":
    for choice in data["choices"]:
        print(f"  {choice['dataset_id']}: {choice['label']}")
```

### JavaScript / Fetch

```javascript
const BASE = 'http://localhost:8001';

const res = await fetch(`${BASE}/nlq/query`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ question: 'Show mortgage delinquency by state' }),
});
const data = await res.json();

if (data.status === 'ok') {
  console.table(data.results.rows);
}
```

---

## OpenAPI / Swagger

When the API is running:

- **Swagger UI:** [http://localhost:8001/docs](http://localhost:8001/docs)
- **ReDoc:** [http://localhost:8001/redoc](http://localhost:8001/redoc)
- **OpenAPI JSON:** [http://localhost:8001/openapi.json](http://localhost:8001/openapi.json)

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-02 | Initial release. NLQ query, disambiguation, datasets, health. |

---

*AI-Financer API • Author: Sai Santhosh V C • MIT License*
