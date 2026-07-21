"""
Tests for output formatting functions.
"""

from io import StringIO
from unittest.mock import patch
import pytest
from cclimits import print_section, print_oneline, get_status_icon


class TestPrintSection:
    """Tests for print_section() function."""

    def test_claude_data_basic(self, capsys):
        """Test printing Claude basic usage data."""
        data = {
            "status": "ok",
            "five_hour": {
                "used": "45.5%",
                "remaining": "54.5%",
                "resets_in": "2h 30m"
            },
            "seven_day": {
                "used": "72.3%",
                "remaining": "27.7%",
                "resets_in": "5d 12h"
            }
        }

        print_section("Claude Code", data)
        captured = capsys.readouterr()

        assert "Claude Code" in captured.out
        assert "5-Hour Window" in captured.out
        assert "45.5%" in captured.out
        assert "2h 30m" in captured.out
        assert "7-Day Window" in captured.out
        assert "72.3%" in captured.out

    def test_claude_data_with_opus(self, capsys):
        """Test printing Claude data with Opus usage."""
        data = {
            "status": "ok",
            "five_hour": {
                "used": "30.0%",
                "remaining": "70.0%",
                "resets_in": "1h 15m"
            },
            "opus": {
                "used": "85.0%"
            }
        }

        print_section("Claude Code", data)
        captured = capsys.readouterr()

        assert "Opus (7-day): 85.0% used" in captured.out

    def test_codex_data(self, capsys):
        """Test printing Codex/ChatGPT usage data."""
        data = {
            "auth": "OAuth (ChatGPT)",
            "status": "ok",
            "plan": "Plus",
            "primary_window": {
                "used": "35.0%",
                "remaining": "65.0%",
                "window": "5h",
                "resets_in": "2h 0m"
            },
            "secondary_window": {
                "used": "68.5%",
                "remaining": "31.5%",
                "window": "7d",
                "resets_in": "4d 0h"
            },
            "code_review": {
                "used": "15.0%"
            }
        }

        print_section("OpenAI Codex", data)
        captured = capsys.readouterr()

        assert "Auth: OAuth (ChatGPT)" in captured.out
        assert "Plan: Plus" in captured.out
        assert "5h Window" in captured.out
        assert "7d Window" in captured.out
        assert "Code Review Quota: 15.0% used" in captured.out

    def test_codex_limit_reached(self, capsys):
        """Test Codex data when limit is reached."""
        data = {
            "auth": "OAuth (ChatGPT)",
            "status": "ok",
            "primary_window": {
                "used": "100.0%",
                "remaining": "0.0%",
                "window": "5h"
            },
            "limit_reached": True
        }

        print_section("OpenAI Codex", data)
        captured = capsys.readouterr()

        assert "Rate limit reached" in captured.out
        assert "100.0%" in captured.out

    def test_gemini_data(self, capsys):
        """Test printing Gemini usage data."""
        data = {
            "auth": "OAuth (Google Account)",
            "status": "ok",
            "tier": "Free",
            "models": {
                "gemini-2.5-flash": {
                    "used": "35.0%",
                    "remaining": "65.0%",
                    "resets_in": "12h 30m"
                },
                "gemini-2.5-pro": {
                    "used": "60.0%",
                    "remaining": "40.0%"
                }
            }
        }

        print_section("Gemini CLI", data)
        captured = capsys.readouterr()

        assert "Auth: OAuth (Google Account)" in captured.out
        assert "Tier: Free" in captured.out
        assert "Model Quotas" in captured.out
        assert "gemini-2.5-flash" in captured.out
        assert "35.0% used" in captured.out

    def test_gemini_token_refreshed(self, capsys):
        """Test Gemini data with auto-refreshed token."""
        data = {
            "auth": "OAuth (Google Account)",
            "status": "ok",
            "token_refreshed": True,
            "token_expires_in": "1h 30m",
            "models": {}
        }

        print_section("Gemini CLI", data)
        captured = capsys.readouterr()

        assert "Token auto-refreshed" in captured.out
        assert "Token expires in: 1h 30m" in captured.out

    def test_zai_data(self, capsys):
        """Test printing Z.AI usage data."""
        data = {
            "status": "ok",
            "token_quota": {
                "limit": 10000000,
                "used": 3500000,
                "remaining": 6500000,
                "percentage": 35.0,
                "resets_in": "2d 5h"
            },
            "request_quota": {
                "limit": 1000,
                "used": 250,
                "remaining": 750
            },
            "weekly_usage": {
                "calls": 1523,
                "tokens": 4500000
            }
        }

        print_section("Z.AI (GLM-4)", data)
        captured = capsys.readouterr()

        assert "Token Quota:" in captured.out
        assert "35.0%" in captured.out
        assert "3,500,000 / 10,000,000" in captured.out
        assert "Request Quota:" in captured.out
        assert "7-Day Historical" in captured.out

    def test_antigravity_model_table(self, capsys):
        """Test printing Antigravity per-model quota table."""
        data = {
            "status": "ok",
            "project_id": "test-project",
            "subscription_tier": "free",
            "summary": {
                "model_count": 2,
                "min_remaining_pct": 65,
                "avg_remaining_pct": 78,
            },
            "models": [
                {"name": "gemini-3-pro", "remaining_pct": 92, "reset_time": "2026-05-30T18:00:00Z"},
                {"name": "claude-opus-4-5-thinking", "remaining_pct": 65, "reset_time": "2026-05-30T17:00:00Z"},
            ],
        }

        print_section("Google Antigravity", data)
        captured = capsys.readouterr()

        assert "Google Antigravity" in captured.out
        assert "Project: test-project" in captured.out
        assert "Tightest:  65% remaining" in captured.out
        assert captured.out.index("claude-opus-4-5-thinking") < captured.out.index("gemini-3-pro")

    def test_error_message(self, capsys):
        """Test printing error message."""
        data = {
            "error": "Token expired",
            "hint": "Run 'gemini' to refresh token"
        }

        print_section("Test Tool", data)
        captured = capsys.readouterr()

        assert "Token expired" in captured.out
        assert "Run 'gemini' to refresh token" in captured.out

    def test_authenticated_status(self, capsys):
        """Test printing authenticated status."""
        data = {
            "status": "authenticated",
            "auth": "API Key",
            "api_key_valid": True
        }

        print_section("Test Tool", data)
        captured = capsys.readouterr()

        assert "Authenticated" in captured.out
        assert "Auth: API Key" in captured.out
        assert "API Key: valid" in captured.out

    def test_minimal_data(self, capsys):
        """Test printing minimal data."""
        data = {
            "status": "ok",
            "note": "No detailed quota available"
        }

        print_section("Test Tool", data)
        captured = capsys.readouterr()

        assert "Test Tool" in captured.out
        assert "Connected" in captured.out
        assert "No detailed quota available" in captured.out

    def test_dashboard_link(self, capsys):
        """Test printing dashboard link."""
        data = {
            "status": "authenticated",
            "dashboard": "https://example.com/dashboard"
        }

        print_section("Test Tool", data)
        captured = capsys.readouterr()

        assert "https://example.com/dashboard" in captured.out

    def test_hint_and_fallback(self, capsys):
        """Test printing hint and fallback messages."""
        data = {
            "hint": "Check usage at platform.example.com",
            "fallback": "https://platform.example.com/usage"
        }

        print_section("Test Tool", data)
        captured = capsys.readouterr()

        assert "Check usage at platform.example.com" in captured.out
        assert "https://platform.example.com/usage" in captured.out


