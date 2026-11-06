import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from streamlit.testing.v1 import AppTest

from dkkk_copilot_ui.backend_client import StreamEvent, stream_agent
from dkkk_copilot_ui.config import get_settings

APP = Path(__file__).resolve().parents[1] / "src/dkkk_copilot_ui/app.py"
QUESTION = {
    "text": "Уточните показатель",
    "term": "Стоимость метанола",
    "options": [
        {"n": 1, "name": "Стоимость метанола"},
        {"n": 2, "name": "Стоимость метанола Угра"},
    ],
}


class ClarificationTests(unittest.TestCase):
    def test_sse_event_name_and_continuation_headers(self):
        response = MagicMock()
        response.ok = True
        response.iter_lines.return_value = iter([
            ": ping", "event: clarification",
            "data: " + json.dumps(QUESTION), "",
        ])
        response.__enter__.return_value = response
        with patch("dkkk_copilot_ui.backend_client.requests.post", return_value=response) as post:
            events = list(stream_agent(get_settings(), "question", "client", "session", "user"))
            self.assertEqual(events, [StreamEvent("clarification", QUESTION)])
            response.iter_lines.return_value = iter([
                "event: answer", 'data: {"text":"done","outcome":"ok"}', "",
            ])
            list(stream_agent(get_settings(), "2", "client", "session", "user"))
        self.assertEqual(post.call_args.kwargs["json"], {"message": "2"})
        for call in post.call_args_list:
            headers = call.kwargs["headers"]
            self.assertEqual(headers["x-user-id"], "user")
            self.assertEqual(headers["x-session-id"], "session")
            self.assertEqual(headers["x-client-id"], "client")
            self.assertIn("x-trace-id", headers)
            self.assertIn("x-request-time", headers)

    def test_repeated_pauses_messages_and_final_clarify_answer(self):
        with patch("dkkk_copilot_ui.backend_client.stream_agent") as stream:
            stream.side_effect = [
                iter([StreamEvent("clarification", QUESTION)]),
                iter([StreamEvent("clarification", QUESTION)]),
                iter([StreamEvent("answer", {"text": "Ещё вопрос?", "outcome": "clarify"})]),
            ]
            app = AppTest.from_file(str(APP)).run()
            app.chat_input[0].set_value("question").run()
            self.assertFalse(app.exception)
            self.assertIsNotNone(app.session_state.pending_clarification)
            self.assertTrue(app.sidebar.text_input[0].disabled)
            self.assertTrue(app.get("file_uploader")[0].disabled)
            self.assertFalse(app.error)
            self.assertFalse(any(b.key and b.key.startswith("clarification_") for b in app.button))
            first_context = stream.call_args.kwargs.copy()
            app.chat_input[0].set_value("2").run()
            self.assertFalse(app.exception)
            self.assertEqual(stream.call_args.kwargs["message"], "2")
            for key in ("user_id", "session_id", "client_id"):
                self.assertEqual(stream.call_args.kwargs[key], first_context[key])
            self.assertIsNotNone(app.session_state.pending_clarification)
            app.chat_input[0].set_value("1").run()
            self.assertFalse(app.exception)
            self.assertIsNone(app.session_state.pending_clarification)
            self.assertFalse(app.sidebar.text_input[0].disabled)
            self.assertEqual(app.session_state.messages[-1]["outcome"], "clarify")
            self.assertFalse(any(b.key and b.key.startswith("clarification_") for b in app.button))
            self.assertEqual(stream.call_count, 3)

    def test_error_kind_and_transport_failure(self):
        with patch("dkkk_copilot_ui.backend_client.stream_agent") as stream:
            stream.side_effect = [
                iter([StreamEvent("clarification", QUESTION)]),
                RuntimeError("offline"),
                iter([StreamEvent("error", {"text": "Ошибка", "kind": "validation"})]),
            ]
            app = AppTest.from_file(str(APP)).run()
            app.chat_input[0].set_value("question").run()
            app.chat_input[0].set_value("Стоимость метанола").run()
            self.assertFalse(app.exception)
            self.assertTrue(app.error)
            self.assertIsNotNone(app.session_state.pending_clarification)
            app.chat_input[0].set_value("1").run()
            self.assertFalse(app.exception)
            self.assertTrue(app.error)
            self.assertIsNone(app.session_state.pending_clarification)
            self.assertEqual(app.session_state.messages[-1]["kind"], "validation")


if __name__ == "__main__":
    unittest.main()
