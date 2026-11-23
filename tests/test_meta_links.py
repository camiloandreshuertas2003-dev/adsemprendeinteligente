"""Pruebas unitarias para la generación de enlaces precisos de Meta Ad Library."""

from __future__ import annotations

from datetime import date

from adscout.services.meta_links import (
    build_ad_library_page_url,
    build_ad_library_search_url,
    extract_page_id,
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