class TestPrintOneline:
    """Tests for print_oneline() function."""

    def test_single_tool_5h_window(self, capsys):
        """Test single tool with 5h window."""
        results = {
            "claude": {
                "status": "ok",
                "five_hour": {"used": "45.5%"},
                "seven_day": {"used": "72.3%"}
            }
        }

        print_oneline(results, "5h")
        captured = capsys.readouterr()

        assert "Claude: 45.5% (5h)" in captured.out
        assert "✅" in captured.out or "⚠️" in captured.out  # Icon depends on percentage

    def test_single_tool_7d_window(self, capsys):
        """Test single tool with 7d window."""
        results = {
            "claude": {
                "status": "ok",
                "five_hour": {"used": "45.5%"},
                "seven_day": {"used": "72.3%"}
            }
        }

        print_oneline(results, "7d")
        captured = capsys.readouterr()

        assert "Claude: 72.3% (7d)" in captured.out

    def test_multiple_tools(self, capsys):
        """Test multiple tools in one line."""
        results = {
            "claude": {
                "status": "ok",
                "five_hour": {"used": "45.5%"},
                "seven_day": {"used": "72.3%"}
            },
            "codex": {
                "status": "ok",
                "primary_window": {"used": "35.0%"},
                "secondary_window": {"used": "68.5%"}
            }
        }

        print_oneline(results, "5h")
        captured = capsys.readouterr()

        assert "Claude: 45.5% (5h)" in captured.out
        assert "Codex: 35.0% (5h)" in captured.out
        assert " | " in captured.out  # Separator

    def test_error_states(self, capsys):
        """Test tools with errors."""
        results = {
            "claude": {"error": "No credentials"},
            "codex": {"error": "Token expired"}
        }

        print_oneline(results, "5h")
        captured = capsys.readouterr()

        assert "Claude: ❌" in captured.out
        assert "Codex: ⏰" in captured.out

    def test_zai_in_oneline(self, capsys):
        """Test Z.AI in oneline output."""
        results = {
            "zai": {
                "status": "ok",
                "token_quota": {"percentage": 35.0}
            }
        }

        print_oneline(results, "5h")
        captured = capsys.readouterr()

        assert "Z.AI: 35.0%" in captured.out
        assert "✅" in captured.out

    def test_gemini_in_oneline(self, capsys):
        """Test Gemini in oneline output (grouped by tier)."""
        results = {
            "gemini": {
                "status": "ok",
                "models": {
                    "gemini-2.5-flash": {"used": "35.0%"},
                    "gemini-2.5-pro": {"used": "60.0%"},
                    "gemini-3-flash-preview": {"used": "20.0%"}
                }
            }
        }

        print_oneline(results, "5h")
        captured = capsys.readouterr()

        assert "Gemini:" in captured.out
        assert "3-Flash 20.0%" in captured.out
        assert "Flash 35.0%" in captured.out
        assert "Pro 60.0%" in captured.out

    def test_antigravity_in_oneline_shows_usage(self, capsys):
        """Test Antigravity oneline output displays usage, not remaining quota."""
        results = {
            "antigravity": {
                "status": "ok",
                "summary": {
                    "model_count": 20,
                    "min_remaining_pct": 96,
                    "avg_remaining_pct": 99,
                },
            }
        }

        print_oneline(results, "5h")
        captured = capsys.readouterr()

        assert "Antigravity: 4% (20 models)" in captured.out
        assert "96%" not in captured.out

    def test_high_usage_icons(self, capsys):
        """Test status icons for high usage."""
        results = {
            "claude": {
                "status": "ok",
                "five_hour": {"used": "95.0%"}  # High usage
            }
        }

        print_oneline(results, "5h")
        captured = capsys.readouterr()

        assert "Claude: 95.0% (5h)" in captured.out
        assert "🔴" in captured.out  # Red for 90%+

    def test_warning_usage_icons(self, capsys):
        """Test status icons for warning usage."""
        results = {
            "claude": {
                "status": "ok",
                "five_hour": {"used": "75.0%"}  # Warning usage
            }
        }

        print_oneline(results, "5h")
        captured = capsys.readouterr()

        assert "Claude: 75.0% (5h)" in captured.out
        assert "⚠️" in captured.out  # Warning for 70%+

    def test_all_four_tools(self, capsys):
        """Test all four tools in oneline output."""
        results = {
            "claude": {
                "status": "ok",
                "five_hour": {"used": "45.5%"},
                "seven_day": {"used": "72.3%"}
            },
            "codex": {
                "status": "ok",
                "primary_window": {"used": "35.0%"},
                "secondary_window": {"used": "68.5%"}
            },
            "zai": {
                "status": "ok",
                "token_quota": {"percentage": 30.0}
            },
            "gemini": {
                "status": "ok",
                "models": {
                    "gemini-2.5-flash": {"used": "25.0%"},
                    "gemini-2.5-pro": {"used": "50.0%"}
                }
            }
        }

        print_oneline(results, "5h")
        captured = capsys.readouterr()

        # Check all tools are present
        assert "Claude:" in captured.out
        assert "Codex:" in captured.out
        assert "Z.AI:" in captured.out
        assert "Gemini:" in captured.out
        # Check separators
        assert captured.out.count(" | ") >= 3

    def test_default_window(self, capsys):
        """Test default window (5h) when not specified."""
        results = {
            "claude": {
                "status": "ok",
                "five_hour": {"used": "45.5%"},
                "seven_day": {"used": "72.3%"}
            }
        }

        print_oneline(results)  # No window specified
        captured = capsys.readouterr()

        assert "Claude: 45.5% (5h)" in captured.out

    def test_invalid_window_defaults_to_5h(self, capsys):
        """Test invalid window defaults to 5h."""
        results = {
            "claude": {
                "status": "ok",
                "five_hour": {"used": "45.5%"},
                "seven_day": {"used": "72.3%"}
            }
        }

        print_oneline(results, "invalid")
        captured = capsys.readouterr()

        # Should use 5h as fallback
        assert "Claude: 45.5% (5h)" in captured.out

    def test_gemini_partial_tier_data(self, capsys):
        """Test Gemini with only some tiers having data."""
        results = {
            "gemini": {
                "status": "ok",
                "models": {
                    "gemini-2.5-flash": {"used": "35.0%"},
                    "gemini-2.5-pro": {"used": "60.0%"}
                    # Missing 3-Flash tier
                }
            }
        }

        print_oneline(results, "5h")
        captured = capsys.readouterr()

        assert "Flash 35.0%" in captured.out
        assert "Pro 60.0%" in captured.out
        # 3-Flash should not appear
        assert "3-Flash" not in captured.out


