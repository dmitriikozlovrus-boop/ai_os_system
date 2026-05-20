from __future__ import annotations

from typing import Any

from .http import request_bytes, request_json


class TelegramClient:
    def __init__(self, token: str):
        self.token = token
        self.base = f"https://api.telegram.org/bot{token}"
        self.file_base = f"https://api.telegram.org/file/bot{token}"

    def send_message(self, chat_id: int, text: str) -> None:
        request_json(
            "POST",
            f"{self.base}/sendMessage",
            payload={"chat_id": chat_id, "text": text[:4096]},
        )

    def get_file_bytes(self, file_id: str) -> tuple[str, bytes]:
        data = request_json("GET", f"{self.base}/getFile?file_id={file_id}")
        path = data["result"]["file_path"]
        return path, request_bytes(f"{self.file_base}/{path}")


def extract_message(update: dict[str, Any]) -> dict[str, Any] | None:
    return update.get("message") or update.get("edited_message")


def extract_text_and_file(message: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    text = message.get("text") or message.get("caption") or ""
    if "voice" in message:
        return text, {"kind": "voice", **message["voice"]}
    if "audio" in message:
        return text, {"kind": "audio", **message["audio"]}
    if "document" in message:
        return text, {"kind": "document", **message["document"]}
    if "photo" in message:
        photos = message.get("photo") or []
        return text, {"kind": "photo", **photos[-1]} if photos else (text, None)
    return text, None
