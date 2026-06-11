"""Local file-based knowledge base with in-memory vector search."""

import json
import os
import pickle
import threading
from typing import Any, Dict, List, Optional

import numpy as np

from config.settings import DATA_DIR, EMBEDDING_MODEL

KB_ROOT = os.path.join(DATA_DIR, "local_kb")
ARTICLES_DIR = os.path.join(KB_ROOT, "articles")
IMAGES_DIR = os.path.join(KB_ROOT, "images")
MANIFEST_PATH = os.path.join(KB_ROOT, "manifest.json")
CACHE_PATH = os.path.join(KB_ROOT, ".embeddings_cache.pkl")

_lock = threading.Lock()
_index: Optional[Dict[str, Any]] = None
_embedding_model = None


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from langchain_huggingface import HuggingFaceEmbeddings

        _embedding_model = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    return _embedding_model


def _manifest_mtime() -> float:
    if not os.path.isfile(MANIFEST_PATH):
        return 0.0
    return os.path.getmtime(MANIFEST_PATH)


def _load_articles() -> List[Dict[str, Any]]:
    articles = []
    if not os.path.isdir(ARTICLES_DIR):
        return articles
    for name in sorted(os.listdir(ARTICLES_DIR)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(ARTICLES_DIR, name), "r", encoding="utf-8") as f:
            articles.append(json.load(f))
    return articles


def _embed_texts(texts: List[str]) -> np.ndarray:
    emb = _get_embedding_model()
    vectors = emb.embed_documents(texts)
    arr = np.array(vectors, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms


def _build_index() -> Dict[str, Any]:
    articles = _load_articles()
    if not articles:
        return {"articles": [], "embeddings": np.zeros((0, 768), dtype=np.float32), "mtime": 0.0}
    texts = [f"{a.get('title', '')}\n{a.get('content', '')}" for a in articles]
    return {"articles": articles, "embeddings": _embed_texts(texts), "mtime": _manifest_mtime()}


def _load_index(force: bool = False) -> Dict[str, Any]:
    global _index
    with _lock:
        mtime = _manifest_mtime()
        if not force and _index is not None and _index.get("mtime") == mtime:
            return _index
        if not force and os.path.isfile(CACHE_PATH):
            try:
                with open(CACHE_PATH, "rb") as f:
                    cached = pickle.load(f)
                if cached.get("mtime") == mtime and cached.get("articles"):
                    _index = cached
                    return _index
            except Exception:
                pass
        _index = _build_index()
        try:
            with open(CACHE_PATH, "wb") as f:
                pickle.dump(_index, f)
        except Exception:
            pass
        return _index


def list_articles() -> List[Dict[str, Any]]:
    idx = _load_index()
    return [
        {
            "id": a.get("id"),
            "title": a.get("title"),
            "category": a.get("category"),
            "tags": a.get("tags", []),
            "has_image": bool(a.get("image")),
        }
        for a in idx.get("articles", [])
    ]


def format_results_for_llm(results: List[Dict[str, Any]], asset_base: str = "") -> str:
    parts = []
    for r in results:
        block = f"### {r.get('title')} (id={r.get('id')}, score={r.get('score', 0):.2f})\n{r.get('content', '')}"
        img = r.get("image")
        if img and img.get("path"):
            url = f"{asset_base.rstrip('/')}/{img['path'].replace('images/', '')}" if asset_base else img["path"]
            block += f"\n[Image: {img.get('caption', '')} — {url}]"
        parts.append(block)
    return "\n\n".join(parts)


def search(query: str, top_k: int = 5, min_score: float = 0.35) -> List[Dict[str, Any]]:
    query = (query or "").strip()
    if not query:
        return []
    idx = _load_index()
    articles = idx.get("articles", [])
    embeddings = idx.get("embeddings")
    if not articles or embeddings is None or len(embeddings) == 0:
        return []
    emb = _get_embedding_model()
    q_vec = np.array(emb.embed_query(query), dtype=np.float32)
    q_norm = np.linalg.norm(q_vec)
    if q_norm > 0:
        q_vec = q_vec / q_norm
    scores = embeddings @ q_vec
    ranked = np.argsort(scores)[::-1][:top_k]
    results = []
    for i in ranked:
        score = float(scores[i])
        if score < min_score:
            continue
        a = dict(articles[i])
        a["score"] = round(score, 4)
        results.append(a)
    return results
