"""Fuente Fase 2 (FUENTE DE PAGO OPCIONAL): esqueleto funcional para actores de Apify.

Requiere cuenta de pago o créditos activos en Apify y configurar APIFY_API_TOKEN
y APIFY_ACTOR_ID en el archivo .env.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

import httpx

from adscout.models.ad import Ad
from adscout.models.market import MarketConfig
from adscout.services.meta_links import build_ad_library_search_url
from adscout.sources.base import (
    AdSource,
    InvalidTokenError,
    RateLimitError,
    SourceConfigError,
    SourceError,
)
from adscout.sources.csv_import import normalize_raw_record

logger = logging.getLogger("adscout.sources.apify")


class ApifySource(AdSource):
    """[FUENTE DE PAGO OPCIONAL] Ejecuta un actor de Apify y normaliza los resultados a Ad."""

    name = "apify"
    label = "Apify Actor Scraper (Automático — Plan gratis $5/mes)"
    description = (
        "Ejecuta el actor de Apify (`apify~facebook-ads-scraper`) para extraer anuncios 100% reales "
        "de la Biblioteca de Meta en cualquier país con IDs reales de página y anuncio."
    )
    is_paid = True

    def __init__(
        self,
        api_token: str | None = None,
        actor_id: str = "apify~facebook-ads-scraper",
        timeout_seconds: float = 180.0,
        max_retries: int = 2,
        base_backoff_seconds: float = 2.0,
        custom_urls: list[str] | None = None,
        media_type: str = "all",
        min_days_active: int = 0,
        exact_phrase: bool = False,
        sort_by_impressions: bool = True,
        transport: httpx.BaseTransport | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_token = (api_token or "").strip()
        raw_actor = (actor_id or "apify~facebook-ads-scraper").strip()
        self.actor_id = raw_actor.replace("/", "~")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.base_backoff_seconds = base_backoff_seconds
        self.custom_urls = [u.strip() for u in (custom_urls or []) if u and u.strip()]
        self.media_type = media_type
        self.min_days_active = min_days_active
        self.exact_phrase = exact_phrase
        self.sort_by_impressions = sort_by_impressions
        self._transport = transport
        self._sleep = sleep_fn

    def _build_actor_input(self, market_config: MarketConfig, keywords: list[str], limit: int) -> dict[str, Any]:
        """Construye las URLs públicas de búsqueda en Meta Ad Library como entrada del actor."""
        if self.custom_urls:
            return {
                "startUrls": [{"url": url} for url in self.custom_urls],
                "resultsLimit": limit,
                "isDetailsPerAd": True,
            }

        effective_keywords = [kw.strip() for kw in keywords if kw.strip()] or market_config.keywords
        start_urls = [
            {
                "url": build_ad_library_search_url(
                    query=kw,
                    country=market_config.country,
                    active_status="active",
                    media_type=self.media_type,
                    min_days_active=self.min_days_active,
                    exact_phrase=self.exact_phrase,
                    sort_by_impressions=self.sort_by_impressions,
                )
            }
            for kw in effective_keywords
        ]
        return {
            "startUrls": start_urls,
            "resultsLimit": limit,
            "country": market_config.country,
            "isDetailsPerAd": True,
        }

    def search(
        self,
        market_config: MarketConfig,
        keywords: list[str],
        limit: int = 100,
    ) -> list[Ad]:
        if not self.api_token:
            raise SourceConfigError(
                "APIFY_API_TOKEN no está configurado en .env. "
                "Apify es una fuente de pago opcional; para costo cero usa CsvImportSource."
            )

        url = f"https://api.apify.com/v2/acts/{self.actor_id}/run-sync-get-dataset-items"
        params = {"token": self.api_token, "clean": "true", "limit": str(limit)}
        actor_input = self._build_actor_input(market_config, keywords, limit)

        logger.info(
            "Ejecutando ApifySource (fuente de pago opcional) | actor=%s | país=%s | limite=%d",
            self.actor_id,
            market_config.country,
            limit,
        )

        items: list[dict[str, Any]] = []
        with httpx.Client(timeout=self.timeout_seconds, transport=self._transport) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    response = client.post(url, params=params, json=actor_input)
                except httpx.HTTPError as exc:
                    if attempt < self.max_retries:
                        self._sleep(self.base_backoff_seconds * (2**attempt))
                        continue
                    raise SourceError(f"Error de red ejecutando actor de Apify: {exc}") from exc

                if response.status_code in (401, 403):
                    raise InvalidTokenError(
                        "APIFY_API_TOKEN inválido o sin permisos para ejecutar el actor."
                    )

                if response.status_code == 402:
                    raise RateLimitError(
                        "Crédito mensual de Apify agotado (HTTP 402). Revisa tu consumo en console.apify.com."
                    )

                if response.status_code in (429, 500, 502, 503, 504):
                    if attempt < self.max_retries:
                        self._sleep(self.base_backoff_seconds * (2**attempt))
                        continue
                    if response.status_code == 429:
                        raise RateLimitError("Límite de tasa alcanzado en la API de Apify.")
                    raise SourceError(f"Apify devolvió error HTTP {response.status_code}.")

                if response.status_code >= 400:
                    raise SourceError(
                        f"Error ejecutando actor de Apify (HTTP {response.status_code}): {response.text[:300]}"
                    )

                payload = response.json()
                if not isinstance(payload, list):
                    raise SourceError("La respuesta de Apify no es una lista de ítems del dataset.")
                items = [item for item in payload if isinstance(item, dict)]
                break

        ads: list[Ad] = []
        for idx, record in enumerate(items, start=1):
            try:
                ads.append(normalize_raw_record(record, market_config))
            except ValueError as exc:
                logger.warning("Ítem #%d de Apify omitido por faltar ad_id: %s", idx, exc)
            if len(ads) >= limit:
                break

        logger.info("ApifySource normalizó %d anuncios para %s", len(ads), market_config.country)
        return ads
