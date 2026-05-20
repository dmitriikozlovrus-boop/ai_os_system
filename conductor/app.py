from __future__ import annotations

import json
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .config import get_settings
from .service import ConductorService
from .telegram import extract_message, extract_text_and_file


settings = get_settings()
service = ConductorService(settings)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._json(200, {"ok": True})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/telegram/webhook":
            self._json(404, {"error": "not found"})
            return
        if settings.telegram_webhook_secret:
            got = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if got != settings.telegram_webhook_secret:
                self._json(401, {"error": "bad secret"})
                return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            update = json.loads(body)
            result = handle_update(update)
            self._json(200, result)
        except Exception as exc:  # noqa: BLE001 - Telegram must get a response, not a dropped connection.
            print("Unhandled webhook error:", repr(exc), flush=True)
            traceback.print_exc()
            self._json(200, {"ok": False, "error": str(exc)})

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def handle_update(update: dict[str, Any]) -> dict[str, Any]:
    message = extract_message(update)
    if not message:
        return {"ok": True, "ignored": True}
    chat_id = int(message["chat"]["id"])
    text, file_info = extract_text_and_file(message)

    if file_info and file_info.get("kind") in {"voice", "audio"}:
        file_path, data = service.telegram.get_file_bytes(file_info["file_id"])
        content_type = file_info.get("mime_type") or "audio/ogg"
        return service.process_audio(file_path, data, content_type=content_type, chat_id=chat_id)

    if not text.strip():
        service.telegram.send_message(chat_id, "Пока MVP обрабатывает текст и голос. Для фото/документов добавь подпись текстом.")
        return {"ok": True, "message": "unsupported without text"}

    return service.process_text(text, chat_id=chat_id)


def main() -> None:
    server = ThreadingHTTPServer((settings.host, settings.port), Handler)
    print(f"Conductor listening on http://{settings.host}:{settings.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
