"""Retrieval-augmented metadata lookup for NLQ-to-SQL."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

# ChromaDB for embeddings; fallback to simple text matching if unavailable
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    EMBED_AVAILABLE = True
except ImportError:
    EMBED_AVAILABLE = False


class MetadataRetriever:
    """Retrieve relevant datasets/tables/definitions for a natural language question."""

    def __init__(
        self,
        db_path: str | Path,
        chroma_dir: str | Path | None = None,
        top_k: int = 3,
    ):
        self.db_path = Path(db_path)
        self.chroma_dir = Path(chroma_dir) if chroma_dir else self.db_path.parent / "chroma_db"
        self.top_k = top_k
        self._model = None
        self._chroma_client = None
        self._collection = None

    def _get_embedding_model(self):
        if not EMBED_AVAILABLE:
            return None
        if self._model is None:
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
        return self._model

    def _get_chroma(self):
        if not CHROMA_AVAILABLE or not EMBED_AVAILABLE:
            return None
        if self._chroma_client is None:
            self.chroma_dir.mkdir(parents=True, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(
                path=str(self.chroma_dir),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = self._chroma_client.get_or_create_collection(
                "nlq_metadata",
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def _ensure_embeddings(self, conn: sqlite3.Connection) -> None:
        """Build embeddings from metadata if collection is empty."""
        coll = self._get_chroma()
        if coll is None:
            return
        if coll.count() > 0:
            return
        model = self._get_embedding_model()
        if model is None:
            return
        texts, ids, metadatas = [], [], []
        for row in conn.execute("""
            SELECT dataset_id, dataset_name, domain, description
            FROM nlq_dataset_registry
        """):
            did, dname, domain, desc = row
            text = f"Dataset {dname} ({domain}): {desc}"
            texts.append(text)
            ids.append(f"ds_{did}")
            metadatas.append({"type": "dataset", "dataset_id": did})
        for row in conn.execute("""
            SELECT r.dataset_id, r.schema_name, r.table_name, r.table_desc
            FROM nlq_table_registry r
        """):
            did, schema, tbl, desc = row
            text = f"Table {schema}.{tbl}: {desc}"
            texts.append(text)
            ids.append(f"t_{did}_{schema}_{tbl}")
            metadatas.append({"type": "table", "dataset_id": did, "schema": schema, "table": tbl})
        for row in conn.execute("""
            SELECT dataset_id, term, definition FROM nlq_domain_definitions
        """):
            did, term, definition = row
            text = f"Definition {term}: {definition}"
            texts.append(text)
            ids.append(f"def_{did}_{term}")
            metadatas.append({"type": "definition", "dataset_id": did, "term": term})
        if texts:
            embeddings = model.encode(texts).tolist()
            coll.add(ids=ids, embeddings=embeddings, metadatas=metadatas)

    def retrieve(self, question: str) -> list[dict[str, Any]]:
        """
        Return top-k datasets with scores. Each item has dataset_id, label, why, score.
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        self._ensure_embeddings(conn)

        coll = self._get_chroma()
        if coll is not None and EMBED_AVAILABLE:
            model = self._get_embedding_model()
            qemb = model.encode([question]).tolist()
            res = coll.query(query_embeddings=qemb, n_results=min(15, coll.count()))
            metas = res.get("metadatas") or [[]]
            dists = res.get("distances") or [[]]
            meta_list = metas[0] if metas else []
            dist_list = dists[0] if dists else []
            dataset_scores: dict[str, float] = {}
            dataset_info: dict[str, dict] = {}
            for meta, dist in zip(meta_list, dist_list):
                did = meta.get("dataset_id", "")
                score = 1 - (dist or 0)
                dataset_scores[ did ] = dataset_scores.get(did, 0) + score
                if did not in dataset_info:
                    for r in conn.execute(
                        "SELECT dataset_name, description FROM nlq_dataset_registry WHERE dataset_id = ?",
                        (did,),
                    ):
                        dataset_info[did] = {"name": r[0], "desc": r[1]}
                        break
            sorted_ds = sorted(dataset_scores.items(), key=lambda x: -x[1])[: self.top_k]
            conn.close()
            return [
                {
                    "dataset_id": did,
                    "label": dataset_info.get(did, {}).get("name", did),
                    "why": dataset_info.get(did, {}).get("desc", ""),
                    "score": round(score, 4),
                }
                for did, score in sorted_ds
            ]

        # Fallback: simple keyword match
        ql = question.lower()
        candidates = []
        for row in conn.execute("""
            SELECT dataset_id, dataset_name, description FROM nlq_dataset_registry
        """):
            did, name, desc = row
            text = f"{name} {desc}".lower()
            score = sum(1 for w in ql.split() if len(w) > 2 and w in text) / max(len(ql.split()), 1)
            if score > 0:
                candidates.append((did, name, desc, score))
        conn.close()
        candidates.sort(key=lambda x: -x[3])
        return [
            {"dataset_id": c[0], "label": c[1], "why": c[2], "score": round(c[3], 4)}
            for c in candidates[: self.top_k]
        ]


def get_grounding_payload(
    conn: sqlite3.Connection,
    dataset_id: str,
) -> dict[str, Any]:
    """Build schema/context payload for SQL generation."""
    datasets = list(
        conn.execute(
            "SELECT dataset_name, domain, description, grain "
            "FROM nlq_dataset_registry WHERE dataset_id = ?",
            (dataset_id,),
        )
    )
    tables = list(
        conn.execute(
            """SELECT schema_name, table_name, table_desc, primary_keys, join_hints,
                      important_cols, example_filters
               FROM nlq_table_registry WHERE dataset_id = ?""",
            (dataset_id,),
        )
    )
    definitions = list(
        conn.execute(
            "SELECT term, definition, formula_sql FROM nlq_domain_definitions WHERE dataset_id = ?",
            (dataset_id,),
        )
    )
    return {
        "dataset": dict(zip(["name", "domain", "description", "grain"], datasets[0])) if datasets else {},
        "tables": [
            {
                "schema": t[0],
                "table": t[1],
                "desc": t[2],
                "primary_keys": t[3],
                "join_hints": t[4],
                "important_cols": t[5],
                "example_filters": t[6],
            }
            for t in tables
        ],
        "definitions": [{"term": d[0], "definition": d[1], "formula_sql": d[2]} for d in definitions],
    }
