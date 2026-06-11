"""Thin OpenAI streaming wrapper for chat answers."""

import json
import os
from typing import Generator, Optional, Tuple

from openai import OpenAI

from config.settings import CHAT_MODEL, OPENAI_API_KEY

UsageInfo = Optional[dict]
Chunk = Tuple[Optional[str], UsageInfo, Optional[str]]


def generate_response_stream(
    data: str,
    system_instruction: str,
    previous_response_id: Optional[str] = None,
) -> Generator[Chunk, None, None]:
    client = OpenAI(api_key=OPENAI_API_KEY)
    safe_input = data if isinstance(data, str) else json.dumps(data)
    params = {
        "model": CHAT_MODEL,
        "input": safe_input,
        "instructions": system_instruction,
        "stream": True,
        "temperature": 0.7,
        "max_output_tokens": 5000,
    }
    if previous_response_id:
        params["previous_response_id"] = previous_response_id

    stream = client.responses.create(**params)
    usage_info = None
    response_id = None

    for event in stream:
        if event.type == "response.created":
            response_id = event.response.id
        elif event.type == "response.output_text.delta" and getattr(event, "delta", None):
            yield (event.delta, None, None)
        elif event.type == "response.completed" and event.response and event.response.usage:
            u = event.response.usage
            usage_info = {
                "input_tokens": getattr(u, "input_tokens", 0),
                "output_tokens": getattr(u, "output_tokens", 0),
                "total_tokens": getattr(u, "total_tokens", 0),
                "model_name": CHAT_MODEL,
            }

    if usage_info:
        yield (None, usage_info, response_id)
