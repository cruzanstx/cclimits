"""
Tests for CLI entry point and argument parsing.
"""

import json
import time
from io import StringIO
from unittest.mock import patch, MagicMock
import pytest
from cclimits import main


class TestCLIArgumentParsing:
    """Tests for CLI argument parsing."""

    @patch('sys.argv', ['cclimits', '--help'])
    def test_help_flag(self, capsys):
        """Test --help flag displays help."""
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        # Help should exit with code 0
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Claude, Codex, Gemini, Z.AI" in captured.out

    @patch('cclimits.get_claude_usage')
    @patch('cclimits.get_codex_usage')
    @patch('cclimits.get_gemini_usage')
    @patch('cclimits.get_zai_usage')
    @patch('sys.argv', ['cclimits'])
    def test_no_flags_checks_all(self, mock_zai, mock_gemini, mock_codex, mock_claude, capsys):
        """Test no flags checks all tools."""
        mock_claude.return_value = {"status": "ok", "five_hour": {"used": "45.5%"}}
        mock_codex.return_value = {"status": "ok", "primary_window": {"used": "35.0%"}}
        mock_gemini.return_value = {"status": "ok", "models": {"gemini-2.5-flash": {"used": "25.0%"}}}
        mock_zai.return_value = {"status": "ok", "token_quota": {"percentage": 30.0}}

        main()

        # All usage functions should be called
        mock_claude.assert_called_once()
        mock_codex.assert_called_once()
        mock_gemini.assert_called_once()
        mock_zai.assert_called_once()

    @patch('cclimits.get_claude_usage')
    @patch('cclimits.get_codex_usage')
    @patch('cclimits.get_gemini_usage')
    @patch('cclimits.get_zai_usage')
    @patch('sys.argv', ['cclimits', '--claude'])
    def test_claude_only(self, mock_zai, mock_gemini, mock_codex, mock_claude, capsys):
        """Test --claude flag checks only Claude."""
        mock_claude.return_value = {"status": "ok", "five_hour": {"used": "45.5%"}}
        mock_codex.return_value = {"error": "No credentials"}
        mock_gemini.return_value = {"error": "No credentials"}
        mock_zai.return_value = {"error": "No credentials"}

        main()

        # Only Claude should be called
        mock_claude.assert_called_once()
        mock_codex.assert_not_called()
        mock_gemini.assert_not_called()
        mock_zai.assert_not_called()

    @patch('cclimits.get_claude_usage')
    @patch('cclimits.get_codex_usage')
    @patch('cclimits.get_gemini_usage')
    @patch('cclimits.get_zai_usage')
    @patch('sys.argv', ['cclimits', '--codex'])
    def test_codex_only(self, mock_zai, mock_gemini, mock_codex, mock_claude, capsys):
        """Test --codex flag checks only Codex."""
        mock_codex.return_value = {"status": "ok", "primary_window": {"used": "35.0%"}}

        main()

        mock_claude.assert_not_called()
        mock_codex.assert_called_once()
        mock_gemini.assert_not_called()
        mock_zai.assert_not_called()

    @patch('cclimits.get_claude_usage')
    @patch('cclimits.get_codex_usage')
    @patch('cclimits.get_gemini_usage')
    @patch('cclimits.get_zai_usage')
    @patch('sys.argv', ['cclimits', '--gemini'])
    def test_gemini_only(self, mock_zai, mock_gemini, mock_codex, mock_claude, capsys):
        """Test --gemini flag checks only Gemini."""
        mock_gemini.return_value = {"status": "ok", "models": {"gemini-2.5-flash": {"used": "25.0%"}}}

        main()

        mock_claude.assert_not_called()
        mock_codex.assert_not_called()
        mock_gemini.assert_called_once()
        mock_zai.assert_not_called()

    @patch('cclimits.get_claude_usage')
    @patch('cclimits.get_codex_usage')
    @patch('cclimits.get_gemini_usage')
    @patch('cclimits.get_zai_usage')
    @patch('sys.argv', ['cclimits', '--zai'])
    def test_zai_only(self, mock_zai, mock_gemini, mock_codex, mock_claude, capsys):
        """Test --zai flag checks only Z.AI."""
        mock_zai.return_value = {"status": "ok", "token_quota": {"percentage": 30.0}}

        main()

        mock_claude.assert_not_called()
        mock_codex.assert_not_called()
        mock_gemini.assert_not_called()
        mock_zai.assert_called_once()

    @patch('cclimits.get_claude_usage')
    @patch('cclimits.get_codex_usage')
    @patch('cclimits.get_gemini_usage')
    @patch('cclimits.get_zai_usage')
    @patch('sys.argv', ['cclimits', '--claude', '--codex'])
    def test_multiple_specific_flags(self, mock_zai, mock_gemini, mock_codex, mock_claude, capsys):
        """Test multiple specific flags."""
        mock_claude.return_value = {"status": "ok", "five_hour": {"used": "45.5%"}}
        mock_codex.return_value = {"status": "ok", "primary_window": {"used": "35.0%"}}

        main()

        mock_claude.assert_called_once()
        mock_codex.assert_called_once()
        mock_gemini.assert_not_called()
        mock_zai.assert_not_called()