class TestPrintOnelineEdgeCases:
    """Edge case tests for oneline output."""

    def test_empty_results(self, capsys):
        """Test oneline with empty results."""
        print_oneline({})
        captured = capsys.readouterr()
        # Should just print newline
        assert captured.out == "\n"

    def test_invalid_window_uses_5h_fallback(self, capsys):
        """Test invalid window values use the 5h fallback."""
        results = {
            "claude": {
                "status": "ok",
                "five_hour": {"used": "45.5%"},
                "seven_day": {"used": "72.3%"}
            }
        }
        print_oneline(results, "invalid")
        captured = capsys.readouterr()
        assert "Claude: 45.5% (5h)" in captured.out


class TestOnelineSingleWindowDegradation:
    """A provider that exposes only one window still renders in every mode,
    labeled by the window it actually has (Codex weekly-only case)."""

    def test_both_mode_shows_lone_weekly_window(self, capsys):
        results = {"codex": {"status": "ok", "secondary_window": {"used": "6%"}}}
        print_oneline(results, "both")
        captured = capsys.readouterr()
        assert "Codex: 6% (7d)" in captured.out

    def test_5h_mode_falls_back_to_weekly(self, capsys):
        results = {"codex": {"status": "ok", "secondary_window": {"used": "6%"}}}
        print_oneline(results, "5h")
        captured = capsys.readouterr()
        assert "Codex: 6% (7d)" in captured.out

    def test_both_mode_still_dual_when_both_present(self, capsys):
        results = {"codex": {"status": "ok",
                             "primary_window": {"used": "35%"},
                             "secondary_window": {"used": "68%"}}}
        print_oneline(results, "both")
        captured = capsys.readouterr()
        assert "Codex: 35%/68%" in captured.out


