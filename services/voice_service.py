"""Gemini Live ephemeral tokens and session config."""

import datetime
from typing import Any, Dict, Tuple

from google.genai import types

from config.settings import GEMINI_API_KEY, LIVE_MODEL
from services import kb_service


def _kb_summary() -> str:
    articles = kb_service.list_articles()
    lines = ["Available knowledge base articles:"]
    for a in articles[:50]:
        lines.append(f"- [{a.get('id')}] {a.get('title')} ({a.get('category')})")
    return "\n".join(lines)


def build_live_connect_config(model: str | None = None) -> types.LiveConnectConfig:
    model = model or LIVE_MODEL
    search_tool = types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="search_local_kb",
                description="Search the local AcmeDesk knowledge base for articles matching the user question.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "query": types.Schema(
                            type=types.Type.STRING,
                            description="Search query derived from the user question",
                        )
                    },
                    required=["query"],
                ),
            )
        ]
    )
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=(
            "You are AcmeDesk voice assistant grounded in a local knowledge base. "
            "Always call search_local_kb before answering factual questions. "
            "Answer concisely in spoken English. If the KB has no match, say so clearly.\n\n"
            + _kb_summary()
        ),
        tools=[search_tool],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
            )
        ),
    )


def mint_ephemeral_token() -> Tuple[Dict[str, Any], int]:
    if not GEMINI_API_KEY:
        return {"status": "error", "message": "GEMINI_API_KEY is not configured"}, 500

    try:
        from google import genai
    except ImportError:
        return {"status": "error", "message": "google-genai package is not installed"}, 500

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    client = genai.Client(api_key=GEMINI_API_KEY, http_options={"api_version": "v1alpha"})

    try:
        token = client.auth_tokens.create(
            config={
                "uses": 1,
                "expire_time": (now + datetime.timedelta(minutes=30)).isoformat(),
                "new_session_expire_time": (now + datetime.timedelta(minutes=2)).isoformat(),
                "http_options": {"api_version": "v1alpha"},
            }
        )
    except Exception as exc:
        return {"status": "error", "message": str(exc), "model": LIVE_MODEL, "provider": "gemini"}, 502

    token_name = getattr(token, "name", None) or (token.get("name") if isinstance(token, dict) else None)
    if not token_name:
        return {"status": "error", "message": "No ephemeral token name returned"}, 502

    return {
        "status": "success",
        "provider": "gemini",
        "token": token_name,
        "model": LIVE_MODEL,
        "articles_count": len(kb_service.list_articles()),
        "client_secret": token_name,
    }, 200
