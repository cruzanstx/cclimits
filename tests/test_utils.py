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
