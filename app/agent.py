"""NLQ-to-SQL LangChain Agent."""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Optional

from app.retrieval import MetadataRetriever, get_grounding_payload
from app.sql_guardrails import add_limit_if_missing, validate_sql

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain_core.messages import HumanMessage, SystemMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False


SYSTEM_PROMPT = """You are a SQL expert for mortgage and credit analytics. Generate ONLY read-only SELECT queries.

RULES:
- Use ONLY the tables, columns, and schema provided in the context.
- Do NOT invent columns or tables.
- Output valid SQLite-compatible SQL.
- Always include a LIMIT (default 1000) unless the user specifies otherwise.
- For time-series data, filter by date/period when the question implies a time range (e.g. "last year", "2024", "Q3").
- Return your response in this exact JSON format:
{"sql": "SELECT ...", "assumptions": ["list of assumptions"], "tables_used": ["table1", "table2"], "explanation": "brief explanation"}

If the question cannot be answered with the provided schema, return:
{"sql": null, "needs_clarification": true, "clarifying_question": "Your question here"}
"""


def _extract_sql_from_response(text: str) -> tuple[str | None, dict | None, bool, str | None]:
    """Extract SQL and metadata from LLM response."""
    text = text.strip()
    # Try JSON block
    json_match = re.search(r"\{[^{}]*\"sql\"[^{}]*\}", text, re.DOTALL)
    if json_match:
        try:
            obj = json.loads(json_match.group())
            if obj.get("needs_clarification"):
                return None, None, True, obj.get("clarifying_question")
            sql = obj.get("sql")
            meta = {k: obj[k] for k in ["assumptions", "tables_used", "explanation"] if k in obj}
            return sql, meta, False, None
        except json.JSONDecodeError:
            pass
    # Try code block
    code_match = re.search(r"```(?:sql)?\s*([\s\S]*?)```", text)
    if code_match:
        sql = code_match.group(1).strip()
        return sql, {}, False, None
    # Try raw SELECT
    if "SELECT" in text.upper():
        start = text.upper().index("SELECT")
        sql = text[start:].split(";")[0].strip()
        if sql:
            return sql + ";" if not sql.endswith(";") else sql, {}, False, None
    return None, None, False, "Could not extract SQL from response"


