"""Página principal: Investigar Perfil Ganador (Radiografía + Ingeniería Inversa IA + Perfiles Guardados)."""

from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st

from adscout.llm import LLMConfigError, LLMDailyLimitExceededError, LLMError
from adscout.models.ad import Ad
from adscout.models.market import MarketConfig
from adscout.services.meta_links import (
    build_ad_library_ad_url,
    build_ad_library_page_url,
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

MOLDABILITY_STATUSES = ["✅ Moldeable", "⚠️ Difícil", "❌ No moldeable"]
FAVORITE_STATUSES = ["✅ Moldeable", "⚠️ Difícil", "❌ No moldeable", "Para modelar", "Modelado", "Descartado"]


def _get_active_apify_token(ctx: AppContext) -> str | None:
    """Devuelve el token de Apify desde Secrets/.env o desde la sesión actual."""
    if ctx.settings.apify_api_token:
        return ctx.settings.apify_api_token
    session_token = str(st.session_state.get("session_apify_token", "")).strip()
    return session_token or None


def _list_analyzed_real_pages(ctx: AppContext) -> list[dict]:
    """Devuelve lista de perfiles reales (page_id numérico) que ya tienen anuncios en la BD."""
    all_ads = ctx.repository.list_ads(country=None, only_active=False)
    by_page: dict[str, dict] = {}
    for ad in all_ads:
        if not is_real_meta_id(ad.page_id):
            continue
        entry = by_page.setdefault(
            ad.page_id,
            {
                "page_id": ad.page_id,
                "page_name": ad.page_name,
                "country": ad.country,
                "total_ads": 0,
                "active_ads": 0,
            },
        )
        entry["total_ads"] += 1
        if ad.is_active:
            entry["active_ads"] += 1
    return sorted(by_page.values(), key=lambda x: (x["active_ads"], x["total_ads"]), reverse=True)


def render_hunter_page(ctx: AppContext, active_market: MarketConfig) -> None:
    st.header("🕵️ Investigar Perfil Ganador")
    st.caption(
        "Encuentra un anunciante ganador en Meta Ad Library, pega aquí su enlace o ID, "
        "y AdScout lee todos sus anuncios para hacerte la investigación de mercado completa."
    )

    apify_token = _get_active_apify_token(ctx)
    if not apify_token:
        with st.container(border=True):
            st.warning(
                "🔑 **Conecta tu clave de Apify** para leer los anuncios del perfil automáticamente "
                "(si ya la guardaste en Streamlit Cloud → Settings → Secrets como `APIFY_API_TOKEN`, recarga la página)."
            )
            tk1, tk2 = st.columns([3, 1.2])
            with tk1:
                pasted_token = st.text_input(
                    "Pega tu APIFY_API_TOKEN aquí",
                    type="password",
                    placeholder="apify_api_...",
                    key="apify_token_input_box",
                )
            with tk2:
                st.write("")
                st.write("")
                if st.button("Conectar ahora", type="primary", use_container_width=True):
                    if pasted_token.strip():
                        st.session_state["session_apify_token"] = pasted_token.strip()
                        st.rerun()
                    else:
                        st.error("Pega tu clave de Apify primero.")

    # Caja principal: pegar perfil ganador
    with st.container(border=True):
        st.markdown("**1️⃣ Pega el enlace o ID del perfil ganador de Meta Ad Library**")
        raw_input = st.text_input(
            "Enlace de Meta Ad Library o Page ID",
            value=st.session_state.get("competitor_input_value", ""),
            placeholder="Ej: https://www.facebook.com/ads/library/?...view_all_page_id=605901895933065  o  605901895933065",
            label_visibility="collapsed",
            key="competitor_raw_input",
        )

        opt1, opt2, opt3 = st.columns([1.2, 1.2, 1.6])
        with opt1:
            spy_status = st.selectbox(
                "Estado de anuncios",
                options=["active", "all"],
                index=0,
                format_func=lambda s: "Solo activos" if s == "active" else "Todos (activos e inactivos)",
                key="competitor_status",
            )
        with opt2:
            spy_limit = st.number_input(
                "Máx. anuncios a leer",
                min_value=10,
                max_value=100,
                value=40,
                step=10,
                key="competitor_limit",
            )
        with opt3:
            st.write("")
            st.write("")
            st.caption("Ordenados por **mayores impresiones** (`country=ALL`)")

        extracted_id = extract_page_id(raw_input)
        page_url = (
            build_ad_library_page_url(
                page_id=extracted_id,
                country="ALL",
                active_status=spy_status,
                sort_by_impressions=True,
            )
            if extracted_id
            else None
        )

        if raw_input.strip() and not extracted_id:
            st.warning(
                "No detecté un ID de página válido. Copia la URL desde Meta Ad Library "
                "(debe incluir `view_all_page_id=...`) o pega el número de ID directamente (ej. `605901895933065`)."
            )

        btn1, btn2 = st.columns([1.8, 1.2])
        with btn1:
            analyze_clicked = st.button(
                "🕵️ Analizar Perfil Ganador (Leer todos sus anuncios)",
                type="primary",
                use_container_width=True,
                disabled=not bool(extracted_id and apify_token),
                key="competitor_analyze_btn",
            )
        with btn2:
            if page_url:
                st.link_button(
                    "🔗 Abrir perfil en Meta Ad Library ↗",
                    page_url,
                    use_container_width=True,
                )
            else:
                st.link_button(
                    "🔎 Abrir Meta Ad Library para buscar ↗",
                    "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=ALL&is_targeted_country=false&media_type=all",
                    use_container_width=True,
                )

        if analyze_clicked and extracted_id and page_url and apify_token:
            try:
                source = ApifySource(
                    api_token=apify_token,
                    actor_id=ctx.settings.apify_actor_id,
                    timeout_seconds=max(ctx.settings.apify_timeout_seconds, 180.0),
                    custom_urls=[page_url],
                )
                with st.spinner(
                    f"Leyendo hasta {int(spy_limit)} anuncios reales del perfil `{extracted_id}` con Apify... "
                    "(suele tardar 20–50 segundos)"
                ):
                    ctx.repository.delete_demo_ads()
                    stats = ctx.pipeline.run(
                        source=source,
                        market=active_market,
                        keywords=[extracted_id],
                        limit=int(spy_limit),
                    )
                st.session_state["active_competitor_page_id"] = extracted_id
                if stats["total_fetched"] == 0:
                    st.warning(
                        f"Apify no encontró anuncios activos para el ID `{extracted_id}`. "
                        "Verifica que la página tenga anuncios activos en Meta Ad Library."
                    )
                else:
                    st.success(
                        f"¡Perfil analizado! Se leyeron **{stats['total_fetched']} anuncios reales** "
                        f"({stats['inserted']} nuevos, {stats['updated']} actualizados)."
                    )
            except InvalidTokenError as exc:
                st.error(f"Clave de Apify inválida: {exc}")
            except RateLimitError as exc:
                st.warning(f"Límite de Apify alcanzado: {exc}")
            except (SourceConfigError, SourceError) as exc:
                st.error(f"Error leyendo el perfil con Apify: {exc}")

    # Selector rápido de perfiles ya analizados
    analyzed_pages = _list_analyzed_real_pages(ctx)
    active_page_id = st.session_state.get("active_competitor_page_id")
    if not active_page_id and extracted_id:
        active_page_id = extracted_id
    if not active_page_id and analyzed_pages:
        active_page_id = analyzed_pages[0]["page_id"]

    if analyzed_pages:
        page_ids = [p["page_id"] for p in analyzed_pages]
        page_labels = {
            p["page_id"]: f"{p['page_name']} (ID: {p['page_id']} · {p['active_ads']} activos / {p['total_ads']} total)"
            for p in analyzed_pages
        }
        default_sel = page_ids.index(active_page_id) if active_page_id in page_ids else 0
        selected_pid = st.selectbox(
            "Perfil analizado en pantalla",
            options=page_ids,
            index=default_sel,
            format_func=lambda pid: page_labels[pid],
            key="competitor_selector",
        )
        active_page_id = selected_pid
        st.session_state["active_competitor_page_id"] = active_page_id

    page_ads = ctx.repository.list_ads_by_page(active_page_id) if active_page_id else []

    tab_xray, tab_ai, tab_saved = st.tabs(
        [
            "📊 Radiografía y Anuncios",
            "🧠 Ingeniería Inversa (IA)",
            "⭐ Mis Perfiles Guardados",
        ]
    )

    with tab_xray:
        _render_xray_tab(ctx, active_page_id, page_ads)

    with tab_ai:
        _render_reverse_engineering_tab(ctx, active_market, active_page_id, page_ads)

    with tab_saved:
        _render_saved_profiles_tab(ctx)


def _render_xray_tab(ctx: AppContext, page_id: str | None, page_ads: list[Ad]) -> None:
    if not page_id or not page_ads:
        st.info(
            "Pega arriba el enlace o ID de un perfil ganador de Meta Ad Library y pulsa "
            "**🕵️ Analizar Perfil Ganador** para ver su radiografía completa aquí."
        )
        return

    page_name = page_ads[0].page_name
    direct_page_url = build_ad_library_page_url(page_id=page_id, page_name=page_name, country="ALL")

    active_ads = [a for a in page_ads if a.is_active]
    total_variants = sum(max(1, a.variants_count) for a in page_ads)
    max_days = max(a.days_active() for a in page_ads)
    unique_domains = sorted({a.link_domain for a in page_ads if a.link_domain})

    h1, h2 = st.columns([2.2, 1.2])
    with h1:
        st.subheader(f"📊 {page_name}")
        st.caption(f"Page ID: `{page_id}` · Total leídos: **{len(page_ads)} anuncios**")
    with h2:
        st.link_button("🕵️ Ver todos en Meta Ad Library ↗", direct_page_url, use_container_width=True)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Anuncios activos", len(active_ads))
    k2.metric("Máx. días activo", f"{max_days} días")
    k3.metric("Variantes totales", total_variants)
    k4.metric("Dominios destino", len(unique_domains))

    # Mapa de embudo / checkouts reales
    url_counter = Counter(a.link_url for a in page_ads if a.link_url)
    top_checkout = url_counter.most_common(1)[0][0] if url_counter else None

    # Evaluación manual rápida en 1 clic: ¿El video es moldeable / replicable?
    saved_list = ctx.repository.list_saved_offers()
    existing_saved = next((s for s in saved_list if s["page_id"] == page_id), None)
    current_verdict = existing_saved["status"] if existing_saved else None
    current_notes = existing_saved["notes"] if existing_saved else ""

    with st.container(border=True):
        st.markdown("### 🎬 ¿El video de este perfil es moldeable?")
        st.caption(
            "¿Puedes replicar el video o crear uno nuevo fácilmente para recrear el anuncio? "
            "Marca tu decisión en 1 clic y quedará guardada en **⭐ Mis Perfiles Guardados**."
        )
        if current_verdict:
            st.info(f"Tu veredicto actual: **{current_verdict}**" + (f" — _{current_notes}_" if current_notes else ""))

        mold_note = st.text_input(
            "Nota sobre cómo replicar el video (opcional)",
            value=current_notes,
            placeholder="Ej: Fácil de replicar con voz en off + grabando el PDF en pantalla en CapCut",
            key=f"mold_note_{page_id}",
        )

        m_col1, m_col2, m_col3 = st.columns(3)
        with m_col1:
            if st.button("✅ Sí, es moldeable", type="primary", use_container_width=True, key=f"mold_yes_{page_id}"):
                ctx.repository.upsert_saved_offer(
                    page_id=page_id,
                    country=page_ads[0].country or "ALL",
                    page_name=page_name,
                    status="✅ Moldeable",
                    notes=mold_note.strip(),
                    fb_page_url=direct_page_url,
                    checkout_url=top_checkout,
                )
                st.success(f"**{page_name}** marcado como **✅ Moldeable**.")
                st.rerun()
        with m_col2:
            if st.button("⚠️ Difícil / Requiere ajustes", use_container_width=True, key=f"mold_mid_{page_id}"):
                ctx.repository.upsert_saved_offer(
                    page_id=page_id,
                    country=page_ads[0].country or "ALL",
                    page_name=page_name,
                    status="⚠️ Difícil",
                    notes=mold_note.strip(),
                    fb_page_url=direct_page_url,
                    checkout_url=top_checkout,
                )
                st.warning(f"**{page_name}** marcado como **⚠️ Difícil**.")
                st.rerun()
        with m_col3:
            if st.button("❌ No moldeable", use_container_width=True, key=f"mold_no_{page_id}"):
                ctx.repository.upsert_saved_offer(
                    page_id=page_id,
                    country=page_ads[0].country or "ALL",
                    page_name=page_name,
                    status="❌ No moldeable",
                    notes=mold_note.strip(),
                    fb_page_url=direct_page_url,
                    checkout_url=top_checkout,
                )
                st.error(f"**{page_name}** marcado como **❌ No moldeable**.")
                st.rerun()

    if url_counter:
        st.markdown("### 🔗 Embudo y Destinos (a dónde manda el tráfico)")
        funnel_rows = [
            {
                "Anuncios apuntando": count,
                "Dominio": next((a.link_domain for a in page_ads if a.link_url == url), "-"),
                "URL de Ventas / Checkout": url,
            }
            for url, count in url_counter.most_common(10)
        ]
        st.dataframe(
            pd.DataFrame(funnel_rows),
            width="stretch",
            hide_index=True,
            column_config={
                "URL de Ventas / Checkout": st.column_config.LinkColumn(
                    "Página de Ventas / Checkout",
                    display_text="Abrir página de ventas ↗",
                ),
            },
        )

    # Tabla de anuncios ordenados por antigüedad y variantes (los más rentables arriba)
    st.markdown("### 🏆 Anuncios del Perfil (ordenados por días activo y variantes)")
    sorted_ads = sorted(
        page_ads,
        key=lambda a: (a.is_active, a.days_active(), a.variants_count),
        reverse=True,
    )
    ad_rows = []
    for ad in sorted_ads:
        ad_rows.append(
            {
                "Estado": "🟢 Activo" if ad.is_active else "⚪ Inactivo",
                "Días activo": ad.days_active(),
                "Variantes": ad.variants_count,
                "Titular": ad.headline or "(sin titular)",
                "Copy (extracto)": (ad.ad_text or "").replace("\n", " ")[:140] or "-",
                "Dominio": ad.link_domain or "-",
                "Ver Anuncio (FB)": build_ad_library_ad_url(
                    ad_id=ad.ad_id,
                    country=ad.country,
                    snapshot_url=ad.snapshot_url,
                    fallback_query=ad.headline or ad.page_name,
                ),
                "Web / Checkout": ad.link_url,
            }
        )

    df_ads = pd.DataFrame(ad_rows)
    st.dataframe(
        df_ads,
        width="stretch",
        hide_index=True,
        column_config={
            "Ver Anuncio (FB)": st.column_config.LinkColumn("Anuncio FB", display_text="Ver anuncio ↗"),
            "Web / Checkout": st.column_config.LinkColumn("Checkout / Web", display_text="Abrir web ↗"),
        },
    )

    csv_bytes = df_ads.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ Exportar anuncios de este perfil a CSV",
        data=csv_bytes,
        file_name=f"adscout_perfil_{page_id}.csv",
        mime="text/csv",
    )

    # Guardar perfil en Mis Perfiles Guardados
    st.divider()
    st.markdown("### ⭐ Guardar este perfil en Mis Competidores")
    s1, s2, s3 = st.columns([1.2, 2.3, 1.1])
    with s1:
        fav_status = st.selectbox("Estado", options=FAVORITE_STATUSES, index=0, key=f"xray_status_{page_id}")
    with s2:
        fav_notes = st.text_input(
            "Notas (ej: Vende ebook de recetas en Hotmart, 18 anuncios activos)",
            value="",
            key=f"xray_notes_{page_id}",
        )
    with s3:
        st.write("")
        st.write("")
        top_checkout = url_counter.most_common(1)[0][0] if url_counter else None
        if st.button("Guardar ⭐", type="primary", use_container_width=True, key=f"xray_save_{page_id}"):
            ctx.repository.upsert_saved_offer(
                page_id=page_id,
                country=page_ads[0].country or "ALL",
                page_name=page_name,
                status=fav_status,
                notes=fav_notes.strip(),
                fb_page_url=direct_page_url,
                checkout_url=top_checkout,
            )
            st.success(f"Perfil **{page_name}** guardado en **⭐ Mis Perfiles Guardados**.")


