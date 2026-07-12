"""
Tests for pure utility functions (no mocking required).
"""

import pytest
from datetime import datetime, timedelta, timezone
from cclimits import format_reset_time, get_status_icon


class TestFormatResetTime:
    """Tests for format_reset_time() function."""

    def test_future_hours_and_minutes(self):
        """Test formatting future time with hours and minutes."""
        # Use UTC time to ensure consistency
        future_time = (datetime.now(timezone.utc) + timedelta(hours=2, minutes=30)).isoformat().replace("+00:00", "Z")
        result = format_reset_time(future_time)
        # Result should be "2h 30m" (or very close)
        assert "2h" in result or "1h" in result  # May be slightly off due to execution time

    def test_future_minutes_only(self):
        """Test formatting future time with minutes only."""
        future_time = (datetime.now(timezone.utc) + timedelta(minutes=45)).isoformat().replace("+00:00", "Z")
        result = format_reset_time(future_time)
        # Should show minutes
        assert "m" in result

    def test_past_time(self):
        """Test formatting past time returns 'Now'."""
        past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        result = format_reset_time(past_time)
        assert result == "Now"

    def test_none_input(self):
        """Test None input returns 'N/A'."""
        result = format_reset_time(None)
        assert result == "N/A"

    def test_empty_string(self):
        """Test empty string returns 'N/A'."""
        result = format_reset_time("")
        assert result == "N/A"

    def test_invalid_timestamp(self):
        """Test invalid timestamp returns truncated string or N/A."""
        result = format_reset_time("not-a-valid-timestamp")
        # Should return first 19 chars or "N/A"
        assert result == "not-a-valid-timesta" or result == "N/A"

    def test_iso_format_with_timezone(self):
        """Test ISO format with timezone offset."""
        future_time = (datetime.now(timezone.utc) + timedelta(hours=1, minutes=15)).isoformat().replace("+00:00", "Z")
        result = format_reset_time(future_time)
        # Should show time (may be slightly off due to execution)
        assert "m" in result or "h" in result or result == "Now"

    def test_milliseconds_precision(self):
        """Test timestamp with milliseconds."""
        future_time = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
        result = format_reset_time(future_time)
        # Should show minutes
        assert "m" in result or result == "Now"


class TestGetStatusIcon:
    """Tests for get_status_icon() function."""

    def test_100_percent_usage(self):
        """Test exactly 100% usage returns cross emoji."""
        result = get_status_icon(100.0)
        assert result == "❌"

    def test_above_100_percent_usage(self):
        """Test above 100% usage returns cross emoji."""
        result = get_status_icon(105.5)
        assert result == "❌"

    def test_90_percent_usage(self):
        """Test 90% usage returns red circle."""
        result = get_status_icon(90.0)
        assert result == "🔴"

    def test_95_percent_usage(self):
        """Test 95% usage returns red circle."""
        result = get_status_icon(95.0)
        assert result == "🔴"

    def test_70_percent_usage(self):
        """Test 70% usage returns warning."""
        result = get_status_icon(70.0)
        assert result == "⚠️"

    def test_85_percent_usage(self):
        """Test 85% usage returns warning."""
        result = get_status_icon(85.0)
        assert result == "⚠️"

    def test_zero_percent_usage(self):
        """Test 0% usage returns checkmark."""
        result = get_status_icon(0.0)
        assert result == "✅"

    def test_low_percent_usage(self):
        """Test low percentage usage returns checkmark."""
        result = get_status_icon(25.5)
        assert result == "✅"

    def test_50_percent_usage(self):
        """Test 50% usage returns checkmark."""
        result = get_status_icon(50.0)
        assert result == "✅"

    def test_69_percent_usage(self):
        """Test 69% usage (just below warning threshold)."""
        result = get_status_icon(69.9)
        assert result == "✅"

    def test_floating_point_precision(self):
        """Test with floating point numbers."""
        result = get_status_icon(89.999)
        assert result == "⚠️"

    def test_negative_usage(self):
        """Test negative percentage (edge case)."""
        result = get_status_icon(-10.0)
        assert result == "✅"


