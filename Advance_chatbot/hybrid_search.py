"""
Hybrid search + reranking:

    Chroma (dense) ─┐
                    ├─► RRF fusion ─► top `rerank_k` ─► cross-encoder ─► top `top_k`
    BM25 (sparse) ──┘

Requires:  pip install rank-bm25 fastembed
"""
import re
from typing import List, Dict, Any, Optional

from rank_bm25 import BM25Okapi
from fastembed.rerank.cross_encoder import TextCrossEncoder

from Embeddings import Embedder
try:
       from Vector_store import VectorDB
except Exception:
       VectorStore = None


_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


class HybridRetriever:
    def __init__(
        self,
        Vectordb: Optional[VectorDB] = None,
        embedder: Optional[Embedder] = None,
        use_reranker: bool = True,
        reranker_model: str = "BAAI/bge-reranker-base",  # small/fast; try "BAAI/bge-reranker-base" for accuracy
    ):
        self.vectorstore = VectorDB()
        self.embedder = embedder or Embedder()

        self._bm25: Optional[BM25Okapi] = None
        self._ids: List[str] = []
        self._docs: List[str] = []
        self._metas: List[dict] = []
        self._indexed_count = -1

        self.reranker = None
        if use_reranker:
            try:
                self.reranker = TextCrossEncoder(model_name=reranker_model)
                print("Reranker loaded ✅")
            except Exception as E:
                print("Reranker failed to load, continuing without it ❌")
                print(E)

    # ------------------------------------------------------------------ BM25
    def _ensure_bm25(self):
        """(Re)build BM25 from Chroma whenever the collection size changes."""
        count = self.vectorstore.collection.count()
        if count == self._indexed_count and self._bm25 is not None:
            return

        data = self.vectorstore.collection.get(include=["documents", "metadatas"])
        self._ids = data["ids"]
        self._docs = data["documents"]
        self._metas = data["metadatas"]
        self._bm25 = BM25Okapi([tokenize(d) for d in self._docs]) if self._docs else None
        self._indexed_count = count

    def _sparse_search(self, query: str, k: int) -> List[str]:
        self._ensure_bm25()
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [self._ids[i] for i in ranked if scores[i] > 0]

    # ----------------------------------------------------------------- dense
    def _dense_search(self, query, k):
        q_emb = self.embedder.embed_text([query])[0]   # shape: (dim,)
        res = self.vectorstore.collection.query(
            query_embeddings=[q_emb.tolist()],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        
        out = {}
        if res["ids"] and res["ids"][0]:
            for id_, doc, meta, dist in zip(
                res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]
            ):
                out[id_] = {"content": doc, "metadata": meta, "cosine_similarity": 1 - dist}
        return out

    # ------------------------------------------------------------- reranking
    def _rerank(self, query: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self.reranker or not results:
            return results
        try:
            scores = list(self.reranker.rerank(query, [r["content"] for r in results]))
            for r, s in zip(results, scores):
                r["rerank_score"] = float(s)
            return sorted(results, key=lambda r: r["rerank_score"], reverse=True)
        except Exception as E:
            print("Reranking failed, using RRF order ❌")
            print(E)
            return results

    # ---------------------------------------------------------------- hybrid
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        candidate_k: int = 20,
        rerank_k: int = 20,
        rrf_k: int = 60,
        dense_weight: float = 1.0,
        sparse_weight: float = 1.0,
        min_rerank_score: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        candidate_k      : hits each retriever contributes before fusion
        rerank_k         : how many fused candidates go to the reranker
        top_k            : final number of chunks returned
        min_rerank_score : optional cutoff on the reranker's score (scale depends on
                           the model, so inspect real scores before setting this)
        """
        dense = self._dense_search(query, candidate_k)
        sparse_ids = self._sparse_search(query, candidate_k)

        fused: Dict[str, float] = {}
        for rank, id_ in enumerate(dense.keys(), start=1):
            fused[id_] = fused.get(id_, 0.0) + dense_weight / (rrf_k + rank)
        for rank, id_ in enumerate(sparse_ids, start=1):
            fused[id_] = fused.get(id_, 0.0) + sparse_weight / (rrf_k + rank)

        by_id = {i: (d, m) for i, d, m in zip(self._ids, self._docs, self._metas)}
        dense_rank = {i: r for r, i in enumerate(dense.keys(), start=1)}
        sparse_rank = {i: r for r, i in enumerate(sparse_ids, start=1)}

        # Stage 1: RRF -> rerank_k candidates (NOT top_k, the reranker needs a wider pool)
        pool_size = max(rerank_k, top_k) if self.reranker else top_k
        candidates = []
        for id_, score in sorted(fused.items(), key=lambda x: x[1], reverse=True)[:pool_size]:
            if id_ in dense:
                content, meta = dense[id_]["content"], dense[id_]["metadata"]
                cos = dense[id_]["cosine_similarity"]
            else:
                content, meta = by_id[id_]
                cos = None
            candidates.append({
                "ids": id_,
                "content": content,
                "metadata": meta,
                "hybrid_score": score,
                "cosine_similarity": cos,
                "dense_rank": dense_rank.get(id_),
                "sparse_rank": sparse_rank.get(id_),
            })

        # Stage 2: cross-encoder rerank
        final = self._rerank(query, candidates)

        if min_rerank_score is not None:
            final = [r for r in final if r.get("rerank_score", float("inf")) >= min_rerank_score]

        return final[:top_k]


