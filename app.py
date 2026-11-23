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
        page_title="AdScout — Investigación de Competidores",
        page_icon="🕵️",
        layout="wide",
    )

    ctx = build_app_context()

    with st.sidebar:
        st.title("🕵️ AdScout")
        st.caption("Pega un perfil ganador de Meta Ad Library y haz su ingeniería inversa con IA")

        if not ctx.markets:
            st.error(
                f"No se encontraron archivos YAML en `{ctx.settings.markets_dir}`. "
                "Crea al menos `markets/brasil.yaml`."
            )
            return

        market_codes = list(ctx.markets.keys())
        default_idx = market_codes.index("brasil") if "brasil" in market_codes else 0
        selected_code = st.selectbox(
            "Mercado de referencia",
            options=market_codes,
            index=default_idx,
            format_func=lambda code: f"{ctx.markets[code].name} ({ctx.markets[code].country})",
        )
        active_market = ctx.markets[selected_code]

        page = st.radio(
            "Navegación",
            options=[
                "1. 🕵️ Investigar Perfil Ganador",
                "2. 🏆 Comparar Todos los Perfiles",
                "3. 📥 Importar / Herramientas",
            ],
        )

        st.divider()
        with st.expander("⚙️ Estado del sistema", expanded=False):
            is_pg = ctx.db_backend == "postgresql"
            apify_ok = bool(ctx.settings.apify_api_token or st.session_state.get("session_apify_token"))
            st.caption(f"Apify (Lector de perfiles): **{'✅ Conectado' if apify_ok else '⚪ Sin clave'}**")
            st.caption(f"Base de datos: **{'🟢 Supabase (PostgreSQL)' if is_pg else '🟡 SQLite local/temp'}**")
            st.caption(f"Gemini IA: {'✅ Activo' if ctx.gemini.is_configured() else '⚪ Sin clave'}")
            st.caption(f"Perplexity IA: {'✅ Activo' if ctx.perplexity.is_configured() else '⚪ Sin clave'}")
            st.caption(f"Cuota IA hoy: `{ctx.limiter.used_today()} / {ctx.limiter.daily_limit}`")

    if page == "1. 🕵️ Investigar Perfil Ganador":
        render_hunter_page(ctx, active_market)
    elif page == "2. 🏆 Comparar Todos los Perfiles":
        render_winners_hub_page(ctx, active_market)
    elif page == "3. 📥 Importar / Herramientas":
        tab_ai_copy, tab_import, tab_trends = st.tabs(
            ["✨ Tropicalizador Rápido", "📥 Importar CSV/JSON", "📈 Tendencias"]
        )
        with tab_ai_copy:
            render_detail_page(ctx, active_market)
        with tab_import:
            render_market_page(ctx, active_market)
        with tab_trends:
            render_trends_page(ctx, active_market)


if __name__ == "__main__":
    main()
