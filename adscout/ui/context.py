"""Contenedor de dependencias compartidas por las páginas de Streamlit."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import streamlit as st
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError

from adscout.config import AppSettings, load_markets, load_scoring_config, load_settings
from adscout.db.database import create_db_engine, create_session_factory, init_db
from adscout.db.repository import AdRepository
from adscout.llm import DailyCallLimiter, GeminiProvider, PerplexityProvider
from adscout.logging_config import configure_logging
from adscout.models.market import MarketConfig
from adscout.scoring.engine import ScoringEngine
from adscout.services.pipeline import IngestionPipeline


@dataclass
class AppContext:
    settings: AppSettings
    markets: dict[str, MarketConfig]
    repository: AdRepository
    scoring_engine: ScoringEngine
    pipeline: IngestionPipeline
    limiter: DailyCallLimiter
    gemini: GeminiProvider
    perplexity: PerplexityProvider
    db_backend: str = "sqlite"


def _sync_streamlit_secrets_to_env() -> None:
    """Copia secretos de Streamlit Community Cloud a os.environ sin sobreescribir valores ya definidos."""
    try:
        secrets = st.secrets
        for key in secrets.keys():
            value = secrets[key]
            if isinstance(value, (str, int, float, bool)) and key not in os.environ:
                os.environ[str(key)] = str(value)
    except Exception:
        # En ejecución local sin .streamlit/secrets.toml es normal que no existan secretos.
        return


@st.cache_resource(show_spinner=False)
def _get_initialized_engine(db_url: str) -> tuple[Engine, str | None]:
    """Crea e inicializa el motor SQLAlchemy una sola vez, con fallback seguro a SQLite si falla."""
    engine = create_db_engine(db_url)
    try:
        init_db(engine)
        return engine, None
    except OperationalError as exc:
        fallback_dir = Path(tempfile.gettempdir()) / "adscout"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        fallback_url = f"sqlite:///{(fallback_dir / 'adscout.db').resolve().as_posix()}"
        if fallback_url == db_url:
            raise
        fallback_engine = create_db_engine(fallback_url)
        init_db(fallback_engine)
        reason = (
            "No se pudo conectar a PostgreSQL/Supabase (verifica que hayas restablecido la contraseña "
            "de la base de datos del proyecto `adscout` en Supabase y la hayas puesto en Secrets). "
            "Usando SQLite temporal mientras tanto."
            if not db_url.startswith("sqlite")
            else str(exc)
        )
        return fallback_engine, reason


def build_app_context() -> AppContext:
    """Inicializa configuración, SQLite/PostgreSQL, motor de scoring y proveedores LLM opcionales."""
    _sync_streamlit_secrets_to_env()
    settings = load_settings()
    configure_logging(settings.log_level)

    engine, db_warning = _get_initialized_engine(settings.db_url)
    if db_warning:
        st.sidebar.warning(db_warning)
    repository = AdRepository(create_session_factory(engine))

    markets = load_markets(settings.markets_dir)
    scoring_config = load_scoring_config(settings.scoring_config_path)
    scoring_engine = ScoringEngine(scoring_config)
    pipeline = IngestionPipeline(repository=repository, scoring_engine=scoring_engine)

    limiter = DailyCallLimiter(repository=repository, daily_limit=settings.llm_daily_call_limit)
    gemini = GeminiProvider(api_key=settings.gemini_api_key, model_name=settings.gemini_model)
    perplexity = PerplexityProvider(
        api_key=settings.perplexity_api_key,
        model_name=settings.perplexity_model,
        base_url=settings.perplexity_base_url,
    )

    return AppContext(
        settings=settings,
        markets=markets,
        repository=repository,
        scoring_engine=scoring_engine,
        pipeline=pipeline,
        limiter=limiter,
        gemini=gemini,
        perplexity=perplexity,
        db_backend=engine.dialect.name,
    )