def _render_reverse_engineering_tab(
    ctx: AppContext,
    active_market: MarketConfig,
    page_id: str | None,
    page_ads: list[Ad],
) -> None:
    if not page_id or not page_ads:
        st.info(
            "Primero analiza un perfil ganador arriba para que la IA pueda leer todos sus anuncios "
            "y hacer la ingeniería inversa completa."
        )
        return

    page_name = page_ads[0].page_name
    st.subheader(f"🧠 Ingeniería Inversa de {page_name}")
    st.caption(
        f"Gemini lee los mejores **{min(len(page_ads), 15)} anuncios** de esta página a la vez para extraer "
        "su oferta, dolores, ángulos ganadores, debilidades y armarte una versión mejorada lista para lanzar."
    )

    target_countries = st.text_input(
        "¿Para qué países en español quieres adaptar esta oferta?",
        value="Colombia, México, Chile, Perú y Argentina",
        key=f"re_target_{page_id}",
    )

    report_key = f"re_report_{page_id}"
    if st.button(
        "🧠 Generar Investigación de Mercado + Plan de Oferta con Gemini",
        type="primary",
        use_container_width=True,
        key=f"re_run_btn_{page_id}",
    ):
        try:
            with st.spinner(f"Analizando los anuncios de {page_name} con Gemini..."):
                report = ctx.gemini.reverse_engineer_competitor_page(
                    page_name=page_name,
                    page_id=page_id,
                    ads=page_ads,
                    target_countries=target_countries,
                    limiter=ctx.limiter,
                )
            st.session_state[report_key] = report
            st.success("¡Investigación de mercado generada!")
        except (LLMConfigError, LLMDailyLimitExceededError, LLMError) as exc:
            st.error(str(exc))

    report = st.session_state.get(report_key)
    if report:
        with st.container(border=True):
            st.markdown(f"### 🎬 Video Moldeable (Evaluación IA): **{report.get('video_moldeable', 'N/D')}**")
            if report.get("razon_moldeabilidad"):
                st.write(report["razon_moldeabilidad"])
            if report.get("como_replicar_video"):
                st.markdown("**Cómo replicar este video fácilmente paso a paso:**")
                for paso in report.get("como_replicar_video", []):
                    st.write(f"- {paso}")

        with st.container(border=True):
            st.markdown(f"### 🎯 Nicho detectado: `{report.get('nicho', 'N/D')}`")
            st.write(f"**📦 Qué vende:** {report.get('que_vende', '')}")
            st.write(f"**💡 Promesa principal:** {report.get('promesa_principal', '')}")
            st.write(f"**👤 Público objetivo:** {report.get('publico_objetivo', '')}")

        col_a, col_b = st.columns(2)
        with col_a:
            with st.container(border=True):
                st.markdown("#### 🔥 Ángulos ganadores que repite")
                for item in report.get("angulos_ganadores", []):
                    st.write(f"- {item}")
                st.markdown("#### 🪝 Mejores Hooks (adaptados al español)")
                for item in report.get("mejores_hooks_es", []):
                    st.write(f"- {item}")
        with col_b:
            with st.container(border=True):
                st.markdown("#### ⚡ Debilidades y oportunidades para superarlo")
                for item in report.get("debilidades_oportunidades", []):
                    st.write(f"- {item}")

        with st.container(border=True):
            st.markdown("### 🚀 Tu Oferta Mejorada (lista para lanzar)")
            st.success(f"**Título sugerido:** {report.get('titulo_sugerido_es', 'N/D')}")
            st.write(f"**Precio sugerido:** `{report.get('precio_sugerido_usd', 'N/D')}`")

            p1, p2 = st.columns(2)
            with p1:
                st.markdown("**📘 Estructura sugerida del PDF / Ebook:**")
                for cap in report.get("estructura_pdf", []):
                    st.write(f"- {cap}")
            with p2:
                st.markdown("**🎁 Bonos irresistibles sugeridos:**")
                for bono in report.get("bonos_sugeridos", []):
                    st.write(f"- {bono}")

            st.markdown("**📣 3 Copies listos para probar en Meta Ads:**")
            for idx, copy_text in enumerate(report.get("copies_listos_es", []), start=1):
                st.info(f"**Anuncio {idx}:** {copy_text}")

    # Validación externa de demanda y saturación con Perplexity
    st.divider()
    st.subheader("🌍 Validar Demanda y Saturación del Nicho (Perplexity)")
    default_niche = report.get("nicho", "") if isinstance(report, dict) else ""
    niche_input = st.text_input(
        "Nicho a validar fuera de Facebook",
        value=default_niche or page_name,
        key=f"re_pplx_niche_{page_id}",
    )
    if st.button("🌍 Validar saturación y competencia con Perplexity", key=f"re_pplx_btn_{page_id}"):
        try:
            with st.spinner("Consultando tendencia, saturación y competidores en Perplexity..."):
                val = ctx.perplexity.validate_niche(
                    nicho=niche_input,
                    market=active_market,
                    repository=ctx.repository,
                    limiter=ctx.limiter,
                )
            st.success(f"Validación completada para **{val.nicho}**")
            st.write(f"**Tendencia:** {val.tendencia}")
            st.write(f"**Saturación:** {val.saturacion}")
            if val.competidores:
                st.write("**Competidores / Referentes:** " + ", ".join(val.competidores))
            st.write(f"**Resumen ejecutivo:** {val.resumen_ejecutivo}")
            if val.sources:
                st.markdown("**Fuentes citadas:**")
                for src in val.sources:
                    st.markdown(f"- [{src}]({src})")
        except (LLMConfigError, LLMDailyLimitExceededError, LLMError) as exc:
            st.error(str(exc))


