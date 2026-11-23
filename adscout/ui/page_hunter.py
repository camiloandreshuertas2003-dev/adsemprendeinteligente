"""Página Streamlit: Buscar y Espiar Anuncios Reales en Meta Ad Library (Automático con Apify + Enlaces Directos)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from adscout.models.market import MarketConfig
from adscout.services.meta_links import (
    build_ad_library_page_url,
    build_ad_library_search_url,
    extract_page_id,
    is_real_meta_id,
)
from adscout.sources import (
    ApifySource,
    InvalidTokenError,
    RateLimitError,
    SourceConfigError,
    SourceError,
)
from adscout.ui.context import AppContext

AGE_PRESETS: dict[str, int] = {
    "Todos los activos": 0,
    "Activos ≥ 15 días": 15,
    "Activos ≥ 30 días (ganadores)": 30,
    "Activos ≥ 60 días (muy escalados)": 60,
}

MEDIA_PRESETS: dict[str, str] = {
    "Todos los formatos": "all",
    "Solo videos": "video",
    "Solo imágenes": "image",
}

ACTIVE_STATUS_PRESETS: dict[str, str] = {
    "Solo anuncios activos": "active",
    "Todos (activos e inactivos)": "all",
}

QUICK_SEARCH_PRESETS: list[str] = [
    "pdf | api.whatsapp.com",
    "ebook | hotmart.com",
    "pdf | hotmart.com",
    "pdf | kiwify.com.br",
    "ebook | kiwify.com.br",
    "pdf | wa.me",
    "guia | api.whatsapp.com",
    "pdf | stan.store",
    "pdf | gumroad.com",
    "ebook | whop.com",
    "hotmart.com",
    "kiwify.com.br",
    "Escribir mi propia búsqueda...",
]


def _get_active_apify_token(ctx: AppContext) -> str | None:
    """Devuelve el token de Apify desde Secrets/.env o desde la sesión actual."""
    if ctx.settings.apify_api_token:
        return ctx.settings.apify_api_token
    session_token = str(st.session_state.get("session_apify_token", "")).strip()
    return session_token or None


def _render_real_ads_table(ctx: AppContext, market: MarketConfig, filter_page_id: str | None = None) -> None:
    """Muestra la tabla de anuncios REALES guardados (con links exactos a Meta y checkout)."""
    ranked = ctx.pipeline.get_ranked_ads(market=market, only_active=False)
    real_items = [
        i
        for i in ranked
        if is_real_meta_id(i["ad"].page_id) or is_real_meta_id(i["ad"].ad_id)
    ]
    if filter_page_id:
        real_items = [i for i in real_items if i["ad"].page_id == filter_page_id]

    if not real_items:
        return

    st.subheader(f"✅ Anuncios reales encontrados ({len(real_items)})")
    rows = []
    for item in real_items:
        ad = item["ad"]
        rows.append(
            {
                "Puntaje": item["score"].total_score,
                "Página": ad.page_name,
                "Titular": ad.headline or "(sin titular)",
                "Días activo": item["days_active"],
                "Variantes": ad.variants_count,
                "Anuncios pág.": item["page_active_ads"],
                "Checkout": item["matched_checkout"] or (ad.link_domain or "-"),
                "Espiar Página (FB)": item["fb_page_url"],
                "Ver Anuncio (FB)": item["fb_ad_url"],
                "Web / Checkout": ad.link_url,
            }
        )

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        column_config={
            "Puntaje": st.column_config.ProgressColumn("Puntaje", min_value=0, max_value=100, format="%.1f"),
            "Espiar Página (FB)": st.column_config.LinkColumn("Página FB", display_text="Ver todos sus anuncios ↗"),
            "Ver Anuncio (FB)": st.column_config.LinkColumn("Anuncio FB", display_text="Abrir anuncio ↗"),
            "Web / Checkout": st.column_config.LinkColumn("Checkout / Web", display_text="Abrir web ↗"),
        },
    )


def render_hunter_page(ctx: AppContext, active_market: MarketConfig) -> None:
    st.header("🔎 Buscar y Espiar Anuncios Reales")
    st.caption(
        "Busca automáticamente anuncios **100% reales** en Meta Ad Library ordenados por mayores impresiones "
        "y obtén enlaces directos a cada página (`view_all_page_id`) y su checkout."
    )

    apify_token = _get_active_apify_token(ctx)
    if apify_token:
        st.success("🟢 **Búsqueda automática activa (Apify conectado)** — lista para extraer anuncios reales en 1 clic.")
    else:
        with st.container(border=True):
            st.warning(
                "🔑 **Conecta tu clave de Apify para buscar automáticamente** "
                "(si ya la pegaste en Streamlit Cloud → Settings → Secrets como `APIFY_API_TOKEN`, recarga la página)."
            )
            tk_col1, tk_col2 = st.columns([3, 1.2])
            with tk_col1:
                pasted_token = st.text_input(
                    "Pega tu APIFY_API_TOKEN aquí para usarla ahora mismo",
                    type="password",
                    placeholder="apify_api_...",
                    key="apify_token_input_box",
                )
            with tk_col2:
                st.write("")
                st.write("")
                if st.button("Conectar ahora", type="primary", use_container_width=True):
                    if pasted_token.strip():
                        st.session_state["session_apify_token"] = pasted_token.strip()
                        st.rerun()
                    else:
                        st.error("Pega tu clave de Apify primero.")

    tab_auto_search, tab_page_spy = st.tabs(
        [
            "🚀 Buscar Anuncios Reales (Automático)",
            "🕵️ Espiar una Página (Todos sus anuncios)",
        ]
    )

    with tab_auto_search:
        _render_auto_search_tab(ctx, active_market, apify_token)

    with tab_page_spy:
        _render_page_spy_tab(ctx, active_market, apify_token)


def _render_auto_search_tab(
    ctx: AppContext,
    active_market: MarketConfig,
    apify_token: str | None,
) -> None:
    market_codes = list(ctx.markets.keys())
    default_idx = market_codes.index(active_market.code) if active_market.code in market_codes else 0

    c1, c2 = st.columns([1.3, 2.2])
    with c1:
        chosen_code = st.selectbox(
            "País a buscar",
            options=market_codes,
            index=default_idx,
            format_func=lambda code: f"{ctx.markets[code].name} ({ctx.markets[code].country})",
            key="auto_search_country",
        )
        target_market = ctx.markets[chosen_code]
    with c2:
        preset_choice = st.selectbox(
            "Qué buscar (combos ganadores o búsqueda propia)",
            options=QUICK_SEARCH_PRESETS,
            index=0,
            key="auto_search_preset",
        )

    if preset_choice == "Escribir mi propia búsqueda...":
        query_text = st.text_input(
            "Escribe tu búsqueda (ej: recetas pdf, ebook | hotmart.com, hotmart.com)",
            value="ebook",
            key="auto_search_custom_query",
        ).strip()
    else:
        query_text = preset_choice

    f1, f2, f3 = st.columns([1.4, 1.2, 1.0])
    with f1:
        age_label = st.selectbox(
            "Antigüedad mínima",
            options=list(AGE_PRESETS.keys()),
            index=2,
            key="auto_search_age",
        )
        min_days = AGE_PRESETS[age_label]
    with f2:
        media_label = st.selectbox(
            "Formato",
            options=list(MEDIA_PRESETS.keys()),
            index=0,
            key="auto_search_media",
        )
        media_type = MEDIA_PRESETS[media_label]
    with f3:
        limit = st.number_input(
            "Máx. anuncios",
            min_value=5,
            max_value=100,
            value=25,
            step=5,
            key="auto_search_limit",
            help="20–30 anuncios tarda ~25 segundos y consume muy pocos centavos de tu crédito gratis de Apify.",
        )

    o1, o2 = st.columns(2)
    with o1:
        sort_by_impressions = st.checkbox(
            "🔥 Ordenar por mayores impresiones (ganadores arriba)",
            value=True,
            key="auto_search_sort_imp",
        )
    with o2:
        exact_phrase = st.checkbox(
            "🎯 Búsqueda exacta (más precisa)",
            value=True,
            key="auto_search_exact",
        )

    search_url = build_ad_library_search_url(
        query=query_text or "ebook",
        country=target_market.country,
        active_status="active",
        media_type=media_type,
        min_days_active=min_days,
        exact_phrase=exact_phrase,
        sort_by_impressions=sort_by_impressions,
    )

    b1, b2 = st.columns([1.8, 1.2])
    with b1:
        run_clicked = st.button(
            "🚀 Buscar anuncios reales ahora",
            type="primary",
            use_container_width=True,
            disabled=not bool(apify_token and query_text),
            key="auto_search_run_btn",
        )
    with b2:
        st.link_button(
            "🔗 Ver esta búsqueda en Facebook ↗",
            search_url,
            use_container_width=True,
        )

    if run_clicked and apify_token and query_text:
        try:
            source = ApifySource(
                api_token=apify_token,
                actor_id=ctx.settings.apify_actor_id,
                timeout_seconds=max(ctx.settings.apify_timeout_seconds, 180.0),
                custom_urls=[search_url],
                media_type=media_type,
                min_days_active=min_days,
                exact_phrase=exact_phrase,
                sort_by_impressions=sort_by_impressions,
            )
            with st.spinner(
                f"Extrayendo hasta {int(limit)} anuncios reales de Meta Ad Library ({target_market.name}) con Apify... "
                "Esto suele tardar entre 20 y 60 segundos."
            ):
                ctx.repository.delete_demo_ads()
                stats = ctx.pipeline.run(
                    source=source,
                    market=target_market,
                    keywords=[query_text],
                    limit=int(limit),
                )

            if stats["total_fetched"] == 0:
                st.warning(
                    "Meta no devolvió anuncios con esos filtros exactos. "
                    "Prueba bajando la **Antigüedad mínima** a `Todos los activos` o cambiando la palabra clave."
                )
            else:
                st.success(
                    f"¡Listo! Se extrajeron **{stats['total_fetched']} anuncios reales** "
                    f"({stats['inserted']} nuevos, {stats['updated']} actualizados). "
                    "Todos los enlaces de abajo son 100% reales."
                )
        except InvalidTokenError as exc:
            st.error(f"Clave de Apify inválida: {exc}")
        except RateLimitError as exc:
            st.warning(f"Límite de Apify alcanzado: {exc}")
        except (SourceConfigError, SourceError) as exc:
            st.error(f"Error al extraer anuncios con Apify: {exc}")

    st.divider()
    _render_real_ads_table(ctx, target_market)


def _render_page_spy_tab(
    ctx: AppContext,
    active_market: MarketConfig,
    apify_token: str | None,
) -> None:
    st.subheader("🕵️ Ver y extraer todos los anuncios de una página")
    st.caption(
        "Pega el **ID de la página** (ej. `605901895933065`) o cualquier **enlace de Meta Ad Library** "
        "para abrir o extraer todos sus anuncios activos ordenados por mayores impresiones."
    )

    raw_input = st.text_input(
        "ID de la página o enlace de Facebook Ad Library",
        placeholder="Ej: 605901895933065  o  https://www.facebook.com/ads/library/?...view_all_page_id=605901895933065",
        key="page_spy_raw_input",
    )

    country_options = ["ALL"] + [ctx.markets[c].country for c in ctx.markets]
    country_labels = {"ALL": "🌍 Todos los países (ALL — Recomendado)"}
    for mkt in ctx.markets.values():
        country_labels[mkt.country] = f"{mkt.name} ({mkt.country})"

    f1, f2, f3 = st.columns([1.8, 1.3, 1.2])
    with f1:
        spy_country = st.selectbox(
            "País",
            options=country_options,
            index=0,
            format_func=lambda c: country_labels.get(c, c),
            key="page_spy_country",
        )
    with f2:
        spy_status_label = st.selectbox(
            "Estado",
            options=list(ACTIVE_STATUS_PRESETS.keys()),
            index=0,
            key="page_spy_status",
        )
        spy_status = ACTIVE_STATUS_PRESETS[spy_status_label]
    with f3:
        spy_media_label = st.selectbox(
            "Formato",
            options=list(MEDIA_PRESETS.keys()),
            index=0,
            key="page_spy_media",
        )
        spy_media = MEDIA_PRESETS[spy_media_label]

    o1, o2, o3 = st.columns([1.5, 1.4, 0.9])
    with o1:
        spy_age_label = st.selectbox(
            "Antigüedad mínima",
            options=list(AGE_PRESETS.keys()),
            index=0,
            key="page_spy_age",
        )
        spy_min_days = AGE_PRESETS[spy_age_label]
    with o2:
        st.write("")
        st.write("")
        spy_sort_impressions = st.checkbox(
            "Ordenar por mayores impresiones (desc)",
            value=True,
            key="page_spy_sort_imp",
        )
    with o3:
        spy_limit = st.number_input(
            "Máx. anuncios",
            min_value=5,
            max_value=100,
            value=30,
            step=5,
            key="page_spy_limit",
        )

    extracted_id = extract_page_id(raw_input)

    if raw_input.strip() and not extracted_id:
        st.warning(
            "No detecté un ID numérico de página válido. Pega un número como `605901895933065` "
            "o una URL de Meta Ad Library que contenga `view_all_page_id=...`."
        )
    elif extracted_id:
        page_url = build_ad_library_page_url(
            page_id=extracted_id,
            country=spy_country,
            active_status=spy_status,
            media_type=spy_media,
            sort_by_impressions=spy_sort_impressions,
            min_days_active=spy_min_days,
        )

        with st.container(border=True):
            st.success(f"Página detectada: ID **`{extracted_id}`**")
            pb1, pb2 = st.columns([1.5, 1.5])
            with pb1:
                scrape_page_clicked = st.button(
                    "🚀 Extraer anuncios reales de esta página (Apify)",
                    type="primary",
                    use_container_width=True,
                    disabled=not bool(apify_token),
                    key=f"spy_scrape_page_{extracted_id}",
                )
            with pb2:
                st.link_button(
                    "🕵️ Abrir todos sus anuncios en Facebook ↗",
                    page_url,
                    use_container_width=True,
                )

            if scrape_page_clicked and apify_token:
                try:
                    source = ApifySource(
                        api_token=apify_token,
                        actor_id=ctx.settings.apify_actor_id,
                        timeout_seconds=max(ctx.settings.apify_timeout_seconds, 180.0),
                        custom_urls=[page_url],
                    )
                    with st.spinner(f"Extrayendo anuncios reales de la página {extracted_id} con Apify..."):
                        ctx.repository.delete_demo_ads()
                        stats = ctx.pipeline.run(
                            source=source,
                            market=active_market,
                            keywords=[extracted_id],
                            limit=int(spy_limit),
                        )
                    st.success(
                        f"¡Listo! Extraídos **{stats['total_fetched']} anuncios reales** de la página `{extracted_id}`."
                    )
                except (InvalidTokenError, RateLimitError, SourceConfigError, SourceError) as exc:
                    st.error(f"Error al extraer anuncios de la página: {exc}")

            st.caption("Enlace exacto generado:")
            st.code(page_url, language=None)

            st.markdown("**⭐ Guardar esta página en tus Favoritos**")
            g1, g2, g3 = st.columns([1.5, 2.2, 1.1])
            with g1:
                fav_name = st.text_input(
                    "Nombre de la página",
                    value=f"Página {extracted_id}",
                    key=f"spy_fav_name_{extracted_id}",
                )
            with g2:
                fav_notes = st.text_input(
                    "Nota rápida (ej: Ebook recetas, 15 anuncios activos)",
                    value="",
                    key=f"spy_fav_notes_{extracted_id}",
                )
            with g3:
                st.write("")
                st.write("")
                if st.button("Guardar ⭐", use_container_width=True, key=f"spy_fav_save_{extracted_id}"):
                    ctx.repository.upsert_saved_offer(
                        page_id=extracted_id,
                        country=spy_country,
                        page_name=fav_name.strip() or f"Página {extracted_id}",
                        status="Para modelar",
                        notes=fav_notes.strip(),
                        fb_page_url=page_url,
                        checkout_url=None,
                    )
                    st.success(f"Guardada **{fav_name.strip() or extracted_id}** en Favoritos.")

        _render_real_ads_table(ctx, active_market, filter_page_id=extracted_id)

    saved_offers = ctx.repository.list_saved_offers()
    if saved_offers:
        st.divider()
        st.subheader("⭐ Tus páginas guardadas (acceso en 1 clic)")
        for s in saved_offers[:10]:
            direct_url = build_ad_library_page_url(
                page_id=s["page_id"],
                page_name=s["page_name"],
                country=s["country"] or "ALL",
                sort_by_impressions=True,
            )
            r1, r2, r3 = st.columns([2.2, 2.3, 1.5])
            with r1:
                st.markdown(f"**{s['page_name']}** · `{s['country']}` · _{s['status']}_")
            with r2:
                st.caption(s["notes"] or f"ID: {s['page_id']}")
            with r3:
                st.link_button("🕵️ Ver anuncios ↗", direct_url, use_container_width=True)