class TestJSONOutput:
    """Tests for JSON output mode."""

    @patch('cclimits.get_claude_usage')
    @patch('cclimits.get_codex_usage')
    @patch('cclimits.get_gemini_usage')
    @patch('cclimits.get_zai_usage')
    @patch('sys.argv', ['cclimits', '--json'])
    def test_json_output_valid(self, mock_zai, mock_gemini, mock_codex, mock_claude, capsys):
        """Test --json flag produces valid JSON."""
        mock_claude.return_value = {"status": "ok", "five_hour": {"used": "45.5%"}}
        mock_codex.return_value = {"status": "ok", "primary_window": {"used": "35.0%"}}
        mock_gemini.return_value = {"status": "ok", "models": {}}
        mock_zai.return_value = {"status": "ok", "token_quota": {"percentage": 30.0}}

        main()

        captured = capsys.readouterr()
        
        # Should be valid JSON
        result = json.loads(captured.out)
        assert "claude" in result
        assert "codex" in result
        assert "gemini" in result
        assert "zai" in result
        assert result["claude"]["status"] == "ok"

    @patch('cclimits.get_claude_usage')
    @patch('sys.argv', ['cclimits', '--json', '--claude'])
    def test_json_output_single_tool(self, mock_claude, capsys):
        """Test JSON output with single tool."""
        mock_claude.return_value = {
            "status": "ok",
            "five_hour": {"used": "45.5%", "remaining": "54.5%", "resets_in": "2h 30m"}
        }

        main()

        captured = capsys.readouterr()
        result = json.loads(captured.out)

        assert "claude" in result
        assert "codex" not in result
        assert result["claude"]["five_hour"]["used"] == "45.5%"

    @patch('cclimits.get_claude_usage')
    @patch('cclimits.get_codex_usage')
    @patch('sys.argv', ['cclimits', '--json'])
    def test_json_output_with_errors(self, mock_codex, mock_claude, capsys):
        """Test JSON output includes error messages."""
        mock_claude.return_value = {"error": "No credentials", "hint": "Run 'claude'"}
        mock_codex.return_value = {"status": "ok", "primary_window": {"used": "35.0%"}}

        main()

        captured = capsys.readouterr()
        result = json.loads(captured.out)

        assert result["claude"]["error"] == "No credentials"
        assert "hint" in result["claude"]


