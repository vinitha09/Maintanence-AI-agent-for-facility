import logging
import os
from collections.abc import Generator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import inspect, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import SQLModel, Session, create_engine

from backend.app.models import maintenance as maintenance_models

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPOSITORY_ROOT / ".env")

logger = logging.getLogger(__name__)

def _build_database_url(database_url: str) -> URL:
    url = make_url(database_url)
    if url.drivername in {"postgres", "postgresql", "postgresql+pg8000"}:
        return url.set(drivername="postgresql+psycopg")
    if url.drivername == "postgresql+psycopg":
        return url
    raise ValueError("DATABASE_URL must use a PostgreSQL connection.")


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not configured")

engine = create_engine(
    _build_database_url(DATABASE_URL),
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def create_db_and_tables() -> None:
    try:
        with engine.begin() as connection:
            if connection.dialect.name == "postgresql":
                connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            SQLModel.metadata.create_all(connection)
            _ensure_existing_schema(connection)
    except SQLAlchemyError:
        logger.exception("Could not initialize the PostgreSQL schema.")
        raise


def _ensure_existing_schema(connection) -> None:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    additive_columns = {
        "app_user": {
            "auth_version": "INTEGER NOT NULL DEFAULT 0",
            "is_invited": "BOOLEAN NOT NULL DEFAULT FALSE",
        },
        "machine": {
            "is_deleted": "BOOLEAN NOT NULL DEFAULT FALSE",
        },
        "maintenance_log": {
            "user_id": "INTEGER",
            "is_deleted": "BOOLEAN NOT NULL DEFAULT FALSE",
        },
        "user_invitation": {
            "failed_attempts": "INTEGER NOT NULL DEFAULT 0",
        },
    }

    for table_name, columns in additive_columns.items():
        if table_name not in tables:
            continue
        existing_columns = {
            column["name"] for column in inspect(connection).get_columns(table_name)
        }
        for column_name, definition in columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(
                        f"ALTER TABLE {table_name} ADD COLUMN "
                        f"{column_name} {definition}"
                    )
                )

    if "user_invitation" in tables and connection.dialect.name == "postgresql":
        email_column = next(
            column
            for column in inspect(connection).get_columns("user_invitation")
            if column["name"] == "email"
        )
        if not email_column["nullable"]:
            connection.execute(
                text("ALTER TABLE user_invitation ALTER COLUMN email DROP NOT NULL")
            )

    if connection.dialect.name == "postgresql":
        foreign_keys = (
            inspect(connection).get_foreign_keys("maintenance_log")
            if "maintenance_log" in tables
            else []
        )
        has_user_foreign_key = any(
            constraint.get("referred_table") == "app_user"
            and "user_id" in (constraint.get("constrained_columns") or [])
            for constraint in foreign_keys
        )
        if (
            "maintenance_log" in tables
            and "app_user" in tables
            and not has_user_foreign_key
        ):
            connection.execute(
                text(
                    "ALTER TABLE maintenance_log "
                    "ADD CONSTRAINT fk_maintenance_log_user_id_app_user "
                    "FOREIGN KEY (user_id) REFERENCES app_user (id) ON DELETE SET NULL"
                )
            )

        indexes = {
            index["name"]
            for index in inspect(connection).get_indexes("machine")
        } if "machine" in tables else set()
        if "ix_machine_is_deleted" not in indexes:
            connection.execute(
                text(
                    "CREATE INDEX ix_machine_is_deleted "
                    "ON machine (is_deleted)"
                )
            )

        log_indexes = {
            index["name"]
            for index in inspect(connection).get_indexes("maintenance_log")
        } if "maintenance_log" in tables else set()
        if "ix_maintenance_log_user_id" not in log_indexes:
            connection.execute(
                text(
                    "CREATE INDEX ix_maintenance_log_user_id "
                    "ON maintenance_log (user_id)"
                )
            )
        if "ix_maintenance_log_is_deleted" not in log_indexes:
            connection.execute(
                text(
                    "CREATE INDEX ix_maintenance_log_is_deleted "
                    "ON maintenance_log (is_deleted)"
                )
            )

        if "searchable_chunk" in tables:
            searchable_indexes = {
                index["name"]
                for index in inspect(connection).get_indexes("searchable_chunk")
            }
            if "ix_searchable_chunk_embedding_hnsw" not in searchable_indexes:
                connection.execute(
                    text(
                        "CREATE INDEX ix_searchable_chunk_embedding_hnsw "
                        "ON searchable_chunk USING hnsw (embedding vector_cosine_ops)"
                    )
                )
            if "ix_searchable_chunk_search_vector_gin" not in searchable_indexes:
                connection.execute(
                    text(
                        "CREATE INDEX ix_searchable_chunk_search_vector_gin "
                        "ON searchable_chunk USING gin (search_vector)"
                    )
                )
