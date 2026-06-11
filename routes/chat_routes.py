import os

from flask import Blueprint, make_response, request, send_from_directory

from config.settings import STATIC_DIR
from services import kb_service
from services.chat_service import chat_stream_service, search_service
from services.voice_service import mint_ephemeral_token

chat_bp = Blueprint("chat", __name__)
KB_IMAGES_DIR = os.path.join(kb_service.KB_ROOT, "images")


@chat_bp.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    return chat_stream_service(request.get_json(silent=True) or {})


@chat_bp.route("/api/search", methods=["POST"])
def kb_search():
    return make_response(search_service(request.get_json(silent=True) or {}), 200)


@chat_bp.route("/api/assets/<path:filename>", methods=["GET"])
def kb_assets(filename):
    return send_from_directory(KB_IMAGES_DIR, filename)


@chat_bp.route("/api/articles", methods=["GET"])
def list_articles():
    return make_response({"status": "success", "articles": kb_service.list_articles()}, 200)


@chat_bp.route("/api/live/session", methods=["POST"])
def live_session():
    body, status = mint_ephemeral_token()
    return make_response(body, status)


@chat_bp.route("/api/realtime/session", methods=["POST"])
def realtime_session():
    body, status = mint_ephemeral_token()
    return make_response(body, status)