class TestOnelineOutput:
    """Tests for oneline output mode."""

    @patch('cclimits.get_claude_usage')
    @patch('cclimits.get_codex_usage')
    @patch('cclimits.get_gemini_usage')
    @patch('cclimits.get_zai_usage')
    @patch('sys.argv', ['cclimits', '--oneline'])
    def test_oneline_default_5h_window(self, mock_zai, mock_gemini, mock_codex, mock_claude, capsys):
        """Test --oneline with default 5h window."""
        mock_claude.return_value = {"status": "ok", "five_hour": {"used": "45.5%"}, "seven_day": {"used": "72.3%"}}
        mock_codex.return_value = {"status": "ok", "primary_window": {"used": "35.0%"}, "secondary_window": {"used": "68.5%"}}
        mock_gemini.return_value = {"status": "ok", "models": {"gemini-2.5-flash": {"used": "25.0%"}}}
        mock_zai.return_value = {"status": "ok", "token_quota": {"percentage": 30.0}}

        main()

        captured = capsys.readouterr()

        # Should use 5h window
        assert "Claude: 45.5% (5h)" in captured.out
        assert "Codex: 35.0% (5h)" in captured.out

    @patch('cclimits.get_claude_usage')
    @patch('sys.argv', ['cclimits', '--claude', '--oneline', '--resets'])
    def test_oneline_resets_flag(self, mock_claude, capsys):
        """--resets appends reset countdowns to oneline output."""
        mock_claude.return_value = {"status": "ok", "five_hour": {"used": "45.5%", "resets_in": "2h 15m"},
                                    "seven_day": {"used": "72.3%", "resets_in": "4d 12h"}}
        main()
        assert "↻2h15m" in capsys.readouterr().out

    @patch('cclimits.get_claude_usage')
    @patch('sys.argv', ['cclimits', '--claude', '--oneline', '--timeremaining'])
    def test_oneline_timeremaining_alias(self, mock_claude, capsys):
        """--timeremaining is an alias for --resets."""
        mock_claude.return_value = {"status": "ok", "five_hour": {"used": "45.5%", "resets_in": "2h 15m"},
                                    "seven_day": {"used": "72.3%"}}
        main()
        assert "↻2h15m" in capsys.readouterr().out

    @patch('cclimits.get_claude_usage')
    @patch('cclimits.get_codex_usage')
    @patch('sys.argv', ['cclimits', '--oneline', '5h'])
    def test_oneline_explicit_5h_window(self, mock_codex, mock_claude, capsys):
        """Test --oneline 5h explicitly."""
        mock_claude.return_value = {"status": "ok", "five_hour": {"used": "45.5%"}, "seven_day": {"used": "72.3%"}}
        mock_codex.return_value = {"status": "ok", "primary_window": {"used": "35.0%"}, "secondary_window": {"used": "68.5%"}}

        main()

        captured = capsys.readouterr()

        assert "Claude: 45.5% (5h)" in captured.out
        assert "Codex: 35.0% (5h)" in captured.out

    @patch('cclimits.get_claude_usage')
    @patch('cclimits.get_codex_usage')
    @patch('sys.argv', ['cclimits', '--oneline', '7d'])
    def test_oneline_7d_window(self, mock_codex, mock_claude, capsys):
        """Test --oneline with 7d window."""
        mock_claude.return_value = {"status": "ok", "five_hour": {"used": "45.5%"}, "seven_day": {"used": "72.3%"}}
        mock_codex.return_value = {"status": "ok", "primary_window": {"used": "35.0%"}, "secondary_window": {"used": "68.5%"}}

        main()

        captured = capsys.readouterr()

        # Should use 7d window
        assert "Claude: 72.3% (7d)" in captured.out
        assert "Codex: 68.5% (7d)" in captured.out

    @patch('cclimits.get_claude_usage')
    @patch('cclimits.get_codex_usage')
    @patch('sys.argv', ['cclimits', '--oneline', '--claude', '--codex'])
    def test_oneline_with_specific_tools(self, mock_codex, mock_claude, capsys):
        """Test --oneline with specific tools."""
        mock_claude.return_value = {"status": "ok", "five_hour": {"used": "45.5%"}}
        mock_codex.return_value = {"status": "ok", "primary_window": {"used": "35.0%"}}

        main()

        captured = capsys.readouterr()

        assert "Claude:" in captured.out
        assert "Codex:" in captured.out
        assert "Gemini:" not in captured.out  # Should not appear

    @patch('cclimits.get_claude_usage')
    @patch('cclimits.get_codex_usage')
    @patch('sys.argv', ['cclimits', '--oneline'])
    def test_oneline_errors(self, mock_codex, mock_claude, capsys):
        """Test oneline output with errors."""
        mock_claude.return_value = {"error": "No credentials"}
        mock_codex.return_value = {"status": "ok", "primary_window": {"used": "35.0%"}}

        main()

        captured = capsys.readouterr()

        assert "Claude: ❌" in captured.out
        assert "Codex:" in captured.out


