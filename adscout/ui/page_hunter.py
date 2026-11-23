"""Página Streamlit: Buscar y Espiar en Meta Ad Library (búsquedas precisas + espía directo de página)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from adscout.models.market import MarketConfig
from adscout.services.meta_links import (
    build_ad_library_page_url,
    build_ad_library_search_url,
    extract_page_id,
)
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

ACTIVE_STATUS_PRESETS: dict[str, str] = {
    "Solo anuncios activos": "active",
    "Todos (activos e inactivos)": "all",
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
    st.header("🔎 Buscar y Espiar en Meta Ad Library")
    st.caption(
        "Abre búsquedas precisas ordenadas por **mayores impresiones** o salta directo a **todos los anuncios de una página** (costo $0)."
    )

    with st.container(border=True):
        s1, s2, s3 = st.columns(3)
        with s1:
            st.markdown("**1️⃣ Busca anuncios**")
            st.caption("Usa filtros precisos ordenados por mayores impresiones para ver los ganadores arriba.")
        with s2:
            st.markdown("**2️⃣ Espía la página completa**")
            st.caption("Pega el ID o enlace de una página para ver **todos** sus anuncios activos de golpe.")
        with s3:
            st.markdown("**3️⃣ Guarda y adapta**")
            st.caption("Guarda páginas ganadoras en **Favoritos** o adapta el anuncio al español con **IA**.")

    tab_page_spy, tab_search = st.tabs(
        [
            "🕵️ Espiar Página (Todos sus anuncios)",
            "🔎 Buscar Anuncios (Por palabra clave o checkout)",
        ]
    )

    with tab_page_spy:
        _render_page_spy_tab(ctx, active_market)

    with tab_search:
        _render_keyword_search_tab(ctx, active_market)


def _render_page_spy_tab(ctx: AppContext, active_market: MarketConfig) -> None:
    st.subheader("🕵️ Ver todos los anuncios de una página (ordenados por impresiones)")
    st.caption(
        "Pega el **ID de la página** (ej. `605901895933065`) o cualquier **enlace de Meta Ad Library**. "
        "AdScout arma automáticamente el enlace exacto de transparencia de página ordenado por mayores impresiones."
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

    o1, o2 = st.columns([1.6, 1.4])
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
            st.link_button(
                "🕵️ Abrir todos los anuncios de esta página en Meta Ad Library ↗",
                page_url,
                type="primary",
                use_container_width=True,
            )
            st.caption("Enlace generado con filtros exactos:")
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

    with st.expander("❓ ¿Cómo encuentro el ID de una página en Meta Ad Library?"):
        st.markdown(
            """
            1. Abre cualquier búsqueda en la pestaña **🔎 Buscar Anuncios** y haz clic en un anuncio interesante.
            2. Haz clic en el **nombre de la página** o en **Ver detalles del anuncio → Transparencia de la página → Ver todo**.
            3. Copia la URL del navegador (contiene `view_all_page_id=123456789...`) y pégala arriba.
            4. ¡Listo! Con 1 clic ves **todos los anuncios activos** de esa página ordenados por **mayores impresiones** y la puedes guardar en Favoritos.
            """
        )

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


def _render_keyword_search_tab(ctx: AppContext, active_market: MarketConfig) -> None:
    st.subheader("🔎 Buscar anuncios ganadores por país y filtro")

    all_codes = list(ctx.markets.keys())
    default_selected = [active_market.code]
    for extra in ("usa", "chile", "peru", "argentina", "colombia"):
        if extra in all_codes and extra not in default_selected and len(default_selected) < 2:
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
            "Antigüedad (señal de rentabilidad)",
            options=list(AGE_PRESETS.keys()),
            index=2,
        )
        min_days = AGE_PRESETS[age_label]
    with c3:
        media_label = st.selectbox(
            "Formato",
            options=list(MEDIA_PRESETS.keys()),
            index=0,
        )
        media_type = MEDIA_PRESETS[media_label]

    p1, p2 = st.columns(2)
    with p1:
        sort_by_impressions = st.checkbox(
            "🔥 Ordenar por mayores impresiones (ganadores arriba)",
            value=True,
        )
    with p2:
        exact_phrase = st.checkbox(
            "🎯 Búsqueda exacta (más precisa, menos ruido)",
            value=True,
            help="Usa coincidencia exacta de frase/dominio en Meta. En combos con `|` se ajusta automáticamente.",
        )

    mode = st.radio(
        "¿Qué quieres buscar?",
        options=[
            "🔥 Combos (Producto | Canal)",
            "💳 Checkouts (Hotmart, Kiwify, Stan...)",
            "📚 Keywords de Ebooks y PDFs",
            "✏️ Búsqueda propia",
        ],
        horizontal=True,
    )

    custom_queries: list[str] = []
    if mode.startswith("🔥"):
        with st.container(border=True):
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

    elif mode.startswith("✏️"):
        raw_custom = st.text_input(
            "Escribe uno o varios términos separados por coma",
            value="pdf | api.whatsapp.com, ebook | hotmart.com",
        )
        custom_queries = [q.strip() for q in raw_custom.split(",") if q.strip()]

    if not selected_codes:
        st.info("Selecciona al menos un país arriba para generar tus enlaces.")
        return

    st.divider()
    table_rows: list[dict[str, str]] = []

    for code in selected_codes:
        mkt = ctx.markets[code]
        if mode.startswith("🔥"):
            terms = custom_queries
            category_label = "Combo (|)"
        elif mode.startswith("📚"):
            terms = mkt.keywords
            category_label = "Keyword"
        elif mode.startswith("💳"):
            terms = mkt.checkout_domains
            category_label = "Checkout"
        else:
            terms = custom_queries
            category_label = "Personalizado"

        if not terms:
            continue

        with st.expander(
            f"🌍 {mkt.name} ({mkt.country}) — {len(terms)} búsquedas listas",
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
                    exact_phrase=exact_phrase,
                    sort_by_impressions=sort_by_impressions,
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
                    exact_phrase=exact_phrase,
                    sort_by_impressions=sort_by_impressions,
                )
                table_rows.append(
                    {
                        "País": f"{mkt.name} ({mkt.country})",
                        "Tipo": category_label,
                        "Búsqueda": term,
                        "Antigüedad": f"≥ {min_days} días" if min_days > 0 else "Todos activos",
                        "Abrir en Meta Ad Library": url,
                    }
                )

    if table_rows:
        with st.expander(f"📋 Ver tabla completa de enlaces ({len(table_rows)})", expanded=False):
            df_links = pd.DataFrame(table_rows)
            st.dataframe(
                df_links,
                width="stretch",
                hide_index=True,
                column_config={
                    "Abrir en Meta Ad Library": st.column_config.LinkColumn(
                        "Meta Ad Library",
                        display_text="Abrir en Facebook ↗",
                    ),
                },
            )
