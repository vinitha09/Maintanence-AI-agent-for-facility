import unittest

from sqlalchemy import create_engine

from backend.app.db.connection import _build_database_url


class DatabaseConnectionConfigTests(unittest.TestCase):
    def test_postgresql_ssl_and_channel_binding_options_are_preserved(self):
        url = _build_database_url(
            "postgresql://db-user:db-password@db.example.test/maintenance"
            "?sslmode=require&channel_binding=require"
        )

        self.assertEqual(url.drivername, "postgresql+psycopg")
        self.assertEqual(url.query["sslmode"], "require")
        self.assertEqual(url.query["channel_binding"], "require")

        dialect = create_engine(url).dialect
        _, connect_args = dialect.create_connect_args(url)
        self.assertEqual(connect_args["sslmode"], "require")
        self.assertEqual(connect_args["channel_binding"], "require")

    def test_non_postgresql_database_urls_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "PostgreSQL"):
            _build_database_url("sqlite:///maintenance.db")


if __name__ == "__main__":
    unittest.main()