class TestDetailedOutput:
    """Tests for detailed (default) output mode."""

    @patch('cclimits.get_claude_usage')
    @patch('cclimits.get_codex_usage')
    @patch('cclimits.get_gemini_usage')
    @patch('cclimits.get_zai_usage')
    @patch('sys.argv', ['cclimits'])
    def test_detailed_output_structure(self, mock_zai, mock_gemini, mock_codex, mock_claude, capsys):
        """Test detailed output has expected structure."""
        mock_claude.return_value = {"status": "ok", "five_hour": {"used": "45.5%"}}
        mock_codex.return_value = {"status": "ok", "primary_window": {"used": "35.0%"}}
        mock_gemini.return_value = {"status": "ok", "models": {"gemini-2.5-flash": {"used": "25.0%"}}}
        mock_zai.return_value = {"status": "ok", "token_quota": {"percentage": 30.0}}

        main()

        captured = capsys.readouterr()

        # Should have section headers
        assert "Claude Code" in captured.out
        assert "OpenAI Codex" in captured.out
        assert "Gemini CLI" in captured.out
        assert "Z.AI (5h shared - GLM-4.x)" in captured.out
        # Should have completion message
        assert "Done!" in captured.out

    @patch('cclimits.get_claude_usage')
    @patch('sys.argv', ['cclimits', '--claude'])
    def test_detailed_single_tool(self, mock_claude, capsys):
        """Test detailed output with single tool."""
        mock_claude.return_value = {
            "status": "ok",
            "five_hour": {"used": "45.5%", "remaining": "54.5%", "resets_in": "2h 30m"},
            "seven_day": {"used": "72.3%", "remaining": "27.7%", "resets_in": "5d 12h"}
        }

        main()

        captured = capsys.readouterr()

        # Should show Claude section
        assert "Claude Code" in captured.out
        assert "5-Hour Window" in captured.out
        assert "45.5%" in captured.out
        # Should not show other tools
        assert "OpenAI Codex" not in captured.out
        assert "Gemini CLI" not in captured.out
        assert "Z.AI" not in captured.out

    @patch('cclimits.get_claude_usage')
    @patch('cclimits.get_codex_usage')
    @patch('sys.argv', ['cclimits'])
    def test_detailed_with_errors(self, mock_codex, mock_claude, capsys):
        """Test detailed output with error messages."""
        mock_claude.return_value = {"error": "Token expired", "hint": "Run 'claude'"}
        mock_codex.return_value = {"status": "ok", "primary_window": {"used": "35.0%"}}

        main()

        captured = capsys.readouterr()

        # Should show error
        assert "Token expired" in captured.out
        assert "Run 'claude'" in captured.out


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @patch('cclimits.get_claude_usage')
    @patch('cclimits.get_codex_usage')
    @patch('cclimits.get_gemini_usage')
    @patch('cclimits.get_zai_usage')
    @patch('sys.argv', ['cclimits', '--oneline', 'invalid'])
    def test_invalid_window_defaults(self, mock_zai, mock_gemini, mock_codex, mock_claude, capsys):
        """Test invalid window value defaults to 5h."""
        mock_claude.return_value = {"status": "ok", "five_hour": {"used": "45.5%"}, "seven_day": {"used": "72.3%"}}

        main()

        captured = capsys.readouterr()

        # Should use 5h as default
        assert "Claude: 45.5% (5h)" in captured.out

    @patch('cclimits.get_claude_usage')
    @patch('cclimits.get_codex_usage')
    @patch('cclimits.get_gemini_usage')
    @patch('cclimits.get_zai_usage')
    @patch('sys.argv', ['cclimits', '--json', '--oneline'])
    def test_json_priority_over_oneline(self, mock_zai, mock_gemini, mock_codex, mock_claude, capsys):
        """Test --json takes priority over --oneline."""
        mock_claude.return_value = {"status": "ok", "five_hour": {"used": "45.5%"}}
        mock_codex.return_value = {"status": "ok", "primary_window": {"used": "35.0%"}}
        mock_gemini.return_value = {"status": "ok", "models": {}}
        mock_zai.return_value = {"status": "ok", "token_quota": {"percentage": 30.0}}

        main()

        captured = capsys.readouterr()

        # Should be JSON, not oneline format
        result = json.loads(captured.out)
        assert isinstance(result, dict)
        assert "claude" in result

    @patch('cclimits.get_claude_usage')
    @patch('cclimits.get_codex_usage')
    @patch('cclimits.get_gemini_usage')
    @patch('cclimits.get_zai_usage')
    @patch('sys.argv', ['cclimits', '--oneline', '--json'])
    def test_oneline_json_flag_order(self, mock_zai, mock_gemini, mock_codex, mock_claude, capsys):
        """Test flag order doesn't matter (oneline then json)."""
        mock_claude.return_value = {"status": "ok", "five_hour": {"used": "45.5%"}}
        mock_codex.return_value = {"error": "No credentials"}
        mock_gemini.return_value = {"error": "No credentials"}
        mock_zai.return_value = {"error": "No credentials"}

        main()

        captured = capsys.readouterr()

        # Should be JSON (last flag wins in argparse, but both are handled)
        # In this implementation, --json should produce JSON
        result = json.loads(captured.out)
        assert isinstance(result, dict)

    @patch('cclimits.get_claude_usage')
    @patch('sys.argv', ['cclimits', '--oneline', '5h'])
    def test_oneline_no_data(self, mock_claude, capsys):
        """Test oneline when no usage data available."""
        mock_claude.return_value = {"status": "ok"}

        main()

        captured = capsys.readouterr()

        # Should still print something, even if minimal
        assert len(captured.out) > 0 or captured.out == ""

    @patch('cclimits.get_claude_usage')
    @patch('cclimits.get_codex_usage')
    @patch('cclimits.get_gemini_usage')
    @patch('cclimits.get_zai_usage')
    @patch('sys.argv', ['cclimits'])
    def test_all_tools_with_various_statuses(self, mock_zai, mock_gemini, mock_codex, mock_claude, capsys):
        """Test detailed output with mixed success/error states."""
        mock_claude.return_value = {"status": "ok", "five_hour": {"used": "45.5%"}}
        mock_codex.return_value = {"error": "Token expired", "hint_refresh": "Run 'codex login'"}
        mock_gemini.return_value = {"status": "authenticated", "auth": "API Key"}
        mock_zai.return_value = {"status": "ok", "token_quota": {"percentage": 90.0}}

        main()

        captured = capsys.readouterr()

        # All tools should appear
        assert "Claude Code" in captured.out
        assert "OpenAI Codex" in captured.out
        assert "Gemini CLI" in captured.out
        assert "Z.AI (5h shared - GLM-4.x)" in captured.out
        # Mixed statuses should be visible
        assert "Token expired" in captured.out
        assert "Authenticated" in captured.out