def _render_saved_profiles_tab(ctx: AppContext) -> None:
    st.subheader("⭐ Mis Perfiles Ganadores Guardados")
    filter_status = st.radio(
        "Filtrar por moldeabilidad / estado",
        options=["Todos", "✅ Moldeable", "⚠️ Difícil", "❌ No moldeable"],
        horizontal=True,
        key="saved_profiles_filter_status",
    )
    saved = ctx.repository.list_saved_offers(
        status=None if filter_status == "Todos" else filter_status
    )
    if not saved:
        st.info(
            "No hay perfiles en esta categoría todavía. Analiza un perfil y marca si su video es "
            "**✅ Moldeable**, **⚠️ Difícil** o **❌ No moldeable** en **📊 Radiografía y Anuncios**."
        )
        return

    for s in saved:
        direct_url = build_ad_library_page_url(
            page_id=s["page_id"],
            page_name=s["page_name"],
            country="ALL",
            sort_by_impressions=True,
        )
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2.2, 2.2, 1.3, 1.3])
            with c1:
                st.markdown(f"**{s['page_name']}**")
                st.caption(f"ID: `{s['page_id']}` · Estado: **{s['status']}**")
            with c2:
                st.write(s["notes"] or "Sin notas")
                if s["checkout_url"]:
                    st.markdown(f"[Abrir checkout/web ↗]({s['checkout_url']})")
            with c3:
                if st.button("📊 Ver perfil", key=f"load_saved_{s['page_id']}_{s['country']}", use_container_width=True):
                    st.session_state["active_competitor_page_id"] = s["page_id"]
                    st.session_state["competitor_input_value"] = s["page_id"]
                    st.rerun()
            with c4:
                st.link_button("🕵️ Abrir en FB ↗", direct_url, use_container_width=True)

    st.divider()
    del_options = {f"{s['page_name']} ({s['page_id']}) — {s['status']}": s for s in saved}
    chosen_del = st.selectbox("Eliminar perfil guardado", options=list(del_options.keys()))
    target = del_options[chosen_del]
    if st.button("🗑️ Eliminar de guardados"):
        ctx.repository.delete_saved_offer(page_id=target["page_id"], country=target["country"])
        st.success(f"Eliminado **{target['page_name']}**.")
        st.rerun()