class TestMergeCacheData:
    """Tests for merge_cache_data() cache-preservation logic."""

    def test_no_creds_error_keeps_previous_good_entry(self):
        from cclimits import merge_cache_data
        old = {"zai": {"status": "ok", "token_quota": {"percentage": 1}}}
        new = {"zai": {"error": "No credentials found"}}
        merged = merge_cache_data(old, new)
        assert merged["zai"]["status"] == "ok"

    def test_real_error_overwrites_previous_entry(self):
        from cclimits import merge_cache_data
        old = {"zai": {"status": "ok"}}
        new = {"zai": {"error": "Invalid API key", "hint": "Check key"}}
        merged = merge_cache_data(old, new)
        assert merged["zai"]["error"] == "Invalid API key"

    def test_transient_error_preserves_previous_good_entry(self):
        from cclimits import merge_cache_data
        old = {"zai": {"status": "ok", "token_quota": {"percentage": 1}}}
        new = {"zai": {"error": "API error (500)"}}
        merged = merge_cache_data(old, new)
        assert merged["zai"]["status"] == "ok"
        assert merged["zai"]["token_quota"]["percentage"] == 1

    def test_transient_error_overwrites_previous_error_entry(self):
        from cclimits import merge_cache_data
        old = {"zai": {"error": "API error (503)"}}
        new = {"zai": {"error": "API error (500)"}}
        merged = merge_cache_data(old, new)
        assert merged["zai"]["error"] == "API error (500)"

    def test_fresh_data_overwrites_old(self):
        from cclimits import merge_cache_data
        old = {"claude": {"status": "ok", "five_hour": {"used": "10%"}}}
        new = {"claude": {"status": "ok", "five_hour": {"used": "20%"}}}
        merged = merge_cache_data(old, new)
        assert merged["claude"]["five_hour"]["used"] == "20%"

    def test_partial_run_preserves_other_providers(self):
        from cclimits import merge_cache_data
        old = {"claude": {"status": "ok"}, "codex": {"status": "ok"}}
        new = {"zai": {"status": "ok"}}
        merged = merge_cache_data(old, new)
        assert set(merged) == {"claude", "codex", "zai"}

    def test_no_creds_over_no_creds_keeps_error(self):
        from cclimits import merge_cache_data
        old = {"zai": {"error": "No credentials found"}}
        new = {"zai": {"error": "No credentials found"}}
        merged = merge_cache_data(old, new)
        assert merged["zai"]["error"] == "No credentials found"

    def test_empty_or_invalid_old_cache(self):
        from cclimits import merge_cache_data
        assert merge_cache_data({}, {"zai": {"status": "ok"}}) == {"zai": {"status": "ok"}}
        assert merge_cache_data(None, {"zai": {"status": "ok"}}) == {"zai": {"status": "ok"}}


class TestFormatCacheAge:
    """Tests for format_cache_age()."""

    def test_seconds(self):
        from cclimits import format_cache_age
        assert format_cache_age(42) == "42s"

    def test_minutes(self):
        from cclimits import format_cache_age
        assert format_cache_age(185) == "3m"

    def test_hours(self):
        from cclimits import format_cache_age
        assert format_cache_age(7300) == "2h"


class TestReadCacheReturnsAge:
    """read_cache() returns (data, age_seconds) for fresh caches."""

    def test_fresh_cache_roundtrip(self):
        from cclimits import read_cache, write_cache
        assert write_cache({"zai": {"status": "ok"}})
        cached = read_cache(60)
        assert cached is not None
        data, age = cached
        assert data["zai"]["status"] == "ok"
        assert isinstance(age, int) and 0 <= age < 60

    def test_stale_cache_returns_none(self):
        import json, time
        from cclimits import read_cache, get_cache_path
        get_cache_path().write_text(json.dumps({"timestamp": time.time() - 120, "data": {}}))
        assert read_cache(60) is None