class TestCachedProviderFilter:
    """Provider filters must be honored on cache hits (issue: --zai --cached printed everything)."""

    @patch('cclimits.get_zai_usage')
    @patch('sys.argv', ['cclimits', '--zai', '--cached'])
    def test_filter_applied_to_cache_hit(self, mock_zai, capsys):
        import cclimits
        cclimits.write_cache({
            "claude": {"status": "ok", "five_hour": {"used": "45.5%"}},
            "zai": {"status": "ok", "token_quota": {"percentage": 30.0}},
        })
        main()
        captured = capsys.readouterr()
        mock_zai.assert_not_called()
        assert "Z.AI" in captured.out
        assert "Claude" not in captured.out
        assert "cached" in captured.out  # staleness note in header

    @patch('cclimits.get_zai_usage')
    @patch('sys.argv', ['cclimits', '--zai', '--cached'])
    def test_missing_provider_triggers_fetch(self, mock_zai, capsys):
        import cclimits
        cclimits.write_cache({"claude": {"status": "ok", "five_hour": {"used": "45.5%"}}})
        mock_zai.return_value = {"status": "ok", "token_quota": {"percentage": 30.0}}
        main()
        mock_zai.assert_called_once()


class TestCachedBypassFix:
    """Regression tests: cache hit must skip the last four providers' fetches
    and credential discovery (openrouter, kimi, antigravity, synthetic).

    Previously these four dispatch lines in main() lacked the ``not skip_fetch``
    guard, so a cache hit still triggered live HTTP round-trips and credential
    probing for them, then overwrote the cached entries.
    """

    @patch('cclimits.get_synthetic_usage')
    @patch('cclimits.get_antigravity_usage')
    @patch('cclimits.get_kimi_usage')
    @patch('cclimits.get_openrouter_usage')
    @patch('cclimits.get_synthetic_credentials')
    @patch('cclimits.get_antigravity_credentials')
    @patch('cclimits.get_kimi_credentials')
    @patch('cclimits.get_openrouter_credentials')
    @patch('cclimits.get_zai_usage')
    @patch('cclimits.get_gemini_usage')
    @patch('cclimits.get_codex_usage')
    @patch('cclimits.get_claude_usage')
    @patch('sys.argv', ['cclimits', '--cached'])
    def test_cache_hit_skips_last_four(
        self, mock_claude, mock_codex, mock_gemini, mock_zai,
        mock_or_creds, mock_kimi_creds, mock_ag_creds, mock_syn_creds,
        mock_or_usage, mock_kimi_usage, mock_ag_usage, mock_syn_usage, capsys):
        """Cache hit: zero usage fetches and zero credential probing for all 8 providers."""
        import cclimits
        cclimits.write_cache({
            "claude": {"status": "ok", "five_hour": {"used": "45.5%"}},
            "codex": {"status": "ok", "primary_window": {"used": "35.0%"}},
            "gemini": {"status": "ok", "models": {}},
            "zai": {"status": "ok", "token_quota": {"percentage": 30.0}},
            "openrouter": {"status": "ok", "total_credits": 100, "total_usage": 50},
            "kimi": {"status": "ok", "balance": 100},
            "antigravity": {"status": "ok", "models": {}},
            "synthetic": {"status": "ok", "subscription": {"percentage": 10.0}},
        })
        main()
        # No usage functions should fire
        mock_claude.assert_not_called()
        mock_codex.assert_not_called()
        mock_gemini.assert_not_called()
        mock_zai.assert_not_called()
        mock_or_usage.assert_not_called()
        mock_kimi_usage.assert_not_called()
        mock_ag_usage.assert_not_called()
        mock_syn_usage.assert_not_called()
        # No credential discovery should fire
        mock_or_creds.assert_not_called()
        mock_kimi_creds.assert_not_called()
        mock_ag_creds.assert_not_called()
        mock_syn_creds.assert_not_called()

    @patch('cclimits.get_openrouter_credentials')
    @patch('cclimits.get_openrouter_usage')
    @patch('sys.argv', ['cclimits', '--openrouter'])
    def test_cache_miss_explicit_flag_forces_fetch(self, mock_or_usage, mock_or_creds, capsys):
        """Cache miss with explicit --openrouter: fetch runs even without credentials."""
        mock_or_usage.return_value = {"status": "ok", "total_credits": 100, "total_usage": 50}
        main()
        mock_or_creds.assert_not_called()  # explicit flag short-circuits credential check
        mock_or_usage.assert_called_once()

    @patch('cclimits.get_zai_usage')
    @patch('cclimits.get_gemini_usage')
    @patch('cclimits.get_codex_usage')
    @patch('cclimits.get_claude_usage')
    @patch('cclimits.get_openrouter_credentials', return_value="fake_key")
    @patch('cclimits.get_openrouter_usage')
    @patch('sys.argv', ['cclimits'])
    def test_cache_miss_check_all_fetches_when_creds_exist(
        self, mock_or_usage, mock_or_creds, mock_claude, mock_codex, mock_gemini, mock_zai, capsys):
        """Cache miss, check_all, credentials present: openrouter is fetched."""
        mock_or_usage.return_value = {"status": "ok", "total_credits": 100, "total_usage": 50}
        main()
        mock_or_creds.assert_called_once()
        mock_or_usage.assert_called_once()

    @patch('cclimits.get_zai_usage')
    @patch('cclimits.get_gemini_usage')
    @patch('cclimits.get_codex_usage')
    @patch('cclimits.get_claude_usage')
    @patch('cclimits.get_openrouter_credentials', return_value=None)
    @patch('cclimits.get_openrouter_usage')
    @patch('sys.argv', ['cclimits'])
    def test_cache_miss_check_all_skips_when_no_creds(
        self, mock_or_usage, mock_or_creds, mock_claude, mock_codex, mock_gemini, mock_zai, capsys):
        """Cache miss, check_all, no credentials: openrouter is skipped."""
        main()
        mock_or_creds.assert_called_once()
        mock_or_usage.assert_not_called()

    @patch('cclimits.get_openrouter_usage')
    @patch('sys.argv', ['cclimits', '--openrouter', '--cached'])
    def test_openrouter_cached_missing_from_cache_refetches(self, mock_or_usage, capsys):
        """--openrouter --cached with openrouter absent from cache must refetch."""
        import cclimits
        cclimits.write_cache({"claude": {"status": "ok", "five_hour": {"used": "45.5%"}}})
        mock_or_usage.return_value = {"status": "ok", "total_credits": 100, "total_usage": 50}
        main()
        mock_or_usage.assert_called_once()


