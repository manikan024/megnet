# MagnetChatBot

Standalone local knowledge-base chatbot with text streaming (OpenAI) and push-to-talk voice (Gemini Live).

## Setup

```bash
cd magnetChatBot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add OPENAI_API_KEY and GEMINI_API_KEY to .env
```

Seed or refresh the demo KB (optional — data is included):

```bash
python3 scripts/seed_local_kb.py
```

## Run

```bash
python3 app.py
```

Open http://localhost:5000 — use **Text Chat** or **Voice** tabs.

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Chat UI |
| POST | `/api/chat/stream` | SSE text chat |
| POST | `/api/search` | KB search (voice tool) |
| GET | `/api/articles` | List articles |
| GET | `/api/assets/<file>` | KB images |
| POST | `/api/live/session` | Gemini Live token |

## CLI voice

```bash
pip install pyaudio
python3 scripts/local_kb_voice.py --mode none
```