class TestOnelineMissingCredentials:
    """Missing credentials render 🔑 (config issue), not ❌ (outage)."""

    def test_no_creds_shows_key_icon(self, capsys):
        results = {
            "zai": {"error": "No credentials found"},
            "codex": {"error": "Token expired"},
        }
        print_oneline(results, "both")
        captured = capsys.readouterr()
        assert "Z.AI: 🔑" in captured.out
        assert "Codex: ⏰" in captured.out

    def test_no_creds_noemoji_shows_no_key_text(self, capsys):
        results = {"zai": {"error": "No credentials found"}}
        print_oneline(results, "5h", use_color=True)
        captured = capsys.readouterr()
        assert "no key" in captured.out
        assert "ERR" not in captured.out


class TestOnelineResets:
    """--resets appends compact reset countdowns to oneline output."""

    def test_default_omits_resets(self, capsys):
        results = {"claude": {"status": "ok",
                              "five_hour": {"used": "45.5%", "resets_in": "2h 15m"},
                              "seven_day": {"used": "72.3%", "resets_in": "4d 12h"}}}
        print_oneline(results, "5h")
        assert "↻" not in capsys.readouterr().out

    def test_single_window_reset(self, capsys):
        results = {"claude": {"status": "ok",
                              "five_hour": {"used": "45.5%", "resets_in": "2h 15m"},
                              "seven_day": {"used": "72.3%", "resets_in": "4d 12h"}}}
        print_oneline(results, "5h", show_resets=True)
        assert "↻2h15m" in capsys.readouterr().out

    def test_both_windows_reset(self, capsys):
        results = {"claude": {"status": "ok",
                              "five_hour": {"used": "45.5%", "resets_in": "2h 15m"},
                              "seven_day": {"used": "72.3%", "resets_in": "4d 12h"}}}
        print_oneline(results, "both", show_resets=True)
        assert "↻2h15m/4d12h" in capsys.readouterr().out

    def test_missing_or_na_reset_omitted(self, capsys):
        results = {"claude": {"status": "ok",
                              "five_hour": {"used": "45.5%", "resets_in": "N/A"}},
                   "zai": {"status": "ok", "token_quota": {"percentage": 30.0}}}
        print_oneline(results, "5h", show_resets=True)
        assert "↻" not in capsys.readouterr().out

    def test_antigravity_earliest_reset(self, capsys):
        results = {"antigravity": {"status": "ok",
                                   "summary": {"min_remaining_pct": 97, "model_count": 20,
                                               "next_reset_in": "1h 30m"}}}
        print_oneline(results, "5h", show_resets=True)
        assert "Antigravity: 3% (20 models) ✅ ↻1h30m" in capsys.readouterr().out

    def test_zai_and_synthetic_resets(self, capsys):
        results = {
            "zai": {"status": "ok", "token_quota": {"percentage": 30.0, "resets_in": "1h 5m"}},
            "synthetic": {"status": "ok",
                          "rolling_5h": {"percentage": 10, "next_tick_in": "45m"},
                          "weekly_credits": {"percent_used": 20, "next_regen_in": "3d 2h"}},
        }
        print_oneline(results, "both", show_resets=True)
        out = capsys.readouterr().out
        assert "Z.AI" in out and "↻1h5m" in out
        assert "Synthetic" in out and "↻45m/3d2h" in out


