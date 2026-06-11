import os

from flask import Flask, send_from_directory
from flask_cors import CORS

from config.settings import SERVER_HOST, SERVER_PORT, STATIC_DIR
from routes.chat_routes import chat_bp

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")
CORS(app)
app.register_blueprint(chat_bp)


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


if __name__ == "__main__":
    os.makedirs(os.path.join(os.path.dirname(__file__), "data", "local_kb", "conversations"), exist_ok=True)
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=True, threaded=True)
