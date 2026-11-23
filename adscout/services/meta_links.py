"""Generación de enlaces directos hacia la Biblioteca de Anuncios de Meta (Facebook Ad Library)."""

from __future__ import annotations

import re
from datetime import date, timedelta
from urllib.parse import parse_qs, urlencode, urlparse

META_AD_LIBRARY_BASE = "https://www.facebook.com/ads/library/"


def _is_numeric_meta_id(value: str | None) -> bool:
    """Devuelve True si el identificador corresponde a un ID numérico real de Meta."""
    if not value:
        return False
    cleaned = value.strip()
    return cleaned.isdigit() and len(cleaned) >= 5


def is_real_meta_id(value: str | None) -> bool:
    """Alias público para verificar si un ID de anuncio o página es un ID numérico real de Meta."""
    return _is_numeric_meta_id(value)


def extract_page_id(raw_value: str | None) -> str | None:
    """Extrae un Page ID numérico desde un ID directo o una URL de Meta Ad Library / Facebook."""
    if not raw_value:
        return None
    cleaned = raw_value.strip()
    if _is_numeric_meta_id(cleaned):
        return cleaned

    if "http://" in cleaned or "https://" in cleaned or "facebook.com" in cleaned:
        url = cleaned if cleaned.startswith(("http://", "https://")) else f"https://{cleaned}"
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        for key in ("view_all_page_id", "page_id", "id"):
            values = qs.get(key)
            if values and _is_numeric_meta_id(values[0]):
                return values[0].strip()

    match = re.search(r"(?:view_all_page_id|page_id)=([0-9]{5,})", cleaned)
    if match:
        return match.group(1)

    return None


def build_ad_library_search_url(
    query: str,
    country: str = "ALL",
    active_status: str = "active",
    media_type: str = "all",
    min_days_active: int = 0,
    exact_phrase: bool = False,
    sort_by_impressions: bool = True,
    reference_date: date | None = None,
) -> str:
    """Construye una URL de búsqueda precisa y filtrada en Meta Ad Library.

    - `sort_by_impressions=True` ordena por mayores impresiones (`total_impressions` desc).
    - `exact_phrase=True` usa `keyword_exact_phrase` para reducir ruido (excepto si hay operador `|`).
    - `min_days_active > 0` agrega `start_date[max]` para mostrar anuncios que llevan rodando al menos N días.
    """
    cleaned_query = query.strip()
    use_exact = exact_phrase and ("|" not in cleaned_query)
    params: dict[str, str] = {
        "active_status": active_status,
        "ad_type": "all",
        "country": (country or "ALL").upper(),
        "is_targeted_country": "false",
        "media_type": media_type,
        "q": cleaned_query,
        "search_type": "keyword_exact_phrase" if use_exact else "keyword_unordered",
    }
    if sort_by_impressions:
        params["sort_data[mode]"] = "total_impressions"
        params["sort_data[direction]"] = "desc"
    if min_days_active > 0:
        today = reference_date or date.today()
        max_start = today - timedelta(days=min_days_active)
        params["start_date[max]"] = max_start.isoformat()
    return f"{META_AD_LIBRARY_BASE}?{urlencode(params, safe='[]')}"


def build_ad_library_ad_url(
    ad_id: str,
    country: str = "ALL",
    snapshot_url: str | None = None,
    fallback_query: str = "",
) -> str:
    """Devuelve el enlace directo al anuncio en Meta Ad Library.

    Valida que `snapshot_url` no contenga un ID ficticio (no numérico) antes de usarlo.
    """
    if snapshot_url and snapshot_url.strip().startswith(("http://", "https://")):
        cleaned_snap = snapshot_url.strip()
        if "facebook.com/ads/library" in cleaned_snap.lower():
            qs = parse_qs(urlparse(cleaned_snap).query)
            snap_ids = qs.get("id") or []
            if snap_ids and _is_numeric_meta_id(snap_ids[0]):
                return cleaned_snap
            if qs.get("view_all_page_id") and _is_numeric_meta_id(qs["view_all_page_id"][0]):
                return cleaned_snap
        else:
            return cleaned_snap

    if _is_numeric_meta_id(ad_id):
        return f"{META_AD_LIBRARY_BASE}?{urlencode({'id': ad_id.strip()})}"
    if fallback_query.strip():
        return build_ad_library_search_url(query=fallback_query, country=country, exact_phrase=True)
    return f"{META_AD_LIBRARY_BASE}?{urlencode({'id': ad_id.strip()})}"


def build_ad_library_page_url(
    page_id: str,
    page_name: str = "",
    country: str = "ALL",
    active_status: str = "active",
    media_type: str = "all",
    sort_by_impressions: bool = True,
    min_days_active: int = 0,
    reference_date: date | None = None,
) -> str:
    """Devuelve el enlace directo para ver TODOS los anuncios de una página en Meta Ad Library.

    Genera el formato de transparencia de página ordenado por mayores impresiones:
    `...?active_status=active&ad_type=all&country=ALL&is_targeted_country=false&media_type=all&search_type=page&sort_data[mode]=total_impressions&sort_data[direction]=desc&source=page-transparency-widget&view_all_page_id=<ID>`
    """
    extracted_id = extract_page_id(page_id)
    if extracted_id:
        params: dict[str, str] = {
            "active_status": active_status,
            "ad_type": "all",
            "country": (country or "ALL").upper(),
            "is_targeted_country": "false",
            "media_type": media_type,
            "search_type": "page",
        }
        if sort_by_impressions:
            params["sort_data[mode]"] = "total_impressions"
            params["sort_data[direction]"] = "desc"
        params["source"] = "page-transparency-widget"
        params["view_all_page_id"] = extracted_id
        if min_days_active > 0:
            today = reference_date or date.today()
            max_start = today - timedelta(days=min_days_active)
            params["start_date[max]"] = max_start.isoformat()
        return f"{META_AD_LIBRARY_BASE}?{urlencode(params, safe='[]')}"

    query = page_name.strip() or page_id.strip()
    return build_ad_library_search_url(
        query=query,
        country=country,
        active_status=active_status,
        media_type=media_type,
        min_days_active=min_days_active,
        exact_phrase=True,
        sort_by_impressions=sort_by_impressions,
        reference_date=reference_date,
    )