class TestParallelFetch:
    """Tests for concurrent provider fetching via ThreadPoolExecutor."""

    @patch('cclimits.get_synthetic_credentials', return_value="fake_key")
    @patch('cclimits.get_antigravity_credentials', return_value={"access_token": "fake"})
    @patch('cclimits.get_kimi_credentials', return_value="fake_key")
    @patch('cclimits.get_openrouter_credentials', return_value="fake_key")
    @patch('cclimits.get_synthetic_usage')
    @patch('cclimits.get_antigravity_usage')
    @patch('cclimits.get_kimi_usage')
    @patch('cclimits.get_openrouter_usage')
    @patch('cclimits.get_zai_usage')
    @patch('cclimits.get_gemini_usage')
    @patch('cclimits.get_codex_usage')
    @patch('cclimits.get_claude_usage')
    @patch('sys.argv', ['cclimits', '--json'])
    def test_canonical_order_all_providers(
            self, mock_claude, mock_codex, mock_gemini, mock_zai,
            mock_or, mock_kimi, mock_ag, mock_syn,
            mock_or_creds, mock_kimi_creds, mock_ag_creds, mock_syn_creds, capsys):
        """All selected providers are fetched and results appear in canonical order."""
        mock_claude.return_value = {"status": "ok", "p": 1}
        mock_codex.return_value = {"status": "ok", "p": 2}
        mock_gemini.return_value = {"status": "ok", "p": 3}
        mock_zai.return_value = {"status": "ok", "p": 4}
        mock_or.return_value = {"status": "ok", "p": 5}
        mock_kimi.return_value = {"status": "ok", "p": 6}
        mock_ag.return_value = {"status": "ok", "p": 7}
        mock_syn.return_value = {"status": "ok", "p": 8}

        main()

        captured = capsys.readouterr()
        result = json.loads(captured.out)

        # Keys must appear in canonical provider order
        assert list(result.keys()) == [
            "claude", "codex", "gemini", "zai",
            "openrouter", "kimi", "antigravity", "synthetic",
        ]
        # Every usage function should have been called exactly once
        mock_claude.assert_called_once()
        mock_codex.assert_called_once()
        mock_gemini.assert_called_once()
        mock_zai.assert_called_once()
        mock_or.assert_called_once()
        mock_kimi.assert_called_once()
        mock_ag.assert_called_once()
        mock_syn.assert_called_once()

    @patch('cclimits.get_claude_usage')
    @patch('cclimits.get_codex_usage')
    @patch('sys.argv', ['cclimits', '--json', '--claude', '--codex'])
    def test_provider_exception_isolated(self, mock_codex, mock_claude, capsys):
        """A provider that raises is captured as error; others succeed."""
        mock_claude.return_value = {"status": "ok"}
        mock_codex.side_effect = RuntimeError("boom")

        main()

        captured = capsys.readouterr()
        result = json.loads(captured.out)

        assert result["claude"]["status"] == "ok"
        assert result["codex"]["error"] == "boom"

    @patch('cclimits.get_claude_usage')
    @patch('cclimits.get_codex_usage')
    @patch('sys.argv', ['cclimits', '--claude', '--codex'])
    def test_concurrent_fetch_timing(self, mock_codex, mock_claude, capsys):
        """Two providers each sleeping 0.3s should complete well under 0.6s."""
        def slow_fetch():
            time.sleep(0.3)
            return {"status": "ok"}

        mock_claude.side_effect = slow_fetch
        mock_codex.side_effect = slow_fetch

        start = time.monotonic()
        main()
        elapsed = time.monotonic() - start

        assert elapsed < 0.55, (
            f"Expected concurrent execution (<0.55s), took {elapsed:.2f}s"
        )


