"""Página Streamlit: Ofertas Escalando — Agrupación por página/anunciante con enlaces directos a FB."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from adscout.models.market import MarketConfig
from adscout.services.pipeline import build_scaling_offers
from adscout.ui.context import AppContext


def render_offers_page(ctx: AppContext, active_market: MarketConfig) -> None:
    st.header("🚀 Ofertas y Páginas Escalando")
    st.caption(
        "Agrupa anuncios por anunciante para detectar quién está invirtiendo en múltiples creativos "
        "y manteniendo anuncios activos durante semanas (la señal más clara de un producto rentable)."
    )

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

    # Filtros rápidos
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

    # KPIs
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Páginas / Ofertas", len(filtered))
    k2.metric("🔥 Escalando fuerte", sum(1 for o in filtered if o["signal"].startswith("🔥")))
    k3.metric("⚡ Tracción activa", sum(1 for o in filtered if o["signal"].startswith("⚡")))
    k4.metric("Con checkout detectado", sum(1 for o in filtered if o["checkouts"] != "-"))

    if not filtered:
        st.warning("Ninguna oferta coincide con los filtros actuales.")
        return

    # Tarjetas destacadas Top 3
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
