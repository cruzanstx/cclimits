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
        assert "Codex: ❌" in captured.out

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

    def test_invalid_window_ignored(self, capsys):
        """Test that invalid window is ignored by print_oneline (validation happens in main())."""
        results = {
            "claude": {
                "status": "ok",
                "five_hour": {"used": "45.5%"},
                "seven_day": {"used": "72.3%"}
            }
        }
        # print_oneline doesn't validate window, so this just won't match data
        print_oneline(results, "invalid")
        captured = capsys.readouterr()
        # No match, so empty output
        assert captured.out == "\n"
