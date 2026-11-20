"""Configuración del motor SQLAlchemy y creación de tablas en SQLite."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from adscout.db.orm import Base


def _normalize_db_url(db_url: str) -> str:
    """Normaliza URIs de PostgreSQL/Supabase para usar el driver psycopg (v3)."""
    cleaned = db_url.strip()
    if cleaned.startswith("postgres://"):
        return "postgresql+psycopg://" + cleaned.removeprefix("postgres://")
    if cleaned.startswith("postgresql://"):
        return "postgresql+psycopg://" + cleaned.removeprefix("postgresql://")
    return cleaned


def create_db_engine(db_url: str) -> Engine:
    """Crea un Engine de SQLAlchemy configurado para SQLite o PostgreSQL (Supabase)."""
    normalized_url = _normalize_db_url(db_url)
    is_sqlite = normalized_url.startswith("sqlite")
    connect_args = {"check_same_thread": False, "timeout": 30} if is_sqlite else {}
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
