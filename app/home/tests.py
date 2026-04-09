import json
from unittest.mock import patch

from django.test import TestCase


class HomePageTests(TestCase):
    def test_index_sets_csrf_cookie_for_chat_api(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", response.cookies)


class ChatApiTests(TestCase):
    def test_chat_api_requires_post(self):
        response = self.client.get("/api/chat")
        self.assertEqual(response.status_code, 405)

    def test_chat_api_rejects_invalid_json(self):
        response = self.client.post(
            "/api/chat",
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid JSON body.")

    def test_chat_api_requires_message(self):
        response = self.client.post(
            "/api/chat",
            data=json.dumps({"history": []}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Message is required.")

    def test_chat_api_rejects_non_list_history(self):
        response = self.client.post(
            "/api/chat",
            data=json.dumps({"message": "hi", "history": "bad"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"],
            "history must be a list of chat turns.",
        )

    @patch("home.api_views._run_chat")
    def test_chat_api_normalizes_history_and_returns_reply(self, mock_run_chat):
        mock_run_chat.return_value = {"reply": "Hello!", "error": ""}
        payload = {
            "message": "Hi there",
            "history": [
                {"role": "user", "content": "A"},
                {"role": "assistant", "content": "B"},
                {"role": "model", "content": "C"},
                {"role": "user", "content": "   "},
                "invalid",
            ],
        }
        response = self.client.post(
            "/api/chat",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"reply": "Hello!", "error": ""})
        mock_run_chat.assert_called_once_with(
            message="Hi there",
            history=[
                {"role": "user", "content": "A"},
                {"role": "assistant", "content": "B"},
                {"role": "assistant", "content": "C"},
            ],
        )

    @patch("home.api_views._run_chat")
    def test_chat_api_propagates_ai_errors_with_502(self, mock_run_chat):
        mock_run_chat.return_value = {"reply": "", "error": "Upstream failed"}
        response = self.client.post(
            "/api/chat",
            data=json.dumps({"message": "Need help"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error"], "Upstream failed")