class NLQAgent:
    """Natural Language to SQL agent."""

    def __init__(
        self,
        db_path: str | Path,
        chroma_dir: str | Path | None = None,
        openai_api_key: str | None = None,
    ):
        self.db_path = Path(db_path)
        self.retriever = MetadataRetriever(self.db_path, chroma_dir, top_k=3)
        self.openai_api_key = openai_api_key
        self._llm = None

    def _get_llm(self):
        if not LANGCHAIN_AVAILABLE:
            return None
        if self._llm is None and self.openai_api_key:
            self._llm = ChatOpenAI(
                model="gpt-4o-mini",
                api_key=self.openai_api_key,
                temperature=0,
            )
        return self._llm

    def _build_context(self, dataset_id: str) -> str:
        conn = sqlite3.connect(str(self.db_path))
        payload = get_grounding_payload(conn, dataset_id)
        conn.close()
        lines = []
        ds = payload.get("dataset", {})
        if ds:
            lines.append(f"Dataset: {ds.get('name', '')} ({ds.get('domain', '')})")
            lines.append(f"Description: {ds.get('description', '')}")
            lines.append(f"Grain: {ds.get('grain', '') or 'N/A'}")
        for t in payload.get("tables", []):
            lines.append(f"\nTable: {t.get('schema','')}.{t.get('table','')}")
            lines.append(f"  Description: {t.get('desc','')}")
            lines.append(f"  Columns: {t.get('important_cols','')}")
            if t.get("example_filters"):
                lines.append(f"  Example filters: {t.get('example_filters')}")
        for d in payload.get("definitions", []):
            lines.append(f"\nDefinition - {d.get('term','')}: {d.get('definition','')}")
        return "\n".join(lines)

    def execute_sql(self, sql: str) -> tuple[list[dict], list[str]]:
        """Execute SQL and return rows + column names."""
        sql = add_limit_if_missing(sql)
        ok, err = validate_sql(sql)
        if not ok:
            raise ValueError(err)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.execute(sql)
        cols = [d[0] for d in cur.description] or []
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        # Convert non-JSON-serializable types
        def _serialize(obj):
            if hasattr(obj, "isoformat"):
                return obj.isoformat()
            return obj
        rows = [{k: _serialize(v) for k, v in r.items()} for r in rows]
        return rows, cols

    def query(
        self,
        question: str,
        dataset_id: Optional[str] = None,
        disambiguation_threshold: float = 0.15,
    ) -> dict[str, Any]:
        """
        Process NLQ. Returns dict with status, choices (if disambiguation),
        or sql/results/explanation (if success).
        """
        candidates = self.retriever.retrieve(question)
        if not candidates:
            return {
                "status": "error",
                "message": "No matching datasets found. Try rephrasing your question.",
            }

        # Auto-select or disambiguate
        scores = [c["score"] for c in candidates]
        if dataset_id:
            selected = next((c for c in candidates if c["dataset_id"] == dataset_id), candidates[0])
        elif len(scores) >= 2 and (scores[0] - scores[1]) < disambiguation_threshold:
            return {
                "status": "needs_selection",
                "choices": [
                    {"dataset_id": c["dataset_id"], "label": c["label"], "why": c["why"]}
                    for c in candidates[:3]
                ],
                "message": "Which data source should I use?",
            }
        else:
            selected = candidates[0]

        resolved_dataset = selected["dataset_id"]
        context = self._build_context(resolved_dataset)

        llm = self._get_llm()
        if llm is None:
            # Fallback: simple template-based SQL for known patterns
            return self._fallback_sql(question, resolved_dataset, context)

        prompt = f"""Context:
{context}

User question: {question}

Generate a SQL query. Respond with JSON only."""

        msg = llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)])
        response_text = msg.content if hasattr(msg, "content") else str(msg)
        sql, meta, needs_clar, clar_q = _extract_sql_from_response(response_text)

        if needs_clar and clar_q:
            return {"status": "needs_clarification", "clarifying_question": clar_q}

        if not sql:
            return {
                "status": "error",
                "message": meta.get("explanation", "Could not generate SQL") if meta else "Could not generate SQL",
            }

        try:
            rows, columns = self.execute_sql(sql)
        except Exception as e:
            return {
                "status": "error",
                "message": f"SQL execution failed: {str(e)}",
                "sql": sql,
                "dataset_id": resolved_dataset,
            }

        return {
            "status": "ok",
            "dataset_id": resolved_dataset,
            "sql": sql,
            "results": {"columns": columns, "rows": rows},
            "explanation": {
                "tables": meta.get("tables_used", []) if meta else [],
                "assumptions": meta.get("assumptions", []) if meta else [],
                "notes": meta.get("explanation", "") if meta else "",
            },
        }

    def _fallback_sql(self, question: str, dataset_id: str, context: str) -> dict[str, Any]:
        """Simple keyword-based SQL when LLM is unavailable."""
        q = question.lower()
        conn = sqlite3.connect(str(self.db_path))
        tables = list(
            conn.execute(
                "SELECT schema_name, table_name FROM nlq_table_registry WHERE dataset_id = ?",
                (dataset_id,),
            )
        )
        conn.close()
        if not tables:
            return {"status": "error", "message": "No tables for dataset"}
        schema, table = tables[0][0], tables[0][1]
        full_table = f"{schema}.{table}" if schema else table
        sql = f"SELECT * FROM {full_table}"
        if "delinquency" in q or "30-89" in q or "90" in q:
            if "state" in q:
                sql = f"SELECT * FROM cpfb_state_delinquency_30_89 WHERE date >= '2023-01-01' ORDER BY date DESC"
            else:
                sql = f"SELECT * FROM cpfb_metro_delinquency_30_89 WHERE date >= '2023-01-01' ORDER BY date DESC LIMIT 100"
        elif "rate" in q or "mortgage" in q:
            sql = "SELECT * FROM fred_mortgage_rates WHERE date >= '2023-01-01' ORDER BY date DESC LIMIT 100"
        elif "hpi" in q or "house price" in q or "index" in q:
            sql = "SELECT * FROM fhfa_hpi_state WHERE period >= '2023Q1' ORDER BY period DESC LIMIT 100"
        else:
            sql = f"SELECT * FROM {full_table} LIMIT 100"
        try:
            rows, columns = self.execute_sql(sql)
            return {
                "status": "ok",
                "dataset_id": dataset_id,
                "sql": sql,
                "results": {"columns": columns, "rows": rows},
                "explanation": {"tables": [table], "notes": "Fallback template SQL (LLM not configured)"},
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
