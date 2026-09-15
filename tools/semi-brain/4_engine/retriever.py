#!/usr/bin/env python3
"""
retriever.py
Hybrid Retriever combining BM25 (SQLite FTS5) + Dense Cosine Similarity (FastEmbed)
using Reciprocal Rank Fusion (RRF).
"""

import sqlite3
import struct
import numpy as np
from pathlib import Path
from typing import List, Dict, Any
from fastembed import TextEmbedding

SEMI_BRAIN_DIR = Path(__file__).resolve().parents[1]
DB_FILE = SEMI_BRAIN_DIR / "1_extractors" / "output" / "knowledge_index.db"

class HybridRetriever:
    def __init__(self):
        self.db_path = DB_FILE
        self._embed_model = None
        
    @property
    def embed_model(self):
        if self._embed_model is None:
            self._embed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        return self._embed_model

    def unpack_vector(self, blob: bytes) -> np.ndarray:
        num_floats = len(blob) // 4
        return np.array(struct.unpack(f"{num_floats}f", blob), dtype=np.float32)

    def bm25_search(self, query: str, limit: int = 15) -> List[Dict[str, Any]]:
        """Run BM25 search against SQLite FTS5."""
        if not self.db_path.exists():
            return []
            
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        # Clean query for FTS5 (escape quotes and special operators)
        clean_q = " OR ".join([f'"{w}"' for w in query.replace('"', '').split() if len(w) > 2])
        if not clean_q:
            clean_q = f'"{query}"'
            
        results = []
        try:
            sql = """
                SELECT doc_id, category, title, content, filepath, rank
                FROM fts_documents
                WHERE fts_documents MATCH ?
                ORDER BY rank
                LIMIT ?
            """
            for row in cur.execute(sql, (clean_q, limit)):
                results.append({
                    "doc_id": row[0],
                    "category": row[1],
                    "title": row[2],
                    "snippet": row[3][:300],
                    "filepath": row[4],
                    "bm25_rank": row[5]
                })
        except sqlite3.OperationalError:
            pass
        finally:
            conn.close()
            
        return results

    def _load_vector_cache(self):
        if hasattr(self, "_vector_cache") and self._vector_cache is not None:
            return
        if not self.db_path.exists():
            self._vector_cache = None
            return
            
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT doc_id, category, title, snippet, filepath, embedding FROM vector_documents")
        rows = cur.fetchall()
        conn.close()
        
        self._doc_meta = []
        vecs = []
        for row in rows:
            doc_id, cat, title, snippet, fpath, blob = row
            self._doc_meta.append({
                "doc_id": doc_id,
                "category": cat,
                "title": title,
                "snippet": snippet,
                "filepath": fpath
            })
            vecs.append(self.unpack_vector(blob))
            
        if vecs:
            self._vector_matrix = np.array(vecs, dtype=np.float32)
            # Normalize matrix rows once
            norms = np.linalg.norm(self._vector_matrix, axis=1, keepdims=True)
            self._vector_matrix = self._vector_matrix / np.maximum(norms, 1e-9)
            self._vector_cache = True
        else:
            self._vector_cache = False

    def dense_search(self, query: str, limit: int = 15) -> List[Dict[str, Any]]:
        """Run sub-millisecond dense vector similarity search via matrix multiplication."""
        self._load_vector_cache()
        if not getattr(self, "_vector_cache", False):
            return []
            
        query_vec = list(self.embed_model.embed([query]))[0]
        query_vec = query_vec / np.maximum(np.linalg.norm(query_vec), 1e-9)
        
        # Single vectorized dot-product across all 8,070 documents
        sims = np.dot(self._vector_matrix, query_vec)
        top_indices = np.argpartition(-sims, min(limit, len(sims)-1))[:limit]
        top_indices = top_indices[np.argsort(-sims[top_indices])]
        
        scored = []
        for idx in top_indices:
            item = dict(self._doc_meta[idx])
            item["dense_score"] = float(sims[idx])
            scored.append(item)
            
        return scored

    def hybrid_search(self, query: str, top_k: int = 6) -> List[Dict[str, Any]]:
        """
        Combines BM25 and Dense vector search via Reciprocal Rank Fusion (RRF):
        RRF_score(d) = 1 / (60 + rank_bm25) + 1 / (60 + rank_dense)
        """
        bm25_res = self.bm25_search(query, limit=20)
        dense_res = self.dense_search(query, limit=20)
        
        rrf_scores = {}
        doc_map = {}
        
        # Add BM25 ranks
        for rank, item in enumerate(bm25_res):
            did = item["doc_id"]
            doc_map[did] = item
            rrf_scores[did] = rrf_scores.get(did, 0.0) + (1.0 / (60.0 + rank + 1.0))
            
        # Add Dense ranks
        for rank, item in enumerate(dense_res):
            did = item["doc_id"]
            if did not in doc_map:
                doc_map[did] = item
            rrf_scores[did] = rrf_scores.get(did, 0.0) + (1.0 / (60.0 + rank + 1.0))
            
        # Sort by combined RRF score
        sorted_docs = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        
        final_results = []
        for did, score in sorted_docs[:top_k]:
            item = doc_map[did]
            item["rrf_score"] = score
            final_results.append(item)
            
        return final_results
