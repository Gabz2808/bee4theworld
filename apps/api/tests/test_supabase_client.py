import os
import unittest
from unittest.mock import patch

from app.core.supabase_client import (
    SupabaseConfigurationError,
    get_supabase_client,
)


class SupabaseClientTests(unittest.TestCase):
    def setUp(self) -> None:
        get_supabase_client.cache_clear()

    def tearDown(self) -> None:
        get_supabase_client.cache_clear()

    def test_requires_url_and_secret_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(
            SupabaseConfigurationError,
            "SUPABASE_URL, SUPABASE_SECRET_KEY",
        ):
            get_supabase_client()

    @patch("app.core.supabase_client.create_client")
    def test_creates_and_reuses_client_from_server_credentials(
        self,
        create_client: unittest.mock.MagicMock,
    ) -> None:
        expected_client = object()
        create_client.return_value = expected_client
        with patch.dict(
            os.environ,
            {
                "SUPABASE_URL": "https://example.supabase.co",
                "SUPABASE_SECRET_KEY": "test-secret-key",
            },
            clear=True,
        ):
            first_client = get_supabase_client()
            second_client = get_supabase_client()

        self.assertIs(first_client, expected_client)
        self.assertIs(second_client, expected_client)
        create_client.assert_called_once_with(
            "https://example.supabase.co",
            "test-secret-key",
        )


if __name__ == "__main__":
    unittest.main()
