"""Configuración del motor SQLAlchemy y creación de tablas en SQLite."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from adscout.db.orm import Base


def _normalize_db_url(db_url: str) -> str:
    """Normaliza URIs de PostgreSQL/Supabase para psycopg v3 (elimina pgbouncer=true y asegura SSL)."""
    cleaned = db_url.strip()
    if cleaned.startswith("postgres://"):
        cleaned = "postgresql+psycopg://" + cleaned.removeprefix("postgres://")
    elif cleaned.startswith("postgresql://"):
        cleaned = "postgresql+psycopg://" + cleaned.removeprefix("postgresql://")

    if cleaned.startswith("postgresql+psycopg://"):
        parts = urlsplit(cleaned)
        query_items = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() != "pgbouncer"]
        query_keys = {k.lower() for k, _ in query_items}
        if "sslmode" not in query_keys and "supabase" in (parts.hostname or "").lower():
            query_items.append(("sslmode", "require"))
        cleaned = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query_items), parts.fragment))
    return cleaned


def create_db_engine(db_url: str) -> Engine:
    """Crea un Engine de SQLAlchemy configurado para SQLite o PostgreSQL (Supabase)."""
    normalized_url = _normalize_db_url(db_url)
    is_sqlite = normalized_url.startswith("sqlite")
    if is_sqlite:
        connect_args: dict = {"check_same_thread": False, "timeout": 30}
    else:
        connect_args = {"prepare_threshold": None}
    return create_engine(
        normalized_url,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Devuelve una fábrica de sesiones SQLAlchemy."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """Crea las tablas definidas en Base si aún no existen."""
    Base.metadata.create_all(bind=engine)
