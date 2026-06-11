"""RAG chat streaming over SSE."""

import json
import os
from typing import Any, Dict, List, Optional

from flask import Response, stream_with_context

from helpers.sse_helper import sse_event
from services import kb_service
from services.llm_stream import generate_response_stream

CONV_DIR = os.path.join(kb_service.KB_ROOT, "conversations")
ASSET_BASE = "/api/assets"

SYSTEM_PROMPT = """You are a helpful assistant for AcmeDesk, grounded ONLY in the provided knowledge base context.

Respond in valid HTML only (no markdown code fences, no ``` blocks). Use:
- <p> for paragraphs
- <strong> for key terms and emphasis
- <span style="color:#2563eb"> for important highlights (sparingly)
- <ul> and <ol> with <li> for lists and numbered steps
- <h3> for section headings when the answer has multiple parts
- When a source article includes a relevant image URL, use:
  <figure><img src="IMAGE_URL" alt="caption" style="max-width:100%;border-radius:8px"><figcaption>caption</figcaption></figure>

Rules:
- Answer only from the KB context below. If the context does not contain the answer, say clearly in HTML that the information is not in the knowledge base.
- Do not invent features, prices, or policies not in the context.
- Keep answers concise and helpful.
"""


def _asset_url(filename: str) -> str:
    return f"{ASSET_BASE}/{filename}"


def _sources_payload(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in results:
        item = {
            "id": r.get("id"),
            "title": r.get("title"),
            "category": r.get("category"),
            "score": r.get("score"),
        }
        img = r.get("image") or {}
        if img.get("path"):
            rel = img["path"].replace("images/", "")
            item["image_url"] = _asset_url(rel)
            item["image_caption"] = img.get("caption", "")
        out.append(item)
    return out


def _build_user_payload(query: str, results: List[Dict[str, Any]]) -> str:
    context = kb_service.format_results_for_llm(results, asset_base=ASSET_BASE)
    return json.dumps(
        {
            "user_query": query,
            "kb_context": context,
            "image_base_url": ASSET_BASE + "/",
        },
        ensure_ascii=False,
    )


def _save_conversation(conversation_id: str, role: str, content: str) -> None:
    if not conversation_id:
        return
    os.makedirs(CONV_DIR, exist_ok=True)
    path = os.path.join(CONV_DIR, f"{conversation_id}.json")
    data = {"conversation_id": conversation_id, "messages": []}
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    data.setdefault("messages", []).append({"role": role, "content": content})
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def chat_stream_service(request_data):
    def gen():
        try:
            data = request_data or {}
            query = str(data.get("query") or data.get("user_query") or "").strip()
            conversation_id = str(data.get("conversation_id") or "").strip()
            response_id = str(
                data.get("response_id")
                or data.get("responseId")
                or data.get("ai_response_id")
                or ""
            ).strip() or None

            if not query:
                yield sse_event("error", {"message": "query is required"})
                return

            results = kb_service.search(query, top_k=5, min_score=0.30)
            sources = _sources_payload(results)
            yield sse_event("sources", sources)

            user_payload = _build_user_payload(query, results)
            acc: List[str] = []
            stream_rid: Optional[str] = None

            for chunk, usage_info, rid in generate_response_stream(
                data=user_payload,
                system_instruction=SYSTEM_PROMPT,
                previous_response_id=response_id,
            ):
                if chunk:
                    acc.append(chunk)
                    yield sse_event("delta", {"text": chunk})
                if usage_info is not None:
                    stream_rid = rid

            answer = "".join(acc).strip()
            if conversation_id:
                _save_conversation(conversation_id, "user", query)
                _save_conversation(conversation_id, "assistant", answer)

            done: Dict[str, Any] = {"answer": answer, "sources": sources}
            if stream_rid:
                done["response_id"] = stream_rid
            if conversation_id:
                done["conversation_id"] = conversation_id
            yield sse_event("done", done)

        except Exception as e:
            yield sse_event("error", {"message": str(e)})

    return Response(stream_with_context(gen()), mimetype="text/event-stream")


def search_service(request_data):
    query = str((request_data or {}).get("query") or "").strip()
    top_k = int((request_data or {}).get("top_k") or 3)
    results = kb_service.search(query, top_k=top_k, min_score=0.25)
    return {
        "status": "success",
        "results": _sources_payload(results),
        "context": kb_service.format_results_for_llm(results, asset_base=ASSET_BASE),
    }
