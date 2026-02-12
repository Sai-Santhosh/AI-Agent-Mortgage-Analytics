"""FastAPI application for AI-Financer NLQ-to-SQL."""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.agent import NLQAgent
from app.config import get_data_dir, get_settings

# Initialize
settings = get_settings()
data_dir = get_data_dir()
db_path = data_dir / "analytics.db"
chroma_dir = data_dir / "chroma_db"

app = FastAPI(
    title="AI-Financer NLQ-to-SQL API",
    description="Natural Language to SQL for mortgage and credit analytics",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy agent initialization
_agent: NLQAgent | None = None


def get_agent() -> NLQAgent:
    global _agent
    if _agent is None:
        chroma = chroma_dir if chroma_dir.exists() or not chroma_dir.exists() else None
        _agent = NLQAgent(
            db_path=db_path,
            chroma_dir=chroma_dir,
            openai_api_key=settings.openai_api_key or None,
        )
    return _agent


# Request/Response models
class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Natural language question")
    user_id: str | None = Field(None, description="Optional user identifier")
    preferred_dataset: str | None = Field(None, description="Pre-selected dataset ID")
    time_zone: str | None = Field(None, description="User timezone")


class DisambiguateRequest(BaseModel):
    question: str = Field(..., min_length=1)
    dataset_id: str = Field(..., description="Selected dataset from disambiguation")
    user_id: str | None = None


@app.get("/health")
def health():
    """Health check."""
    return {"status": "ok", "service": "ai-financer"}


@app.get("/nlq/datasets")
def list_datasets():
    """List available datasets."""
    import sqlite3
    if not db_path.exists():
        return {"datasets": []}
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT dataset_id, dataset_name, domain, description FROM nlq_dataset_registry"
    ).fetchall()
    conn.close()
    return {
        "datasets": [
            {"id": r[0], "name": r[1], "domain": r[2], "description": r[3]}
            for r in rows
        ]
    }


@app.post("/nlq/query")
def nlq_query(req: QueryRequest):
    """Main NLQ endpoint."""
    if not db_path.exists():
        raise HTTPException(503, "Database not initialized. Run scripts/init_db.py and scripts/ingest_data.py")
    agent = get_agent()
    result = agent.query(
        question=req.question,
        dataset_id=req.preferred_dataset,
    )
    return result


@app.post("/nlq/disambiguate")
def nlq_disambiguate(req: DisambiguateRequest):
    """Continue after user selects dataset."""
    if not db_path.exists():
        raise HTTPException(503, "Database not initialized")
    agent = get_agent()
    result = agent.query(
        question=req.question,
        dataset_id=req.dataset_id,
    )
    return result


@app.get("/nlq/history")
def nlq_history(user_id: str | None = None, limit: int = 20):
    """Query history (stub - extend with persistence)."""
    return {"history": []}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
