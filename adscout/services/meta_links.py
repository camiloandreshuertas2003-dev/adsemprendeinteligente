"""Generación de enlaces directos hacia la Biblioteca de Anuncios de Meta (Facebook Ad Library)."""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urlparse

import httpx

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


def _clean_phone_digits(raw: str | None) -> str | None:
    """Limpia un teléfono dejando solo dígitos (entre 8 y 15 dígitos)."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if 8 <= len(digits) <= 15:
        return digits
    return None


def _unwrap_facebook_redirect(url: str) -> str:
    """Si la URL es un redirect l.facebook.com/l.php?u=..., extrae la URL real."""
    try:
        parsed = urlparse(url)
        if parsed.hostname and "facebook.com" in parsed.hostname.lower() and parsed.path.startswith("/l.php"):
            u_vals = parse_qs(parsed.query).get("u")
            if u_vals and u_vals[0]:
                return unquote(u_vals[0])
    except Exception:
        pass
    return url


def _extract_whatsapp_from_text_or_url(blob: str) -> tuple[str | None, str | None]:
    """Busca `wa.me/<num>` o `whatsapp.com/send?phone=<num>` dentro de una URL o texto/HTML.

    Devuelve `(digits, prefilled_text)`.
    """
    if not blob:
        return None, None

    # 1. api.whatsapp.com/send?phone=... o web.whatsapp.com/send?phone=...
    for match in re.finditer(
        r"https?://(?:api|web)\.whatsapp\.com/send\?[^\s\"'<>]+",
        blob,
        flags=re.IGNORECASE,
    ):
        raw_url = match.group(0).replace("&amp;", "&")
        qs = parse_qs(urlparse(raw_url).query)
        phone_vals = qs.get("phone") or []
        digits = _clean_phone_digits(phone_vals[0]) if phone_vals else None
        if digits:
            text_vals = qs.get("text") or []
            return digits, unquote(text_vals[0]) if text_vals else None

    # 2. wa.me/<digits>
    for match in re.finditer(
        r"(?:https?://)?wa\.me/(\+?[0-9]{8,15})(?:\?([^\s\"'<>]+))?",
        blob,
        flags=re.IGNORECASE,
    ):
        digits = _clean_phone_digits(match.group(1))
        if digits:
            prefilled = None
            if match.group(2):
                qs = parse_qs(match.group(2).replace("&amp;", "&"))
                if qs.get("text"):
                    prefilled = unquote(qs["text"][0])
            return digits, prefilled

    return None, None


def extract_whatsapp_info(
    link_url: str | None = None,
    ad_text: str = "",
    cta: str = "",
    raw_json: dict[str, Any] | None = None,
) -> dict[str, str | None]:
    """Extrae número de WhatsApp (si existe) desde el enlace, copy o metadatos del anuncio."""
    candidates: list[str] = []
    if link_url:
        candidates.append(_unwrap_facebook_redirect(link_url.strip()))

    if isinstance(raw_json, dict):
        snap = raw_json.get("snapshot") if isinstance(raw_json.get("snapshot"), dict) else {}
        for key in ("link_url", "linkUrl", "cta_link"):
            val = raw_json.get(key) or snap.get(key)
            if isinstance(val, str) and val.strip():
                candidates.append(_unwrap_facebook_redirect(val.strip()))
        cards = snap.get("cards")
        if isinstance(cards, list):
            for card in cards[:5]:
                if isinstance(card, dict) and isinstance(card.get("link_url"), str):
                    candidates.append(_unwrap_facebook_redirect(card["link_url"].strip()))

    for url in candidates:
        digits, prefilled = _extract_whatsapp_from_text_or_url(url)
        if digits:
            return {
                "phone": f"+{digits}",
                "wa_url": f"https://wa.me/{digits}",
                "prefilled_text": prefilled,
                "source": "link",
            }

    if ad_text:
        digits, prefilled = _extract_whatsapp_from_text_or_url(ad_text)
        if digits:
            return {
                "phone": f"+{digits}",
                "wa_url": f"https://wa.me/{digits}",
                "prefilled_text": prefilled,
                "source": "copy",
            }
        # Teléfono internacional explícito en el copy (ej. +55 11 99999-9999 o +57 300 123 4567)
        intl_match = re.search(r"\+\d{1,3}[\s.-]?\(?\d{1,4}\)?[\s.-]?\d{3,5}[\s.-]?\d{3,5}", ad_text)
        if intl_match:
            digits = _clean_phone_digits(intl_match.group(0))
            if digits:
                return {
                    "phone": f"+{digits}",
                    "wa_url": f"https://wa.me/{digits}",
                    "prefilled_text": None,
                    "source": "copy",
                }

    # Detectar si es un botón nativo de Meta Click-to-WhatsApp (donde Meta oculta el número)
    cta_blob = f"{cta} {link_url or ''}".lower()
    raw_cta_type = ""
    if isinstance(raw_json, dict):
        snap = raw_json.get("snapshot") if isinstance(raw_json.get("snapshot"), dict) else {}
        raw_cta_type = str(raw_json.get("cta_type") or snap.get("cta_type") or "").upper()
    if "WHATSAPP" in raw_cta_type or "whatsapp" in cta_blob or "wa.link" in cta_blob:
        return {
            "phone": None,
            "wa_url": None,
            "prefilled_text": None,
            "source": "native_hidden" if "wa.link" not in cta_blob else "shortlink",
        }

    return {"phone": None, "wa_url": None, "prefilled_text": None, "source": None}


def resolve_whatsapp_from_url(url: str, timeout: float = 6.0) -> dict[str, str | None]:
    """Sigue redirecciones (wa.link, bit.ly, landing pages) para intentar extraer un WhatsApp real."""
    if not url or not url.strip():
        return {"phone": None, "wa_url": None, "prefilled_text": None, "source": None}

    cleaned = _unwrap_facebook_redirect(url.strip())
    if not cleaned.startswith(("http://", "https://")):
        cleaned = f"https://{cleaned}"

    # Chequeo directo antes de hacer red
    digits, prefilled = _extract_whatsapp_from_text_or_url(cleaned)
    if digits:
        return {
            "phone": f"+{digits}",
            "wa_url": f"https://wa.me/{digits}",
            "prefilled_text": prefilled,
            "source": "link",
        }

    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AdScoutBot/1.0)"},
        ) as client:
            resp = client.get(cleaned)
            final_url = str(resp.url)
            digits, prefilled = _extract_whatsapp_from_text_or_url(final_url)
            if digits:
                return {
                    "phone": f"+{digits}",
                    "wa_url": f"https://wa.me/{digits}",
                    "prefilled_text": prefilled,
                    "source": "redirect",
                }
            # Escanear los primeros 150KB del HTML buscando botones wa.me / api.whatsapp.com
            content_type = resp.headers.get("content-type", "").lower()
            if "text/html" in content_type or "text/plain" in content_type:
                body_sample = resp.text[:150_000]
                digits, prefilled = _extract_whatsapp_from_text_or_url(body_sample)
                if digits:
                    return {
                        "phone": f"+{digits}",
                        "wa_url": f"https://wa.me/{digits}",
                        "prefilled_text": prefilled,
                        "source": "landing",
                    }
    except Exception:
        pass

    return {"phone": None, "wa_url": None, "prefilled_text": None, "source": None}
