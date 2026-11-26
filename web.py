"""App web do YAWE: abra no celular (mesmo Wi-Fi do PC) ou em qualquer navegador.

Rode com:  py web.py   (ou dê dois cliques em "Abrir YAWE.bat")
"""

from __future__ import annotations

import hmac
import json
import os
import queue
import secrets
import socket
import sys
import threading
import time
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory, session

from yawe.ai_client import AIError, create_chat
from yawe.config import ConfigError, Settings, load_settings

STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_MESSAGE_CHARS = 8000


def create_app(settings: Settings) -> Flask:
    app = Flask(__name__, static_folder=None)
    # Chave que assina o cookie de login; muda a cada reinício (basta entrar de novo).
    app.secret_key = os.getenv("APP_SECRET_KEY") or secrets.token_hex(32)
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

    voice = None
    if settings.elevenlabs_api_key:
        try:
            from yawe.voice import Voice

            voice = Voice(settings.elevenlabs_api_key, settings.voice_id, settings.tts_model, settings.voice_max_chars)
        except ImportError:
            print("[aviso] biblioteca de voz não instalada; rode: pip install -r requirements.txt", file=sys.stderr)

    chats: dict[str, object] = {}
    locks: dict[str, threading.Lock] = {}

    def chat_for_session():
        sid = session.setdefault("sid", secrets.token_hex(16))
        if sid not in chats:
            chats[sid] = create_chat(settings)
            locks[sid] = threading.Lock()
        return chats[sid], locks[sid]

    def logged_in() -> bool:
        return session.get("auth") is True

    @app.after_request
    def security_headers(resp: Response) -> Response:
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        return resp

    @app.get("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.get("/static/<path:name>")
    def static_files(name: str):
        return send_from_directory(STATIC_DIR, name)

    @app.get("/manifest.json")
    def manifest():
        data = json.loads((STATIC_DIR / "manifest.json").read_text(encoding="utf-8"))
        data["name"] = data["short_name"] = settings.assistant_name
        return jsonify(data)

    @app.get("/api/status")
    def status():
        return jsonify(
            logged_in=logged_in(),
            name=settings.assistant_name,
            model=settings.model if logged_in() else None,
            voice=voice is not None,
        )

    @app.post("/api/login")
    def login():
        password = str((request.get_json(silent=True) or {}).get("password", ""))
        if settings.app_password and hmac.compare_digest(password.encode(), settings.app_password.encode()):
            session.clear()
            session["auth"] = True
            session.permanent = True
            return jsonify(ok=True)
        time.sleep(1.5)  # dificulta adivinhar a senha por tentativa e erro
        return jsonify(ok=False, error="Senha incorreta."), 401

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify(ok=True)

    @app.post("/api/reset")
    def reset():
        if not logged_in():
            return jsonify(error="Faça login."), 401
        chat, _ = chat_for_session()
        chat.reset()
        return jsonify(ok=True)

    @app.post("/api/chat")
    def chat_endpoint():
        if not logged_in():
            return jsonify(error="Faça login."), 401
        message = str((request.get_json(silent=True) or {}).get("message", "")).strip()
        if not message:
            return jsonify(error="Mensagem vazia."), 400
        if len(message) > MAX_MESSAGE_CHARS:
            return jsonify(error="Mensagem muito longa."), 400

        chat, lock = chat_for_session()
        if not lock.acquire(blocking=False):
            return jsonify(error="Aguarde a resposta anterior terminar."), 429

        events: queue.Queue = queue.Queue()
        notices: list[str] = []

        def run() -> None:
            try:
                if hasattr(chat, "on_model_change"):
                    chat.on_model_change = lambda old, new: notices.append(
                        f"O modelo '{old}' não está disponível; usando '{new}'."
                    )
                reply = chat.send(message, on_text=lambda t: events.put({"t": t}))
                for note in notices:
                    events.put({"notice": note})
                events.put({"done": True, "text": reply.text, "truncated": reply.truncated})
            except AIError as e:
                events.put({"error": str(e)})
            except Exception as e:  # nunca deixa a página sem resposta
                events.put({"error": f"Erro inesperado: {e.__class__.__name__}"})
            finally:
                lock.release()
                events.put(None)

        threading.Thread(target=run, daemon=True).start()

        def stream():
            while (event := events.get()) is not None:
                yield json.dumps(event, ensure_ascii=False) + "\n"

        return Response(stream(), mimetype="application/x-ndjson", headers={"Cache-Control": "no-store"})

    @app.post("/api/tts")
    def tts():
        if not logged_in():
            return jsonify(error="Faça login."), 401
        if voice is None:
            return jsonify(error="Voz desativada: coloque ELEVENLABS_API_KEY no .env."), 400
        text = str((request.get_json(silent=True) or {}).get("text", ""))
        try:
            audio = voice.synthesize_mp3(text)
        except Exception as e:  # VoiceError ou falha inesperada: o chat continua
            return jsonify(error=str(e)), 502
        if not audio:
            return Response(status=204)
        return Response(audio, mimetype="audio/mpeg", headers={"Cache-Control": "no-store"})

    return app


def local_ip() -> str:
    """IP do PC na rede Wi-Fi (para abrir no celular)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # não envia nada; só descobre a interface de rede
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as e:
        print(f"[configuração] {e}", file=sys.stderr)
        return 1
    if not settings.app_password:
        print(
            "[configuração] Defina uma senha para o app: adicione no .env a linha\n"
            "    APP_PASSWORD=uma-senha-forte\n"
            "Ela protege suas chaves: sem a senha, ninguém na sua rede consegue usar o app.",
            file=sys.stderr,
        )
        return 1

    port = int(os.getenv("PORT", "8000"))
    app = create_app(settings)
    print(f"\n{settings.assistant_name} está no ar!  (modelo: {settings.model})")
    print(f"  No celular (mesmo Wi-Fi):  http://{local_ip()}:{port}")
    print(f"  Neste computador:          http://localhost:{port}")
    print("Deixe esta janela aberta enquanto usa. Para desligar: Ctrl + C.\n")
    app.run(host="0.0.0.0", port=port, threaded=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
