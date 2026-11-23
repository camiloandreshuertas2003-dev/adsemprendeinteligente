"""AdScout — Punto de entrada de la aplicación Streamlit."""

from __future__ import annotations

import streamlit as st

from adscout.ui.context import build_app_context
from adscout.ui.page_detail import render_detail_page
from adscout.ui.page_hunter import render_hunter_page
from adscout.ui.page_market import render_market_page
from adscout.ui.page_offers import render_winners_hub_page
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
        st.caption("Encuentra y espía productos digitales ganadores en Meta Ad Library")

        if not ctx.markets:
            st.error(
                f"No se encontraron archivos YAML en `{ctx.settings.markets_dir}`. "
                "Crea al menos `markets/brasil.yaml`."
            )
            return

        market_codes = list(ctx.markets.keys())
        default_idx = market_codes.index("brasil") if "brasil" in market_codes else 0
        selected_code = st.selectbox(
            "País principal",
            options=market_codes,
            index=default_idx,
            format_func=lambda code: f"{ctx.markets[code].name} ({ctx.markets[code].country})",
        )
        active_market = ctx.markets[selected_code]

        page = st.radio(
            "¿Qué quieres hacer?",
            options=[
                "1. 🔎 Buscar y Espiar",
                "2. 🏆 Ganadores y Favoritos",
                "3. ✨ Analizar con IA",
                "4. 📥 Importar y Tendencias",
            ],
        )

        st.divider()
        with st.expander("⚙️ Estado del sistema", expanded=False):
            is_pg = ctx.db_backend == "postgresql"
            apify_ok = bool(ctx.settings.apify_api_token or st.session_state.get("session_apify_token"))
            st.caption(f"Apify (Búsqueda auto): **{'✅ Conectado' if apify_ok else '⚪ Sin clave'}**")
            st.caption(f"Mercados activos: **{len(ctx.markets)} países**")
            st.caption(f"Base de datos: **{'🟢 Supabase (PostgreSQL)' if is_pg else '🟡 SQLite local/temp'}**")
            st.caption(f"Gemini: {'✅ Activo' if ctx.gemini.is_configured() else '⚪ Sin clave'}")
            st.caption(f"Perplexity: {'✅ Activo' if ctx.perplexity.is_configured() else '⚪ Sin clave'}")
            st.caption(f"Cuota IA hoy: `{ctx.limiter.used_today()} / {ctx.limiter.daily_limit}`")

    if page == "1. 🔎 Buscar y Espiar":
        render_hunter_page(ctx, active_market)
    elif page == "2. 🏆 Ganadores y Favoritos":
        render_winners_hub_page(ctx, active_market)
    elif page == "3. ✨ Analizar con IA":
        render_detail_page(ctx, active_market)
    elif page == "4. 📥 Importar y Tendencias":
        tab_import, tab_trends = st.tabs(["📥 Importar Anuncios", "📈 Tendencias de Nichos"])
        with tab_import:
            render_market_page(ctx, active_market)
        with tab_trends:
            render_trends_page(ctx, active_market)


if __name__ == "__main__":
    main()
