import unittest
from unittest.mock import Mock
from unittest.mock import patch

from conductor import app


class TelegramWebhookTest(unittest.TestCase):
    def test_handle_update_logs_safe_metadata_without_message_text(self):
        update = {
            "message": {
                "message_id": 123,
                "chat": {"id": 42},
                "text": "секретный текст не должен попасть в лог",
                "reply_to_message": {"message_id": 99},
            }
        }

        with patch.object(app.service, "process_text", return_value={"ok": True}) as process_text:
            with patch("builtins.print") as printed:
                result = app.handle_update(update)

        self.assertEqual(result, {"ok": True})
        process_text.assert_called_once_with(
            "секретный текст не должен попасть в лог",
            chat_id=42,
            telegram_message_id=123,
            reply_to_message_id=99,
        )
        log_line = printed.call_args.args[0]
        self.assertIn("TELEGRAM_UPDATE_RECEIVED", log_line)
        self.assertIn("chat_id=42", log_line)
        self.assertIn("message_id=123", log_line)
        self.assertIn("reply_to_message_id=99", log_line)
        self.assertNotIn("секретный текст", log_line)


if __name__ == "__main__":
    unittest.main()