class TestOnelineCacheAge:
    """Cached oneline output is labeled with its age."""

    def test_cache_age_suffix(self, capsys):
        results = {"zai": {"status": "ok", "token_quota": {"percentage": 30.0}}}
        print_oneline(results, "5h", cache_age=42)
        captured = capsys.readouterr()
        assert captured.out.rstrip().endswith("(cached 42s)")

    def test_no_suffix_when_live(self, capsys):
        results = {"zai": {"status": "ok", "token_quota": {"percentage": 30.0}}}
        print_oneline(results, "5h")
        captured = capsys.readouterr()
        assert "cached" not in captured.out


class TestZaiOnelineBoth:
    """In 'both' mode Z.AI shows tokens%/requests% like other dual-window providers."""

    def test_both_shows_request_quota(self, capsys):
        results = {"zai": {
            "status": "ok",
            "token_quota": {"percentage": 1},
            "request_quota": {"limit": 4000, "used": 1000, "remaining": 3000},
        }}
        print_oneline(results, "both")
        captured = capsys.readouterr()
        assert "Z.AI: 1%/25%" in captured.out

    def test_both_without_request_quota_falls_back(self, capsys):
        results = {"zai": {"status": "ok", "token_quota": {"percentage": 30.0}}}
        print_oneline(results, "both")
        captured = capsys.readouterr()
        assert "Z.AI: 30.0% (5h)" in captured.out

    def test_5h_window_unchanged(self, capsys):
        results = {"zai": {
            "status": "ok",
            "token_quota": {"percentage": 30.0},
            "request_quota": {"limit": 4000, "used": 1000},
        }}
        print_oneline(results, "5h")
        captured = capsys.readouterr()
        assert "Z.AI: 30.0% (5h)" in captured.out