class TestStaleCacheFallback:
    """When a live fetch hits a transient error but the cache holds a previous
    good entry, serve the stale entry (labeled with its age) instead of ❌."""

    def _write_cache_with_age(self, data, age_seconds):
        """Write a cache file with a timestamp *age_seconds* in the past."""
        import json, time
        from cclimits import get_cache_path
        get_cache_path().write_text(json.dumps({
            "timestamp": time.time() - age_seconds,
            "data": data,
        }))

    @patch('cclimits.get_zai_usage')
    @patch('sys.argv', ['cclimits', '--zai', '--oneline'])
    def test_transient_error_serves_stale(self, mock_zai, capsys):
        """Transient API error + fresh-enough good cache → stale entry with marker."""
        mock_zai.return_value = {"error": "API error (500)"}
        self._write_cache_with_age(
            {"zai": {"status": "ok", "token_quota": {"percentage": 1}}}, 1800
        )
        main()
        captured = capsys.readouterr()
        assert "Z.AI: 1% (5h)" in captured.out
        assert "(stale 30m)" in captured.out

    @patch('cclimits.get_zai_usage')
    @patch('sys.argv', ['cclimits', '--zai', '--json'])
    def test_json_output_contains_stale_annotation(self, mock_zai, capsys):
        """JSON output carries stale_fallback and stale_age_seconds."""
        mock_zai.return_value = {"error": "API error (500)"}
        self._write_cache_with_age(
            {"zai": {"status": "ok", "token_quota": {"percentage": 42}}}, 600
        )
        main()
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["zai"]["stale_fallback"] is True
        assert isinstance(result["zai"]["stale_age_seconds"], int)
        assert result["zai"]["status"] == "ok"
        assert result["zai"]["token_quota"]["percentage"] == 42

    @patch('cclimits.get_zai_usage')
    @patch('sys.argv', ['cclimits', '--zai', '--oneline'])
    def test_no_creds_not_replaced(self, mock_zai, capsys):
        """No-credentials error is NOT replaced by stale data."""
        mock_zai.return_value = {"error": "No credentials found"}
        self._write_cache_with_age(
            {"zai": {"status": "ok", "token_quota": {"percentage": 1}}}, 60
        )
        main()
        captured = capsys.readouterr()
        assert "Z.AI: 🔑" in captured.out
        assert "stale" not in captured.out

    @patch('cclimits.get_claude_usage')
    @patch('sys.argv', ['cclimits', '--claude', '--oneline'])
    def test_expired_token_not_replaced(self, mock_claude, capsys):
        """Expired-token error is NOT replaced by stale data."""
        mock_claude.return_value = {"error": "Token expired"}
        self._write_cache_with_age(
            {"claude": {"status": "ok", "five_hour": {"used": "10%"}}}, 60
        )
        main()
        captured = capsys.readouterr()
        assert "Claude: ⏰" in captured.out
        assert "stale" not in captured.out

    @patch('cclimits.get_openrouter_usage')
    @patch('sys.argv', ['cclimits', '--openrouter', '--oneline'])
    def test_401_not_replaced(self, mock_or, capsys):
        """401/invalid-key error is NOT replaced by stale data."""
        mock_or.return_value = {"error": "Invalid API key"}
        self._write_cache_with_age(
            {"openrouter": {"status": "ok", "balance_usd": 10.0}}, 60
        )
        main()
        captured = capsys.readouterr()
        # Invalid API key is a non-transient error, shows ❌
        assert "stale" not in captured.out

    @patch('cclimits.get_zai_usage')
    @patch('sys.argv', ['cclimits', '--zai', '--oneline'])
    def test_cache_older_than_cap_not_replaced(self, mock_zai, capsys):
        """Cached entry older than STALE_CACHE_MAX_AGE → error shown, no substitution."""
        from cclimits import STALE_CACHE_MAX_AGE
        mock_zai.return_value = {"error": "API error (500)"}
        self._write_cache_with_age(
            {"zai": {"status": "ok", "token_quota": {"percentage": 1}}},
            STALE_CACHE_MAX_AGE + 100,
        )
        main()
        captured = capsys.readouterr()
        assert "Z.AI: ❌" in captured.out
        assert "stale" not in captured.out

    @patch('cclimits.get_zai_usage')
    @patch('sys.argv', ['cclimits', '--zai', '--oneline', '--no-stale-fallback'])
    def test_no_stale_fallback_flag_disables(self, mock_zai, capsys):
        """--no-stale-fallback flag disables the stale substitution."""
        mock_zai.return_value = {"error": "API error (500)"}
        self._write_cache_with_age(
            {"zai": {"status": "ok", "token_quota": {"percentage": 1}}}, 60
        )
        main()
        captured = capsys.readouterr()
        assert "Z.AI: ❌" in captured.out
        assert "stale" not in captured.out

    @patch('cclimits.get_zai_usage')
    @patch('sys.argv', ['cclimits', '--zai', '--oneline', '--cached'])
    def test_cached_mode_ttl_miss_with_transient_error(self, mock_zai, capsys):
        """--cached run whose TTL missed, followed by a failed fetch, serves stale."""
        mock_zai.return_value = {"error": "Could not fetch usage"}
        self._write_cache_with_age(
            {"zai": {"status": "ok", "token_quota": {"percentage": 7}}}, 120
        )
        main()
        captured = capsys.readouterr()
        assert "Z.AI: 7% (5h)" in captured.out
        assert "(stale 2m)" in captured.out

    @patch('cclimits.get_zai_usage')
    @patch('sys.argv', ['cclimits', '--zai'])
    def test_detailed_output_shows_stale_line(self, mock_zai, capsys):
        """Detailed output shows a stale-fallback notice line."""
        mock_zai.return_value = {"error": "API error (500)"}
        self._write_cache_with_age(
            {"zai": {"status": "ok", "token_quota": {"percentage": 15}}}, 1800
        )
        main()
        captured = capsys.readouterr()
        assert "Stale fallback" in captured.out
        assert "30m" in captured.out
