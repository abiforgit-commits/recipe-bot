"""Week 4 retrieval backends.

Two retrievers:
  dense  - vector similarity over the structure-aware index (the BASELINE)
  hybrid - the ONE Week 4 change: dense + BM25 keyword search, fused with
           Reciprocal Rank Fusion (RRF, k=60)

Why RRF fuses RANKS and not scores: cosine similarities (0..1) and BM25
scores (unbounded) are not on the same scale and never were. Each retriever
contributes 1/(60 + rank) per chunk; the constant 60 damps the influence of
any single list's top position.
"""
import re
from pathlib import Path

import chromadb
from rank_bm25 import BM25Okapi

ROOT = Path(__file__).parent
_client = chromadb.PersistentClient(path=str(ROOT / "chroma_db"))
_col = _client.get_collection("recipes_structure")


def dense_top(question, k=3):
    """Vector-similarity retrieval: returns [(chunk_id, text, score), ...]."""
    res = _col.query(query_texts=[question], n_results=k)
    return list(zip(res["ids"][0], res["documents"][0],
                    [1 - d for d in res["distances"][0]]))


# --- BM25 index, built once at import over the same 24 chunks -------------
def _tokenize(text):
    """Lowercase word/number tokens, punctuation stripped.

    Plain .split() kept punctuation glued on - '(noi' and 'arisi)' never
    matched the query's 'arisi?', so BM25 lost its rare-token signal and its
    stopword noise dragged two previously-passing questions down via RRF.
    Keeps % and . inside tokens so '6.7%' survives as one token.
    """
    return re.findall(r"[a-z0-9%.]+", text.lower())


_all = _col.get()
_IDS = _all["ids"]
_DOCS = _all["documents"]
_DOC_BY_ID = dict(zip(_IDS, _DOCS))
_bm25 = BM25Okapi([_tokenize(d) for d in _DOCS])

RRF_K = 60
POOL = 24  # candidate list depth per retriever; covers the whole corpus here


def hybrid_top(question, k=3):
    """Dense + BM25 candidate lists fused by RRF; returns top-k."""
    dense = dense_top(question, k=POOL)

    bm25_scores = _bm25.get_scores(_tokenize(question))
    bm25_order = sorted(range(len(_IDS)), key=lambda i: -bm25_scores[i])[:POOL]

    fused = {}
    for rank, (cid, _, _) in enumerate(dense, 1):
        fused[cid] = fused.get(cid, 0.0) + 1.0 / (RRF_K + rank)
    for rank, i in enumerate(bm25_order, 1):
        fused[_IDS[i]] = fused.get(_IDS[i], 0.0) + 1.0 / (RRF_K + rank)

    top = sorted(fused, key=fused.get, reverse=True)[:k]
    return [(cid, _DOC_BY_ID[cid], fused[cid]) for cid in top]


RETRIEVERS = {
    "dense": dense_top,
    "hybrid": hybrid_top,
}
