import os
import unittest
from unittest.mock import Mock, patch

import httpx

from backend.app.services.rag import answer_generation


SOURCE_MATCH = {
    "source_type": "maintenance_log",
    "log_id": 12,
    "record_type": "repair",
    "recorded_on": "2026-11-09",
    "text": "The pump seal was replaced.",
}


class GeminiAnswerGenerationTests(unittest.TestCase):
    def test_build_payload_uses_gemini_system_instruction_and_source_context(self):
        payload = answer_generation._build_payload(
            "Why did the pump stop?", [SOURCE_MATCH]
        )

        self.assertIn("industrial maintenance assistant", payload["system_instruction"]["parts"][0]["text"])
        self.assertEqual(payload["contents"][0]["role"], "user")
        user_text = payload["contents"][0]["parts"][0]["text"]
        self.assertIn("Why did the pump stop?", user_text)
        self.assertIn("The pump seal was replaced.", user_text)
        self.assertEqual(payload["generationConfig"]["temperature"], 0.2)

    def test_missing_api_key_fails_before_request(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(
                answer_generation.AnswerGenerationError, "GEMINI_API_KEY"
            ):
                answer_generation._headers()

    @patch("backend.app.services.rag.answer_generation.httpx.post")
    def test_generate_answer_uses_server_side_key_and_parses_candidates(
        self, post
    ):
        response = Mock()
        response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "The repair log records a seal replacement. "},
                            {"text": "The records do not establish the root cause."},
                        ]
                    }
                }
            ],
            "usageMetadata": {"promptTokenCount": 24, "candidatesTokenCount": 18},
        }
        post.return_value = response

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            answer = answer_generation.generate_answer("What happened?", [SOURCE_MATCH])

        self.assertEqual(
            answer,
            "The repair log records a seal replacement. "
            "The records do not establish the root cause.",
        )
        args, kwargs = post.call_args
        self.assertTrue(args[0].endswith(":generateContent"))
        self.assertNotIn("test-key", args[0])
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], "test-key")
        response.raise_for_status.assert_called_once()

    def test_stream_parses_gemini_sse_text_and_usage(self):
        body = (
            'data: {"candidates":[{"content":{"parts":[{"text":"The service "} ]}}]}\n\n'
            'data: {"candidates":[{"content":{"parts":[{"text":"was restored."}]}}],'
            '"usageMetadata":{"promptTokenCount":20,"candidatesTokenCount":8}}\n\n'
        )
        response = httpx.Response(
            200,
            text=body,
            request=httpx.Request("POST", "https://example.invalid"),
        )
        stream = answer_generation.GeminiAnswerStream(
            client=Mock(), response=response
        )

        self.assertEqual(list(stream.tokens()), ["The service ", "was restored."])
        self.assertEqual(
            stream.metrics,
            {"promptTokenCount": 20, "candidatesTokenCount": 8},
        )

    def test_empty_sources_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least one source"):
            answer_generation._build_payload("Question?", [])


if __name__ == "__main__":
    unittest.main()