class TestAtomicCacheWrite:
    """write_cache must not leave a partial file or a stray temp file."""

    def test_no_tmp_file_left_behind(self):
        from cclimits import write_cache, get_cache_path
        assert write_cache({"zai": {"status": "ok"}})
        cache_file = get_cache_path()
        assert cache_file.exists()
        assert not cache_file.with_suffix(".json.tmp").exists()


class TestIsTransientError:
    """_is_transient_error classifies which failures qualify for stale fallback."""

    def test_no_creds_not_transient(self):
        from cclimits import _is_transient_error
        assert not _is_transient_error({"error": "No credentials found"})

    def test_token_expired_not_transient(self):
        from cclimits import _is_transient_error
        assert not _is_transient_error({"error": "Token expired"})
        assert not _is_transient_error({"token_status": "expired", "error": "some error"})

    def test_invalid_api_key_not_transient(self):
        from cclimits import _is_transient_error
        assert not _is_transient_error({"error": "Invalid API key"})

    def test_forbidden_not_transient(self):
        from cclimits import _is_transient_error
        assert not _is_transient_error({"error": "Forbidden"})

    def test_authentication_failed_not_transient(self):
        from cclimits import _is_transient_error
        assert not _is_transient_error({"error": "Authentication failed"})

    def test_401_in_error_string_not_transient(self):
        from cclimits import _is_transient_error
        assert not _is_transient_error({"error": "API error (HTTP 401)"})

    def test_403_in_error_string_not_transient(self):
        from cclimits import _is_transient_error
        assert not _is_transient_error({"error": "API error (HTTP 403)"})

    def test_500_is_transient(self):
        from cclimits import _is_transient_error
        assert _is_transient_error({"error": "API error (500)"})

    def test_connection_error_is_transient(self):
        from cclimits import _is_transient_error
        assert _is_transient_error({"error": "API error (0)"})
        assert _is_transient_error({"error": "HTTP 0"})

    def test_could_not_fetch_is_transient(self):
        from cclimits import _is_transient_error
        assert _is_transient_error({"error": "Could not fetch usage"})

    def test_generic_api_error_is_transient(self):
        from cclimits import _is_transient_error
        assert _is_transient_error({"error": "API error"})

    def test_no_error_key_not_transient(self):
        from cclimits import _is_transient_error
        assert not _is_transient_error({"status": "ok"})
        assert not _is_transient_error({})

    def test_non_dict_not_transient(self):
        from cclimits import _is_transient_error
        assert not _is_transient_error(None)
        assert not _is_transient_error("error")