class TestOnelineExpiredToken:
    """Expired tokens render ⏰ instead of silently vanishing from the line."""

    def test_gemini_expired_token_shown(self, capsys):
        results = {"gemini": {"token_status": "expired", "hint_refresh": "Run 'gemini' to refresh token"}}
        print_oneline(results, "both")
        captured = capsys.readouterr()
        assert "Gemini: ⏰" in captured.out

    def test_codex_expired_token_shown(self, capsys):
        results = {"codex": {"auth": "OAuth (ChatGPT)", "token_status": "expired"}}
        print_oneline(results, "5h")
        captured = capsys.readouterr()
        assert "Codex: ⏰" in captured.out

    def test_claude_token_expired_error_uses_expired_icon(self, capsys):
        results = {"claude": {"error": "Token expired", "hint": "Run 'claude' to re-authenticate"}}
        print_oneline(results, "5h")
        captured = capsys.readouterr()
        assert "Claude: ⏰" in captured.out

    def test_expired_noemoji(self, capsys):
        results = {"gemini": {"token_status": "expired"}}
        print_oneline(results, "5h", use_color=True)
        captured = capsys.readouterr()
        assert "expired" in captured.out


class TestOnelineStaleFallback:
    """Stale-cache fallback entries render a visible age marker in oneline."""

    def test_stale_marker_shown(self, capsys):
        results = {"zai": {
            "status": "ok",
            "token_quota": {"percentage": 1},
            "stale_fallback": True,
            "stale_age_seconds": 1920,  # 32m
        }}
        print_oneline(results, "5h")
        captured = capsys.readouterr()
        assert "Z.AI: 1% (5h)" in captured.out
        assert "(stale 32m)" in captured.out

    def test_non_stale_no_marker(self, capsys):
        results = {"zai": {
            "status": "ok",
            "token_quota": {"percentage": 1},
        }}
        print_oneline(results, "5h")
        captured = capsys.readouterr()
        assert "stale" not in captured.out

    def test_stale_marker_seconds(self, capsys):
        results = {"zai": {
            "status": "ok",
            "token_quota": {"percentage": 1},
            "stale_fallback": True,
            "stale_age_seconds": 42,
        }}
        print_oneline(results, "5h")
        captured = capsys.readouterr()
        assert "(stale 42s)" in captured.out

    def test_stale_marker_with_color(self, capsys):
        results = {"zai": {
            "status": "ok",
            "token_quota": {"percentage": 1},
            "stale_fallback": True,
            "stale_age_seconds": 300,
        }}
        print_oneline(results, "5h", use_color=True)
        captured = capsys.readouterr()
        assert "(stale 5m)" in captured.out


class TestPrintSectionStaleFallback:
    """Detailed output shows a stale-fallback notice line."""

    def test_stale_line_shown(self, capsys):
        data = {
            "status": "ok",
            "five_hour": {"used": "45.0%"},
            "stale_fallback": True,
            "stale_age_seconds": 1800,
        }
        print_section("Claude Code", data)
        captured = capsys.readouterr()
        assert "Stale fallback" in captured.out
        assert "30m" in captured.out

    def test_non_stale_no_stale_line(self, capsys):
        data = {
            "status": "ok",
            "five_hour": {"used": "45.0%"},
        }
        print_section("Claude Code", data)
        captured = capsys.readouterr()
        assert "Stale fallback" not in captured.out
