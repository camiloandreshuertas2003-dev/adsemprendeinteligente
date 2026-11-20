"""Generación de enlaces directos hacia la Biblioteca de Anuncios de Meta (Facebook Ad Library)."""

from __future__ import annotations

from datetime import date, timedelta
from urllib.parse import urlencode

META_AD_LIBRARY_BASE = "https://www.facebook.com/ads/library/"


def _is_numeric_meta_id(value: str | None) -> bool:
    """Devuelve True si el identificador corresponde a un ID numérico real de Meta."""
    if not value:
        return False
    cleaned = value.strip()
    return cleaned.isdigit() and len(cleaned) >= 5


def build_ad_library_search_url(
    query: str,
    country: str = "ALL",
    active_status: str = "active",
    media_type: str = "all",
    min_days_active: int = 0,
    reference_date: date | None = None,
) -> str:
    """Construye una URL de búsqueda filtrada en Meta Ad Library.

    Si `min_days_active > 0`, agrega `start_date[max]` para mostrar únicamente anuncios
    que llevan rodando al menos esa cantidad de días (señal clave de rentabilidad).
    """
    params: dict[str, str] = {
        "active_status": active_status,
        "ad_type": "all",
        "country": (country or "ALL").upper(),
        "q": query.strip(),
        "search_type": "keyword_unordered",
        "media_type": media_type,
    }
    if min_days_active > 0:
        today = reference_date or date.today()
        max_start = today - timedelta(days=min_days_active)
        params["start_date[max]"] = max_start.isoformat()
    return f"{META_AD_LIBRARY_BASE}?{urlencode(params)}"


def build_ad_library_ad_url(
    ad_id: str,
    country: str = "ALL",
    snapshot_url: str | None = None,
    fallback_query: str = "",
) -> str:
    """Devuelve el enlace directo al anuncio en Meta Ad Library."""
    if snapshot_url and snapshot_url.strip().startswith(("http://", "https://")):
        return snapshot_url.strip()
    if _is_numeric_meta_id(ad_id):
        return f"{META_AD_LIBRARY_BASE}?{urlencode({'id': ad_id.strip()})}"
    if fallback_query.strip():
        return build_ad_library_search_url(query=fallback_query, country=country)
    return f"{META_AD_LIBRARY_BASE}?{urlencode({'id': ad_id.strip()})}"


def build_ad_library_page_url(
    page_id: str,
    page_name: str = "",
    country: str = "ALL",
    active_status: str = "active",
) -> str:
    """Devuelve el enlace para espiar todos los anuncios activos de una página en Meta Ad Library."""
    if _is_numeric_meta_id(page_id):
        params = {
            "active_status": active_status,
            "ad_type": "all",
            "country": (country or "ALL").upper(),
            "view_all_page_id": page_id.strip(),
            "search_type": "page",
            "media_type": "all",
        }
        return f"{META_AD_LIBRARY_BASE}?{urlencode(params)}"
    query = page_name.strip() or page_id.strip()
    return build_ad_library_search_url(query=query, country=country, active_status=active_status)
