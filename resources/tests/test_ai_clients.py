"""Focused tests for AI client auth refresh and rate-limit handling."""

import sys
import types
import unittest
from unittest.mock import Mock, patch


BASE_DIR = __file__
from pathlib import Path
BASE_DIR = Path(BASE_DIR).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.ai_clients import GitHubCopilotClient, GroqClient


class GitHubCopilotClientTests(unittest.TestCase):
    def test_available_refreshes_token_after_login_without_restart(self):
        token_reads = [None, "x" * 24]

        with (
            patch.object(GitHubCopilotClient, "_resolve_gh_cmd", return_value=["gh"]),
            patch.object(GitHubCopilotClient, "_read_token", side_effect=lambda: token_reads.pop(0)),
            patch("builtins.print"),
        ):
            client = GitHubCopilotClient(model="gpt-4o-mini")
            self.assertIsNone(client._token)
            self.assertTrue(client.available)
            self.assertEqual(client._token, "x" * 24)


class GroqClientRateLimitTests(unittest.TestCase):
    def test_chat_skips_calls_during_cooldown_after_429(self):
        create_mock = Mock(side_effect=Exception("429 Too Many Requests. Please try again in 9.5s"))
        fake_sdk = types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(create=create_mock)
            )
        )

        with patch("core.ai_clients.Groq", return_value=fake_sdk), patch("builtins.print"):
            client = GroqClient(api_key="g" * 32)

        messages = [{"role": "user", "content": "hola"}]
        self.assertIsNone(client.chat(messages))
        self.assertGreater(client._rate_limited_until, 0.0)
        self.assertIsNone(client.chat(messages))
        self.assertEqual(create_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)