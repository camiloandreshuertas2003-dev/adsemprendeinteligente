"""Pruebas unitarias para la generación de enlaces precisos de Meta Ad Library."""

from __future__ import annotations

from datetime import date

from adscout.services.meta_links import (
    build_ad_library_page_url,
    build_ad_library_search_url,
    extract_page_id,
    extract_whatsapp_info,
)


def test_extract_page_id_from_raw_id_and_urls():
    assert extract_page_id("605901895933065") == "605901895933065"
    assert (
        extract_page_id(
            "https://www.facebook.com/ads/library/?active_status=active&ad_type=all"
            "&country=ALL&is_targeted_country=false&media_type=all&search_type=page"
            "&sort_data[mode]=total_impressions&sort_data[direction]=desc"
            "&source=page-transparency-widget&view_all_page_id=605901895933065"
        )
        == "605901895933065"
    )
    assert extract_page_id("pg_non_numeric") is None
    assert extract_page_id("") is None


def test_build_ad_library_page_url_matches_transparency_impressions_format():
    url = build_ad_library_page_url(page_id="605901895933065")
    expected = (
        "https://www.facebook.com/ads/library/?"
        "active_status=active&ad_type=all&country=ALL&is_targeted_country=false"
        "&media_type=all&search_type=page&sort_data[mode]=total_impressions"
        "&sort_data[direction]=desc&source=page-transparency-widget"
        "&view_all_page_id=605901895933065"
    )
    assert url == expected


def test_build_ad_library_search_url_exact_and_impressions():
    url_exact = build_ad_library_search_url(
        query="hotmart.com",
        country="BR",
        exact_phrase=True,
        sort_by_impressions=True,
        min_days_active=30,
        reference_date=date(2026, 11, 23),
    )
    assert "search_type=keyword_exact_phrase" in url_exact
    assert "sort_data[mode]=total_impressions" in url_exact
    assert "sort_data[direction]=desc" in url_exact
    assert "is_targeted_country=false" in url_exact
    assert "start_date[max]=2026-10-24" in url_exact

    # Combos con `|` usan keyword_unordered automáticamente aunque exact_phrase=True
    url_combo = build_ad_library_search_url(
        query="pdf | api.whatsapp.com",
        country="CO",
        exact_phrase=True,
        sort_by_impressions=True,
    )
    assert "search_type=keyword_unordered" in url_combo
    assert "sort_data[mode]=total_impressions" in url_combo


def test_extract_whatsapp_info_from_links_copy_and_native():
    res_api = extract_whatsapp_info(
        link_url="https://api.whatsapp.com/send?phone=5511998877665&text=Hola%20quiero%20el%20PDF"
    )
    assert res_api["phone"] == "+5511998877665"
    assert res_api["wa_url"] == "https://wa.me/5511998877665"
    assert res_api["prefilled_text"] == "Hola quiero el PDF"

    res_wame = extract_whatsapp_info(link_url="https://wa.me/573001234567")
    assert res_wame["phone"] == "+573001234567"

    res_copy = extract_whatsapp_info(ad_text="Escríbenos al +57 300 987 6543 para recibir el PDF")
    assert res_copy["phone"] == "+573009876543"
    assert res_copy["source"] == "copy"

    res_native = extract_whatsapp_info(cta="Enviar mensaje de WhatsApp")
    assert res_native["phone"] is None
    assert res_native["source"] == "native_hidden"
