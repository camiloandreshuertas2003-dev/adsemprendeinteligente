"""Página Streamlit: Ofertas Escalando y Favoritos (persistentes en Supabase/SQLite)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from adscout.models.market import MarketConfig
from adscout.services.pipeline import build_scaling_offers
from adscout.ui.context import AppContext

FAVORITE_STATUSES = ["Para modelar", "En revisión", "Modelado", "Descartado"]


def render_offers_page(ctx: AppContext, active_market: MarketConfig) -> None:
    st.header("🚀 Ofertas Escalando & Favoritos")
    st.caption(
        "Agrupa anuncios por anunciante para detectar quién está escalando un producto digital "
        "y guarda tus ofertas favoritas con estado y notas."
    )

    tab_offers, tab_favs = st.tabs(["🚀 Ofertas Escalando", "⭐ Mis Favoritos y Notas"])

    with tab_offers:
        _render_scaling_tab(ctx, active_market)

    with tab_favs:
        _render_favorites_tab(ctx)


def _render_scaling_tab(ctx: AppContext, active_market: MarketConfig) -> None:
    scope = st.radio(
        "Alcance del análisis",
        options=[
            f"Mercado actual: {active_market.name} ({active_market.country})",
            "🌍 Radar Global (Todos los mercados)",
        ],
        horizontal=True,
    )

    if scope.startswith("🌍"):
        ranked_items = ctx.pipeline.get_global_ranked_ads(markets=ctx.markets, only_active=False)
    else:
        ranked_items = ctx.pipeline.get_ranked_ads(market=active_market, only_active=False)

    if not ranked_items:
        st.info(
            "Aún no hay anuncios cargados. Ve a **📥 Mercado e Ingesta** para importar datos "
            "(o prueba con el archivo de ejemplo `brasil_ads_sample.csv`)."
        )
        return

    offers = build_scaling_offers(ranked_items)

    fc1, fc2, fc3, fc4 = st.columns([2, 1.2, 1.2, 1.8])
    with fc1:
        signal_filter = st.multiselect(
            "Señal de escalado",
            options=["🔥 Escalando fuerte", "⚡ Tracción activa", "🧪 En prueba"],
            default=[],
        )
    with fc2:
        min_active_ads = st.number_input("Mín. anuncios activos", min_value=0, max_value=500, value=1, step=1)
    with fc3:
        min_days = st.number_input("Mín. días activo", min_value=0, max_value=3650, value=0, step=1)
    with fc4:
        search_q = st.text_input("Buscar anunciante, titular o checkout", value="").strip().lower()

    filtered = []
    for offer in offers:
        if signal_filter and offer["signal"] not in signal_filter:
            continue
        if offer["active_ads"] < min_active_ads:
            continue
        if offer["max_days_active"] < min_days:
            continue
        if search_q:
            blob = f"{offer['page_name']} {offer['top_headline']} {offer['checkouts']} {offer['country']}".lower()
            if search_q not in blob:
                continue
        filtered.append(offer)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Páginas / Ofertas", len(filtered))
    k2.metric("🔥 Escalando fuerte", sum(1 for o in filtered if o["signal"].startswith("🔥")))
    k3.metric("⚡ Tracción activa", sum(1 for o in filtered if o["signal"].startswith("⚡")))
    k4.metric("Con checkout detectado", sum(1 for o in filtered if o["checkouts"] != "-"))

    if not filtered:
        st.warning("Ninguna oferta coincide con los filtros actuales.")
        return

    st.subheader("Top ofertas destacadas")
    top_n = filtered[:3]
    cards = st.columns(len(top_n))
    for idx, offer in enumerate(top_n):
        with cards[idx]:
            with st.container(border=True):
                st.markdown(f"**{offer['signal']}** · `{offer['country']}`")
                st.markdown(f"#### {offer['page_name']}")
                st.caption(offer["top_headline"])
                st.write(
                    f"**{offer['active_ads']}** activos · **{offer['max_days_active']}d** máx · "
                    f"**{offer['max_score']:.1f}** pts · Checkout: `{offer['checkouts']}`"
                )
                b1, b2 = st.columns(2)
                with b1:
                    st.link_button("Espiar Página FB ↗", offer["fb_page_url"], use_container_width=True)
                with b2:
                    if offer["top_link_url"]:
                        st.link_button("Ver Checkout ↗", offer["top_link_url"], use_container_width=True)
                    else:
                        st.link_button("Ver Anuncio FB ↗", offer["fb_top_ad_url"], use_container_width=True)

    st.divider()
    st.subheader("Tabla completa de ofertas agrupadas por anunciante")

    rows = [
        {
            "Señal": o["signal"],
            "Página / Anunciante": o["page_name"],
            "País": o["country"],
            "Puntaje máx.": o["max_score"],
            "Anuncios activos": o["active_ads"],
            "Variantes totales": o["total_variants"],
            "Máx. días activo": o["max_days_active"],
            "Checkout": o["checkouts"],
            "Espiar Página (FB)": o["fb_page_url"],
            "Mejor Anuncio (FB)": o["fb_top_ad_url"],
            "Página de Ventas": o["top_link_url"],
        }
        for o in filtered
    ]

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        column_config={
            "Puntaje máx.": st.column_config.ProgressColumn(
                "Puntaje máx.",
                min_value=0,
                max_value=100,
                format="%.1f",
            ),
            "Espiar Página (FB)": st.column_config.LinkColumn(
                "Espiar Página (FB)",
                display_text="Ver todos sus anuncios ↗",
            ),
            "Mejor Anuncio (FB)": st.column_config.LinkColumn(
                "Mejor Anuncio (FB)",
                display_text="Abrir anuncio ↗",
            ),
            "Página de Ventas": st.column_config.LinkColumn(
                "Página de Ventas",
                display_text="Abrir web/checkout ↗",
            ),
        },
    )

    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="Exportar ofertas escalando a CSV",
        data=csv_bytes,
        file_name="adscout_ofertas_escalando.csv",
        mime="text/csv",
    )

    st.divider()
    st.subheader("⭐ Guardar una oferta en Favoritos")
    offer_options = {
        f"{o['signal']} | {o['page_name']} ({o['country']}) — {o['active_ads']} activos": o
        for o in filtered
    }
    selected_label = st.selectbox("Elige una oferta para guardar", options=list(offer_options.keys()))
    selected_offer = offer_options[selected_label]

    s_col1, s_col2 = st.columns([1.2, 2.8])
    with s_col1:
        fav_status = st.selectbox("Estado", options=FAVORITE_STATUSES, index=0)
    with s_col2:
        fav_notes = st.text_input(
            "Notas (ej: PDF de recetas keto en BR, buen gancho para tropicalizar a CO/MX)",
            value="",
        )

    if st.button("Guardar en Favoritos ⭐", type="primary"):
        ctx.repository.upsert_saved_offer(
            page_id=selected_offer["page_id"],
            country=selected_offer["country"],
            page_name=selected_offer["page_name"],
            status=fav_status,
            notes=fav_notes.strip(),
            fb_page_url=selected_offer["fb_page_url"],
            checkout_url=selected_offer["top_link_url"],
        )
        st.success(f"Oferta **{selected_offer['page_name']}** guardada en Favoritos ({fav_status}).")


def _render_favorites_tab(ctx: AppContext) -> None:
    st.subheader("⭐ Ofertas guardadas para modelar / seguimiento")

    status_filter = st.selectbox(
        "Filtrar por estado",
        options=["Todos"] + FAVORITE_STATUSES,
        index=0,
    )
    saved = ctx.repository.list_saved_offers(
        status=None if status_filter == "Todos" else status_filter
    )

    if not saved:
        st.info(
            "Todavía no tienes ofertas guardadas en Favoritos. "
            "Ve a la pestaña **🚀 Ofertas Escalando** y guarda cualquier anunciante ganador."
        )
        return

    df_fav = pd.DataFrame(
        [
            {
                "Estado": s["status"],
                "Página / Anunciante": s["page_name"],
                "País": s["country"],
                "Notas": s["notes"] or "-",
                "Espiar Página (FB)": s["fb_page_url"],
                "Checkout / Web": s["checkout_url"],
                "Actualizado": str(s["updated_at"].date()),
            }
            for s in saved
        ]
    )

    st.dataframe(
        df_fav,
        width="stretch",
        hide_index=True,
        column_config={
            "Espiar Página (FB)": st.column_config.LinkColumn("Página FB", display_text="Abrir en FB ↗"),
            "Checkout / Web": st.column_config.LinkColumn("Web / Checkout", display_text="Abrir web ↗"),
        },
    )

    st.divider()
    del_options = {f"{s['page_name']} ({s['country']}) — {s['status']}": s for s in saved}
    chosen_del = st.selectbox("Gestionar oferta guardada", options=list(del_options.keys()))
    target = del_options[chosen_del]
    if st.button("Eliminar de Favoritos 🗑️"):
        ctx.repository.delete_saved_offer(page_id=target["page_id"], country=target["country"])
        st.success(f"Eliminada **{target['page_name']}** de Favoritos.")
        st.rerun()
