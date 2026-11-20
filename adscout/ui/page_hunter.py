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

PRO_COMBOS_PRESET: list[str] = [
    "pdf | api.whatsapp.com",
    "ebook | api.whatsapp.com",
    "pdf | wa.me",
    "guia | api.whatsapp.com",
    "pdf | hotmart.com",
    "ebook | hotmart.com",
    "pdf | kiwify.com.br",
    "ebook | kiwify.com.br",
    "pdf | stan.store",
    "pdf | gumroad.com",
    "pdf | payhip.com",
    "ebook | whop.com",
]

COMBO_PRODUCTS: list[str] = [
    "pdf",
    "ebook",
    "guia",
    "plantilla",
    "recetario",
    "metodo",
    "workbook",
    "curso online",
]

COMBO_CHANNELS: list[str] = [
    "api.whatsapp.com",
    "wa.me",
    "hotmart.com",
    "pay.hotmart.com",
    "kiwify.com.br",
    "stan.store",
    "gumroad.com",
    "payhip.com",
    "whop.com",
    "systeme.io",
    "digistore24.com",
]


def render_hunter_page(ctx: AppContext, active_market: MarketConfig) -> None:
    st.header("🎯 Cazador Rápido — Meta Ad Library Multi-País")
    st.caption(
        "Genera enlaces directos ya filtrados a la Biblioteca de Anuncios de Facebook — incluyendo "
        "combos booleanos con `|` como `pdf | api.whatsapp.com` — para cazar ebooks y PDFs en varios países (costo $0)."
    )

    all_codes = list(ctx.markets.keys())
    default_selected = [active_market.code]
    for extra in ("usa", "chile", "peru", "argentina", "colombia"):
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
        "Modo de caza en Meta Ad Library",
        options=[
            "🔥 Combos Pro con operador | (ej: pdf | api.whatsapp.com)",
            "📚 Keywords nativas de Ebooks y PDFs",
            "💳 Pasarelas de Checkout (Hotmart, Kiwify, Stan, Whop...)",
            "🔎 Búsqueda personalizada (término o combo propio)",
        ],
        horizontal=False,
    )

    custom_queries: list[str] = []
    if mode.startswith("🔥"):
        with st.container(border=True):
            st.markdown("**⚡ Constructor rápido de Combo (`Producto | Canal / Checkout`)**")
            cc1, cc2, cc3 = st.columns([1.4, 1.6, 1.4])
            with cc1:
                chosen_prod = st.selectbox("Producto digital", options=COMBO_PRODUCTS, index=0)
            with cc2:
                chosen_chan = st.selectbox("Canal o Pasarela", options=COMBO_CHANNELS, index=0)
            built_combo = f"{chosen_prod} | {chosen_chan}"
            with cc3:
                st.write("")
                st.code(built_combo, language=None)
            custom_queries = [built_combo] + [c for c in PRO_COMBOS_PRESET if c != built_combo]

    elif mode.startswith("🔎"):
        raw_custom = st.text_input(
            "Escribe uno o varios términos/combos separados por coma (ej: pdf | api.whatsapp.com, recetas pdf | hotmart.com)",
            value="pdf | api.whatsapp.com, ebook | hotmart.com",
        )
        custom_queries = [q.strip() for q in raw_custom.split(",") if q.strip()]

    if not selected_codes:
        st.info("Selecciona al menos un país arriba para generar tus enlaces de caza en Meta Ad Library.")
        return

    st.divider()

    table_rows: list[dict[str, str]] = []

    for code in selected_codes:
        mkt = ctx.markets[code]
        if mode.startswith("🔥"):
            terms = custom_queries
            category_label = "Combo Pro (|)"
        elif mode.startswith("📚"):
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
                        "Búsqueda en Meta": term,
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

    with st.expander("🧩 Cómo usar extensiones de Chrome a tu favor con AdScout (flujo de 2 minutos)"):
        st.markdown(
            """
            Puedes multiplicar tu velocidad combinando los enlaces de arriba con extensiones gratuitas de Chrome:
            1. **Abre un enlace de arriba** (por ejemplo `pdf | api.whatsapp.com` en Brasil, Chile o Perú).
            2. **Filtra visualmente en Facebook** con extensiones de Chrome como **Ad Library Helper / Foreplay / Meta Ad Library Filter** (te permiten filtrar en vivo por cantidad de anuncios activos de la misma página, ej. ≥ 5 anuncios).
            3. **Exporta a CSV/JSON en 1 clic** con **Instant Data Scraper** o un **Ad Library Exporter** de Chrome.
            4. **Sube ese CSV/JSON** en **📥 Mercado e Ingesta** → AdScout lo deduplica, puntúa (0–100), agrupa por anunciante en **🚀 Ofertas Escalando** y lo guarda permanentemente en tu base de datos **Supabase**.
            """
        )
