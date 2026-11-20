"""AdScout — Punto de entrada de la aplicación Streamlit."""

from __future__ import annotations

import streamlit as st

from adscout.ui.context import build_app_context
from adscout.ui.page_detail import render_detail_page
from adscout.ui.page_hunter import render_hunter_page
from adscout.ui.page_market import render_market_page
from adscout.ui.page_offers import render_offers_page
from adscout.ui.page_ranking import render_ranking_page
from adscout.ui.page_trends import render_trends_page


def main() -> None:
    st.set_page_config(
        page_title="AdScout — Cazador de Productos Digitales",
        page_icon="🔎",
        layout="wide",
    )

    ctx = build_app_context()

    with st.sidebar:
        st.title("🔎 AdScout")
        st.caption("Cazador multi-mercado de ebooks, PDFs y productos digitales en Meta Ad Library")

        if not ctx.markets:
            st.error(
                f"No se encontraron archivos YAML en `{ctx.settings.markets_dir}`. "
                "Crea al menos `markets/brasil.yaml`."
            )
            return

        market_codes = list(ctx.markets.keys())
        default_idx = market_codes.index("brasil") if "brasil" in market_codes else 0
        selected_code = st.selectbox(
            "País / Mercado principal",
            options=market_codes,
            index=default_idx,
            format_func=lambda code: f"{ctx.markets[code].name} ({ctx.markets[code].country} · {ctx.markets[code].language})",
        )
        active_market = ctx.markets[selected_code]

        page = st.radio(
            "Navegación",
            options=[
                "🎯 Cazador Rápido (Meta)",
                "🏆 Ranking de Ganadores",
                "🚀 Ofertas Escalando",
                "🔍 Detalle y Análisis IA",
                "📥 Mercado e Ingesta",
                "📈 Tendencias",
            ],
        )

        st.divider()
        is_pg = ctx.settings.db_url.startswith(("postgres://", "postgresql://", "postgresql+"))
        st.caption(f"Mercados activos: **{len(ctx.markets)} países**")
        st.caption(f"Base de datos: **{'🟢 Supabase (PostgreSQL)' if is_pg else '🟡 SQLite local/temp'}**")
        st.caption("Estado de módulos opcionales")
        st.write(f"- Gemini: {'✅ Configurado' if ctx.gemini.is_configured() else '⚪ Inactivo (sin clave)'}")
        st.write(f"- Perplexity: {'✅ Configurado' if ctx.perplexity.is_configured() else '⚪ Inactivo (sin clave)'}")
        st.write(f"- Cuota LLM hoy: `{ctx.limiter.used_today()} / {ctx.limiter.daily_limit}`")

    if page == "🎯 Cazador Rápido (Meta)":
        render_hunter_page(ctx, active_market)
    elif page == "🏆 Ranking de Ganadores":
        render_ranking_page(ctx, active_market)
    elif page == "🚀 Ofertas Escalando":
        render_offers_page(ctx, active_market)
    elif page == "🔍 Detalle y Análisis IA":
        render_detail_page(ctx, active_market)
    elif page == "📥 Mercado e Ingesta":
        render_market_page(ctx, active_market)
    elif page == "📈 Tendencias":
        render_trends_page(ctx, active_market)


if __name__ == "__main__":
    main()
