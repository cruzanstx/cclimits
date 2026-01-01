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
