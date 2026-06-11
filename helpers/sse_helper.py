import json


def sse_event(event_name, data):
    if not isinstance(event_name, str) or not event_name:
        event_name = "message"
    try:
        payload = data if isinstance(data, str) else json.dumps(data, default=str)
    except Exception:
        payload = json.dumps({"raw": str(data)})
    data_lines = "\n".join(f"data: {line}" for line in payload.split("\n"))
    return f"event: {event_name}\n{data_lines}\n\n"
