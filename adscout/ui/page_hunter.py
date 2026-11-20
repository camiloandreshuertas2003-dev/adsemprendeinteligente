"""Página Streamlit: Cazador Rápido — Lanzador multi-país en 1 clic hacia Meta Ad Library."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from adscout.models.market import MarketConfig
from adscout.services.meta_links import build_ad_library_search_url
from adscout.ui.context import AppContext

AGE_PRESETS: dict[str, int] = {
    "Todos los activos (sin filtro de fecha)": 0,
    "Activos ≥ 15 días (en tracción)": 15,
    "Activos ≥ 30 días (señal fuerte de ventas)": 30,
    "Activos ≥ 60 días (ganador consolidado)": 60,
}

MEDIA_PRESETS: dict[str, str] = {
    "Todos los formatos": "all",
    "Solo videos": "video",
    "Solo imágenes": "image",
}


def render_hunter_page(ctx: AppContext, active_market: MarketConfig) -> None:
    st.header("🎯 Cazador Rápido — Meta Ad Library Multi-País")
    st.caption(
        "Genera enlaces directos ya filtrados a la Biblioteca de Anuncios de Facebook para cazar "
        "ebooks, PDFs, plantillas y pasarelas de pago en varios mercados a la vez (costo $0)."
    )

    all_codes = list(ctx.markets.keys())
    default_selected = [active_market.code]
    for extra in ("usa", "brasil", "espana", "francia"):
        if extra in all_codes and extra not in default_selected and len(default_selected) < 3:
            default_selected.append(extra)

    c1, c2, c3 = st.columns([2.2, 1.5, 1.3])
    with c1:
        selected_codes = st.multiselect(
            "Países a investigar",
            options=all_codes,
            default=default_selected,
            format_func=lambda code: f"{ctx.markets[code].name} ({ctx.markets[code].country})",
        )
    with c2:
        age_label = st.selectbox(
            "Filtro de ganadores (antigüedad)",
            options=list(AGE_PRESETS.keys()),
            index=2,
        )
        min_days = AGE_PRESETS[age_label]
    with c3:
        media_label = st.selectbox(
            "Formato creativo",
            options=list(MEDIA_PRESETS.keys()),
            index=0,
        )
        media_type = MEDIA_PRESETS[media_label]

    mode = st.radio(
        "¿Qué quieres cazar hoy?",
        options=[
            "📚 Ebooks, PDFs y Productos Digitales (keywords nativas)",
            "💳 Pasarelas de Checkout (Hotmart, Kiwify, Stan, Whop, Gumroad...)",
            "🔎 Búsqueda personalizada (nicho o término propio)",
        ],
        horizontal=True,
    )

    custom_queries: list[str] = []
    if mode.startswith("🔎"):
        raw_custom = st.text_input(
            "Escribe uno o varios términos separados por coma (ej: recetas pdf, pilates ebook, trading guide, hotmart.com)",
            value="ebook, pdf",
        )
        custom_queries = [q.strip() for q in raw_custom.split(",") if q.strip()]

    if not selected_codes:
        st.info("Selecciona al menos un país arriba para generar tus enlaces de caza en Meta Ad Library.")
        return

    st.divider()

    # Botones rápidos por país (los primeros 4 términos) + tabla completa clicable
    table_rows: list[dict[str, str]] = []

    for code in selected_codes:
        mkt = ctx.markets[code]
        if mode.startswith("📚"):
            terms = mkt.keywords
            category_label = "Keyword digital"
        elif mode.startswith("💳"):
            terms = mkt.checkout_domains
            category_label = "Checkout"
        else:
            terms = custom_queries
            category_label = "Personalizado"

        if not terms:
            continue

        with st.expander(
            f"🌍 {mkt.name} ({mkt.country} · {mkt.language}) — {len(terms)} enlaces listos",
            expanded=(len(selected_codes) <= 3),
        ):
            quick_terms = terms[:6]
            cols = st.columns(min(3, len(quick_terms)))
            for idx, term in enumerate(quick_terms):
                url = build_ad_library_search_url(
                    query=term,
                    country=mkt.country,
                    active_status="active",
                    media_type=media_type,
                    min_days_active=min_days,
                )
                with cols[idx % len(cols)]:
                    st.link_button(
                        f"🔎 {term}",
                        url,
                        use_container_width=True,
                    )

            for term in terms:
                url = build_ad_library_search_url(
                    query=term,
                    country=mkt.country,
                    active_status="active",
                    media_type=media_type,
                    min_days_active=min_days,
                )
                table_rows.append(
                    {
                        "País": f"{mkt.name} ({mkt.country})",
                        "Tipo": category_label,
                        "Término / Pasarela": term,
                        "Antigüedad": f"≥ {min_days} días" if min_days > 0 else "Todos activos",
                        "Abrir en Meta Ad Library": url,
                    }
                )

    if table_rows:
        st.subheader("📋 Matriz completa de enlaces de investigación")
        df_links = pd.DataFrame(table_rows)
        st.dataframe(
            df_links,
            width="stretch",
            hide_index=True,
            column_config={
                "Abrir en Meta Ad Library": st.column_config.LinkColumn(
                    "Meta Ad Library",
                    display_text="Abrir búsqueda en Facebook ↗",
                ),
            },
        )
        st.info(
            "💡 **Tip rápido:** Cuando encuentres anuncios ganadores en Facebook, expórtalos a CSV/JSON "
            "(o usa Apify) e impórtalos en **📥 Mercado e Ingesta** para puntuarlos, agruparlos por página "
            "y seguir cuántos días siguen activos."
        )