class TestApplyStaleFallback:
    """apply_stale_fallback replaces transient errors with stale good entries."""

    def test_transient_error_replaced_with_stale_good_entry(self):
        from cclimits import apply_stale_fallback
        results = {"zai": {"error": "API error (500)"}}
        cached = {"zai": {"status": "ok", "token_quota": {"percentage": 30}}}
        updated = apply_stale_fallback(results, cached, cached_age=120)
        assert updated["zai"]["status"] == "ok"
        assert updated["zai"]["stale_fallback"] is True
        assert updated["zai"]["stale_age_seconds"] == 120

    def test_no_creds_not_replaced(self):
        from cclimits import apply_stale_fallback
        results = {"zai": {"error": "No credentials found"}}
        cached = {"zai": {"status": "ok", "token_quota": {"percentage": 30}}}
        updated = apply_stale_fallback(results, cached, cached_age=60)
        assert updated["zai"]["error"] == "No credentials found"
        assert "stale_fallback" not in updated["zai"]

    def test_expired_token_not_replaced(self):
        from cclimits import apply_stale_fallback
        results = {"codex": {"token_status": "expired"}}
        cached = {"codex": {"status": "ok", "primary_window": {"used": "10%"}}}
        updated = apply_stale_fallback(results, cached, cached_age=60)
        assert updated["codex"]["token_status"] == "expired"
        assert "stale_fallback" not in updated["codex"]

    def test_401_not_replaced(self):
        from cclimits import apply_stale_fallback
        results = {"openrouter": {"error": "Invalid API key"}}
        cached = {"openrouter": {"status": "ok", "balance_usd": 10.0}}
        updated = apply_stale_fallback(results, cached, cached_age=60)
        assert updated["openrouter"]["error"] == "Invalid API key"
        assert "stale_fallback" not in updated["openrouter"]

    def test_no_cached_entry_not_replaced(self):
        from cclimits import apply_stale_fallback
        results = {"zai": {"error": "API error (500)"}}
        cached = {"claude": {"status": "ok"}}
        updated = apply_stale_fallback(results, cached, cached_age=60)
        assert updated["zai"]["error"] == "API error (500)"

    def test_cached_entry_not_good_not_replaced(self):
        from cclimits import apply_stale_fallback
        results = {"zai": {"error": "API error (500)"}}
        cached = {"zai": {"error": "Could not fetch usage"}}
        updated = apply_stale_fallback(results, cached, cached_age=60)
        assert updated["zai"]["error"] == "API error (500)"

    def test_older_than_cap_not_replaced(self):
        from cclimits import apply_stale_fallback, STALE_CACHE_MAX_AGE
        results = {"zai": {"error": "API error (500)"}}
        cached = {"zai": {"status": "ok", "token_quota": {"percentage": 30}}}
        updated = apply_stale_fallback(results, cached, cached_age=STALE_CACHE_MAX_AGE)
        assert updated["zai"]["error"] == "API error (500)"

    def test_successful_entry_not_replaced(self):
        from cclimits import apply_stale_fallback
        results = {"zai": {"status": "ok", "token_quota": {"percentage": 50}}}
        cached = {"zai": {"status": "ok", "token_quota": {"percentage": 30}}}
        updated = apply_stale_fallback(results, cached, cached_age=60)
        assert updated["zai"]["token_quota"]["percentage"] == 50
        assert "stale_fallback" not in updated["zai"]

    def test_mixed_results_only_transients_replaced(self):
        from cclimits import apply_stale_fallback
        results = {
            "zai": {"error": "API error (500)"},
            "claude": {"error": "No credentials found"},
            "codex": {"status": "ok", "primary_window": {"used": "10%"}},
        }
        cached = {
            "zai": {"status": "ok", "token_quota": {"percentage": 30}},
            "claude": {"status": "ok", "five_hour": {"used": "45%"}},
            "codex": {"status": "ok", "primary_window": {"used": "99%"}},
        }
        updated = apply_stale_fallback(results, cached, cached_age=300)
        assert updated["zai"]["stale_fallback"] is True
        assert updated["zai"]["stale_age_seconds"] == 300
        assert updated["claude"]["error"] == "No credentials found"
        assert updated["codex"]["primary_window"]["used"] == "10%"


class TestReadCacheMaxAge:
    """read_cache(ttl, max_age=...) reads stale cache bounded by max_age."""

    def test_stale_within_max_age_returned(self):
        import json, time
        from cclimits import read_cache, get_cache_path
        get_cache_path().write_text(json.dumps({
            "timestamp": time.time() - 120,
            "data": {"zai": {"status": "ok"}},
        }))
        # ttl=60 would normally miss, but max_age=300 allows it
        cached = read_cache(60, max_age=300)
        assert cached is not None
        data, age = cached
        assert data["zai"]["status"] == "ok"
        assert 100 <= age <= 130

    def test_stale_beyond_max_age_returns_none(self):
        import json, time
        from cclimits import read_cache, get_cache_path
        get_cache_path().write_text(json.dumps({
            "timestamp": time.time() - 600,
            "data": {"zai": {"status": "ok"}},
        }))
        assert read_cache(60, max_age=300) is None

    def test_max_age_none_uses_ttl(self):
        import json, time
        from cclimits import read_cache, get_cache_path
        get_cache_path().write_text(json.dumps({
            "timestamp": time.time() - 120,
            "data": {"zai": {"status": "ok"}},
        }))
        # max_age=None: ttl=60 is the bound, 120 > 60 -> None
        assert read_cache(60) is None
        assert read_cache(60, max_age=None) is None
