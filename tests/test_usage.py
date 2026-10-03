"""
Tests for API usage functions (mock both credentials and HTTP).
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock, call
import pytest
from cclimits import (
    get_claude_usage,
    get_codex_usage,
    get_copilot_usage,
    get_gemini_usage,
    get_antigravity_credentials,
    get_antigravity_usage,
    _normalize_antigravity_models,
    _earliest_antigravity_reset,
    get_zai_usage,
    zai_quota_rate,
    _is_transient_error,
    COPILOT_NO_SUB_ERROR,
    GEMINI_TIERS
)


class TestGetClaudeUsage:
    """Tests for get_claude_usage() function."""

    @patch('cclimits.get_claude_credentials')
    @patch('cclimits.http_get')
    def test_successful_usage(self, mock_get, mock_creds):
        """Test successful Claude usage retrieval."""
        mock_creds.return_value = "test-token"
        mock_get.return_value = (200, {
            "five_hour": {
                "utilization": 45.5,
                "resets_at": "2025-01-02T10:30:00Z"
            },
            "seven_day": {
                "utilization": 72.3,
                "resets_at": "2025-01-08T00:00:00Z"
            },
            "seven_day_opus": {
                "utilization": 30.0
            }
        })

        result = get_claude_usage()

        assert result["status"] == "ok"
        assert "45.5%" in result["five_hour"]["used"]
        assert "54.5%" in result["five_hour"]["remaining"]
        assert "72.3%" in result["seven_day"]["used"]
        assert "27.7%" in result["seven_day"]["remaining"]
        assert result["opus"]["used"] == "30.0%"

    @patch('cclimits.get_claude_credentials')
    @patch('cclimits.http_get')
    def test_expired_token(self, mock_get, mock_creds):
        """Test handling expired token."""
        mock_creds.return_value = "expired-token"
        mock_get.return_value = (401, "Unauthorized")

        result = get_claude_usage()

        assert result["error"] == "Token expired"
        assert "re-authenticate" in result["hint"]

    @patch('cclimits.get_claude_credentials')
    def test_no_credentials(self, mock_creds):
        """Test when no credentials are found without touching real local sessions."""
        mock_creds.return_value = None

        with patch('cclimits.get_claude_desktop_credentials', return_value=None), \
             patch('cclimits.get_claude_cached_usage', return_value=None), \
             patch('cclimits._claude_desktop_detected', return_value=False):
            result = get_claude_usage()

        assert result["error"] == "No credentials found"
        assert "No existing Claude Code" in result["hint"]

    @patch('cclimits.get_claude_credentials')
    @patch('cclimits.http_get')
    def test_http_error(self, mock_get, mock_creds):
        """Test HTTP error response."""
        mock_creds.return_value = "test-token"
        mock_get.return_value = (500, "Internal Server Error")

        result = get_claude_usage()

        assert result["error"] == "HTTP 500"
        assert "Internal Server Error" in result["details"][:50]

    @patch('cclimits.get_claude_credentials')
    @patch('cclimits.http_get')
    def test_partial_data(self, mock_get, mock_creds):
        """Test when only partial data is returned."""
        mock_creds.return_value = "test-token"
        mock_get.return_value = (200, {
            "five_hour": {
                "utilization": 50.0,
                "resets_at": "2025-01-02T10:00:00Z"
            }
            # Missing seven_day data
        })

        result = get_claude_usage()

        assert result["status"] == "ok"
        assert "five_hour" in result
        assert "seven_day" not in result


class TestGetCodexUsage:
    """Tests for get_codex_usage() function."""

    @patch('cclimits.get_openai_credentials')
    @patch('cclimits.http_get')
    def test_oauth_success(self, mock_get, mock_creds):
        """Test successful Codex usage via OAuth."""
        mock_creds.return_value = {
            "access_token": "test-oauth-token",
            "account_id": "test-account-id"
        }
        mock_get.return_value = (200, {
            "plan_type": "Plus",
            "rate_limit": {
                "primary_window": {
                    "used_percent": 35.0,
                    "limit_window_seconds": 18000,
                    "reset_after_seconds": 7200
                },
                "secondary_window": {
                    "used_percent": 68.5,
                    "limit_window_seconds": 604800,
                    "reset_after_seconds": 345600
                },
                "limit_reached": False
            },
            "code_review_rate_limit": {
                "primary_window": {
                    "used_percent": 15.0
                }
            }
        })

        result = get_codex_usage()

        assert result["status"] == "ok"
        assert result["auth"] == "OAuth (ChatGPT)"
        assert result["plan"] == "Plus"
        assert result["primary_window"]["used"] == "35.0%"
        assert result["secondary_window"]["used"] == "68.5%"
        assert result["code_review"]["used"] == "15.0%"

    @patch('cclimits.get_openai_credentials')
    @patch('cclimits.http_get')
    def test_weekly_only_in_primary_slot(self, mock_get, mock_creds):
        """Weekly-only accounts return the 7d window in the primary slot with
        secondary null (quotio#356) — it must classify as the 7d bucket, not
        be mislabeled 5h or dropped."""
        mock_creds.return_value = {
            "access_token": "test-oauth-token",
            "account_id": "test-account-id"
        }
        mock_get.return_value = (200, {
            "plan_type": "pro",
            "rate_limit": {
                "primary_window": {
                    "used_percent": 6,
                    "limit_window_seconds": 604800,
                    "reset_after_seconds": 555731
                },
                "secondary_window": None
            }
        })

        result = get_codex_usage()

        assert result["status"] == "ok"
        assert "primary_window" not in result
        assert result["secondary_window"]["used"] == "6%"
        assert result["secondary_window"]["window"] == "7d"

    @patch('cclimits.get_openai_credentials')
    @patch('cclimits.http_get')
    def test_windows_classified_by_duration_not_slot(self, mock_get, mock_creds):
        """Even if the API swaps slot order, each window is bucketed by its own
        limit_window_seconds (<=24h -> 5h, longer -> 7d)."""
        mock_creds.return_value = {
            "access_token": "test-oauth-token",
            "account_id": "test-account-id"
        }
        mock_get.return_value = (200, {
            "plan_type": "Plus",
            "rate_limit": {
                "primary_window": {
                    "used_percent": 68.5,
                    "limit_window_seconds": 604800,
                    "reset_after_seconds": 345600
                },
                "secondary_window": {
                    "used_percent": 35.0,
                    "limit_window_seconds": 18000,
                    "reset_after_seconds": 7200
                }
            }
        })

        result = get_codex_usage()

        assert result["primary_window"]["used"] == "35.0%"
        assert result["primary_window"]["window"] == "5h"
        assert result["secondary_window"]["used"] == "68.5%"
        assert result["secondary_window"]["window"] == "7d"

    @patch('cclimits.get_openai_credentials')
    @patch('cclimits.http_get')
    def test_api_key_validation(self, mock_get, mock_creds):
        """Test Codex usage with API key (no OAuth)."""
        mock_creds.return_value = {
            "api_key": "sk-test-api-key"
        }
        mock_get.return_value = (200, {"object": "list", "data": []})

        result = get_codex_usage()

        assert result["api_key_valid"] is True
        assert "API key valid but no subscription quota API" in result["note"]

    @patch('cclimits.get_openai_credentials')
    def test_no_credentials(self, mock_creds):
        """Test when no credentials are found."""
        mock_creds.return_value = {}

        result = get_codex_usage()

        assert result["error"] == "No credentials found"
        assert "codex login" in result["hint"]

    @patch('cclimits.get_openai_credentials')
    @patch('cclimits.http_get')
    def test_oauth_expired(self, mock_get, mock_creds):
        """Test expired OAuth token."""
        mock_creds.return_value = {
            "access_token": "expired-token",
            "account_id": "test-account-id"
        }
        mock_get.return_value = (401, "Unauthorized")

        result = get_codex_usage()

        assert result["token_status"] == "expired"
        assert "re-authenticate" in result["hint_refresh"]


class TestGetGeminiUsage:
    """Tests for get_gemini_usage() function."""

    @patch('cclimits.get_gemini_credentials')
    @patch('cclimits.http_post')
    @patch('cclimits.http_get')
    def test_oauth_success(self, mock_get, mock_post, mock_creds):
        """Test successful Gemini usage via OAuth."""
        mock_creds.return_value = {
            "access_token": "test-token",
            "expiry_date": "9999999999000"
        }
        # Mock multiple http_post calls and http_get calls
        mock_post.side_effect = [
            (200, {  # loadCodeAssist response
                "currentTier": {"name": "Free"},
                "cloudaicompanionProject": "test-project"
            }),
            (200, {  # retrieveUserQuota response
                "buckets": [
                    {
                        "modelId": "gemini-2.5-flash",
                        "remainingFraction": 0.65,
                        "resetTime": "2025-01-03T12:00:00Z"
                    }
                ]
            })
        ]
        mock_get.return_value = (200, {"ok": True})

        result = get_gemini_usage()

        assert result["status"] == "ok"
        assert result["auth"] == "OAuth (Google Account)"
        assert result["tier"] == "Free"
        assert "models" in result
        assert "gemini-2.5-flash" in result["models"]

    @patch('cclimits.get_gemini_credentials')
    @patch('cclimits.http_get')
    def test_api_key_user(self, mock_get, mock_creds):
        """Test Gemini usage with API key."""
        mock_creds.return_value = {
            "api_key": "test-api-key"
        }
        mock_get.return_value = (200, {
            "id": "123456",
            "email": "test@example.com"
        })

        result = get_gemini_usage()

        assert result["auth"] == "API Key"
        assert "aistudio.google.com" in result["hint"]

    @patch('cclimits.get_gemini_credentials')
    def test_no_credentials(self, mock_creds):
        """Test when no Gemini credentials are found."""
        mock_creds.return_value = None

        result = get_gemini_usage()

        assert result["error"] == "No credentials found"
        assert "GEMINI_API_KEY" in result["hint"]


class TestGetAntigravityUsage:
    """Tests for Antigravity usage retrieval."""

    def test_normalize_models_sorts_by_remaining_quota(self):
        """Test Antigravity model normalization and tightest-first sorting."""
        result = _normalize_antigravity_models({
            "models": {
                "gemini-3-pro": {"quotaInfo": {"remainingFraction": 0.92, "resetTime": "2026-05-30T18:00:00Z"}},
                "claude-opus-4-5-thinking": {"quotaInfo": {"remainingFraction": 0.65, "resetTime": "2026-05-30T17:00:00Z"}},
            }
        })

        assert result[0]["name"] == "claude-opus-4-5-thinking"
        assert result[0]["remaining_pct"] == 65
        assert result[1]["remaining_pct"] == 92

    @patch('cclimits.get_antigravity_credentials')
    @patch('cclimits.http_post')
    def test_successful_usage(self, mock_post, mock_creds):
        """Test successful Antigravity two-step API flow."""
        mock_creds.return_value = {"access_token": "test-token", "source": "env"}
        mock_post.side_effect = [
            (200, {
                "cloudaicompanionProject": {"id": "test-project"},
                "currentTier": {"id": "free"},
            }),
            (200, {
                "models": {
                    "gemini-3-pro": {"quotaInfo": {"remainingFraction": 0.92, "resetTime": "2026-05-30T18:00:00Z"}},
                    "claude-sonnet-4-6": {"quotaInfo": {"remainingFraction": 0.71, "resetTime": "2026-05-30T18:00:00Z"}},
                }
            }),
            (200, {
                "groups": [
                    {"displayName": "Gemini Models", "description": "Gemini Flash, Gemini Pro",
                     "buckets": [
                         {"bucketId": "gemini-weekly", "displayName": "Weekly Limit Remaining", "window": "weekly",
                          "remainingFraction": 0.99, "resetTime": "2026-05-30T18:00:00Z"},
                         {"bucketId": "gemini-5h", "displayName": "Five Hour Limit Remaining", "window": "5h",
                          "remainingFraction": 0.98, "resetTime": "2026-05-30T17:00:00Z"},
                     ]},
                    {"displayName": "Claude and GPT models", "description": "Claude Opus, Claude Sonnet, GPT-OSS",
                     "buckets": [
                         {"bucketId": "3p-weekly", "window": "weekly", "remainingFraction": 0.22, "resetTime": "2026-05-30T16:00:00Z"},
                         {"bucketId": "3p-5h", "window": "5h", "remainingFraction": 1.0, "resetTime": "2026-05-30T17:00:00Z"},
                     ]},
                ]
            }),
        ]

        result = get_antigravity_usage()

        assert result["status"] == "ok"
        assert result["project_id"] == "test-project"
        assert result["subscription_tier"] == "free"
        assert result["summary"] == {
            "model_count": 2,
            "min_remaining_pct": 71,
            "avg_remaining_pct": 82,
            "next_reset_in": "Now",  # mock resetTime is in the past
        }
        assert result["models"][0]["name"] == "claude-sonnet-4-6"
        assert [g["short_name"] for g in result["quota_groups"]] == ["Gemini", "Claude/GPT"]
        gemini = result["quota_groups"][0]["buckets"]
        assert gemini["weekly"]["used_pct"] == 1.0
        assert gemini["5h"]["used_pct"] == 2.0
        claude = result["quota_groups"][1]["buckets"]
        assert claude["weekly"]["used_pct"] == 78.0
        assert claude["weekly"]["remaining_pct"] == 22.0
        assert claude["5h"]["used_pct"] == 0.0

    @patch('cclimits.get_antigravity_credentials')
    @patch('cclimits.http_post')
    def test_quota_summary_failure_degrades_to_per_model(self, mock_post, mock_creds):
        """retrieveUserQuotaSummary outage must not break the per-model result."""
        mock_creds.return_value = {"access_token": "test-token", "source": "env"}
        mock_post.side_effect = [
            (200, {"cloudaicompanionProject": {"id": "test-project"}}),
            (200, {"models": {"gemini-3-pro": {"quotaInfo": {"remainingFraction": 0.92}}}}),
            (403, {"error": "forbidden"}),
        ]

        result = get_antigravity_usage()

        assert result["status"] == "ok"
        assert "quota_groups" not in result
        assert "retrieveUserQuotaSummary returned 403" in result["quota_groups_error"]

    def test_earliest_reset_picks_soonest_and_skips_bad(self):
        """_earliest_antigravity_reset returns the soonest ISO time, ignoring empty/garbage."""
        earliest = _earliest_antigravity_reset([
            {"reset_time": "2026-05-30T18:00:00Z"},
            {"reset_time": "2026-05-30T17:00:00Z"},
            {"reset_time": ""},
            {"reset_time": "garbage"},
        ])
        assert earliest == "2026-05-30T17:00:00Z"
        assert _earliest_antigravity_reset([{"reset_time": ""}]) is None

    @patch('cclimits.get_antigravity_credentials')
    def test_no_credentials(self, mock_creds):
        """Test missing Antigravity credentials."""
        mock_creds.return_value = None

        result = get_antigravity_usage()

        assert result["error"] == "No credentials found"
        assert "ANTIGRAVITY_REFRESH_TOKEN" in result["hint"]

    def test_credentials_from_oauth_token_file(self, tmp_path, monkeypatch):
        """get_antigravity_credentials reads ~/.gemini/antigravity-cli/antigravity-oauth-token."""
        token_file = tmp_path / "antigravity-cli" / "antigravity-oauth-token"
        token_file.parent.mkdir(parents=True)
        token_file.write_text(json.dumps({
            "token": {
                "access_token": "ya29.test-access",
                "refresh_token": "1//test-refresh",
                "expiry": "2030-01-01T00:00:00Z",
            },
            "auth_method": "consumer",
        }))

        monkeypatch.delenv("ANTIGRAVITY_REFRESH_TOKEN", raising=False)
        monkeypatch.delenv("ANTIGRAVITY_ACCESS_TOKEN", raising=False)
        monkeypatch.setattr(
            "cclimits.ANTIGRAVITY_TOKEN_PATHS",
            [token_file],
        )

        creds = get_antigravity_credentials()

        assert creds is not None
        assert creds["source"] == "file"
        assert creds["access_token"] == "ya29.test-access"
        assert creds["refresh_token"] == "1//test-refresh"


class TestGetZaiUsage:
    """Tests for get_zai_usage() function."""

    @patch('cclimits.get_zai_credentials')
    @patch('cclimits.http_get')
    def test_successful_usage(self, mock_get, mock_creds):
        """Test successful Z.AI usage retrieval."""
        mock_creds.return_value = "test-api-key"
        
        # Mock quota endpoint response
        def get_side_effect(url, headers, **kwargs):
            if "quota/limit" in url:
                return (200, {
                    "success": True,
                    "data": {
                        "limits": [
                            {
                                "type": "TOKENS_LIMIT",
                                "usage": 10000000,
                                "currentValue": 3500000,
                                "remaining": 6500000,
                                "percentage": 35.0,
                                "nextResetTime": 1704355200000
                            },
                            {
                                "type": "TIME_LIMIT",
                                "usage": 1000,
                                "currentValue": 250,
                                "remaining": 750
                            }
                        ]
                    }
                })
            elif "model-usage" in url:
                return (200, {
                    "success": True,
                    "data": {
                        "totalUsage": {
                            "totalModelCallCount": 1523,
                            "totalTokensUsage": 4500000
                        }
                    }
                })
            return (404, {})
        
        mock_get.side_effect = get_side_effect

        result = get_zai_usage()

        assert result["status"] == "ok"
        assert result["token_quota"]["used"] == 3500000
        assert result["token_quota"]["percentage"] == 35.0

    @patch('cclimits.get_zai_credentials')
    def test_no_credentials(self, mock_creds):
        """Test when no Z.AI credentials are found."""
        mock_creds.return_value = None

        result = get_zai_usage()

        assert result["error"] == "No credentials found"
        assert "ZAI_API_KEY" in result["hint"]
        assert "billing" in result["dashboard"]


class TestGeminiTiers:
    """Tests for GEMINI_TIERS constant."""

    def test_tiers_structure(self):
        """Test that GEMINI_TIERS has correct structure."""
        assert "3-Flash" in GEMINI_TIERS
        assert "Flash" in GEMINI_TIERS
        assert "Pro" in GEMINI_TIERS

    def test_flash_tier_models(self):
        """Test Flash tier model IDs."""
        flash_models = GEMINI_TIERS["Flash"]
        assert "gemini-2.5-flash" in flash_models
        assert "gemini-2.5-flash-lite" in flash_models
        assert "gemini-2.0-flash" in flash_models

    def test_pro_tier_models(self):
        """Test Pro tier model IDs."""
        pro_models = GEMINI_TIERS["Pro"]
        assert "gemini-2.5-pro" in pro_models
        assert "gemini-3-pro-preview" in pro_models

    def test_3_flash_tier_models(self):
        """Test 3-Flash tier model IDs."""
        flash3_models = GEMINI_TIERS["3-Flash"]
        assert "gemini-3-flash-preview" in flash3_models


class TestZaiQuotaRate:
    """Peak is Mon-Fri 06:00-10:00 UTC (14:00-18:00 UTC+8); weekends off-peak all day.

    2026-07-24 is a Friday, 2026-07-25 a Saturday, 2026-07-27 a Monday.
    """

    def test_peak_hours(self):
        from datetime import datetime, timezone
        rate = zai_quota_rate(datetime(2026, 7, 24, 7, 30, tzinfo=timezone.utc))
        assert rate["peak"] is True
        assert rate["multiplier"] == "3x"
        assert rate["changes_in"] == "2h 30m"

    def test_offpeak_friday_afternoon_skips_weekend(self):
        from datetime import datetime, timezone
        rate = zai_quota_rate(datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc))
        assert rate["peak"] is False
        assert rate["multiplier"] == "1x"
        assert rate["changes_in"] == "66h 0m"  # Monday 06:00 UTC

    def test_saturday_inside_window_hours_is_offpeak(self):
        from datetime import datetime, timezone
        rate = zai_quota_rate(datetime(2026, 7, 25, 7, 0, tzinfo=timezone.utc))
        assert rate["peak"] is False
        assert rate["multiplier"] == "1x"
        assert rate["changes_in"] == "47h 0m"  # Monday 06:00 UTC

    def test_boundaries(self):
        from datetime import datetime, timezone
        assert zai_quota_rate(datetime(2026, 7, 24, 6, 0, tzinfo=timezone.utc))["peak"] is True
        assert zai_quota_rate(datetime(2026, 7, 24, 10, 0, tzinfo=timezone.utc))["peak"] is False
        assert zai_quota_rate(datetime(2026, 7, 24, 5, 59, tzinfo=timezone.utc))["peak"] is False
        assert zai_quota_rate(datetime(2026, 7, 26, 7, 0, tzinfo=timezone.utc))["peak"] is False  # Sunday


class TestZaiSparseQuota:
    """Z.AI TOKENS_LIMIT often has only percentage + nextResetTime — no fake zeros."""

    @patch('cclimits.get_zai_credentials')
    @patch('cclimits.http_get')
    def test_percentage_only_omits_counts(self, mock_get, mock_creds):
        mock_creds.return_value = "test-api-key"

        def get_side_effect(url, headers, **kwargs):
            if "quota/limit" in url:
                return (200, {
                    "success": True,
                    "data": {
                        "level": "max",
                        "limits": [
                            {"type": "TOKENS_LIMIT", "percentage": 1, "nextResetTime": 9999999999999},
                            {"type": "TIME_LIMIT", "usage": 4000, "currentValue": 0, "remaining": 4000},
                        ]
                    }
                })
            return (500, {})

        mock_get.side_effect = get_side_effect
        result = get_zai_usage()

        assert result["status"] == "ok"
        assert result["plan"] == "max"
        assert result["token_quota"]["percentage"] == 1
        for absent in ("limit", "used", "remaining"):
            assert absent not in result["token_quota"]
        assert result["mcp_quota"] == {"limit": 4000, "used": 0, "remaining": 4000}
        assert result["quota_rate"]["multiplier"] in ("3x", "1x")

    @patch('cclimits.get_zai_credentials')
    @patch('cclimits.http_get')
    def test_all_endpoints_down_reports_error(self, mock_get, mock_creds):
        """Network/API failure must surface as an explicit error, not a silent empty dict."""
        mock_creds.return_value = "test-api-key"
        mock_get.return_value = (0, None)

        result = get_zai_usage()

        assert result["error"] == "Could not fetch usage"
        assert "status" not in result


class TestGetCopilotUsage:
    """Tests for get_copilot_usage() function."""

    CREDS = {"token": "gho_test", "source": "$GITHUB_TOKEN"}

    @patch('cclimits.get_copilot_credentials')
    @patch('cclimits.http_get')
    def test_successful_usage(self, mock_get, mock_creds, sample_copilot_user_response):
        """Full parse of a good copilot_internal/user response."""
        mock_creds.return_value = dict(self.CREDS)
        mock_get.return_value = (200, sample_copilot_user_response)

        result = get_copilot_usage()

        assert result["status"] == "ok"
        assert result["account"] == "octocat"
        assert result["plan"] == "individual"
        assert result["auth"] == "$GITHUB_TOKEN"
        pr = result["premium_requests"]
        assert pr["used"] == 60
        assert pr["entitlement"] == 300
        assert pr["remaining"] == 240
        assert pr["percentage"] == 20
        assert pr["reset_date"] == "2099-09-01"
        assert "resets_in" in pr  # 2099 reset date is always in the future
        assert result["unlimited_buckets"] == ["chat", "completions"]
        url, headers = mock_get.call_args[0]
        assert url == "https://api.github.com/copilot_internal/user"
        assert headers["Authorization"] == "Bearer gho_test"

    @patch('cclimits.get_copilot_credentials')
    @patch('cclimits.http_get')
    def test_unlimited_premium(self, mock_get, mock_creds, sample_copilot_user_response):
        """Unlimited premium bucket (some Business/Enterprise setups)."""
        sample_copilot_user_response["quota_snapshots"]["premium_interactions"]["unlimited"] = True
        mock_creds.return_value = dict(self.CREDS)
        mock_get.return_value = (200, sample_copilot_user_response)

        result = get_copilot_usage()

        assert result["premium_requests"]["unlimited"] is True
        assert "percentage" not in result["premium_requests"]

    @patch('cclimits.get_copilot_credentials')
    @patch('cclimits.http_get')
    def test_no_subscription_404(self, mock_get, mock_creds):
        mock_creds.return_value = dict(self.CREDS)
        mock_get.return_value = (404, "Not Found")

        result = get_copilot_usage()

        assert result["error"] == COPILOT_NO_SUB_ERROR
        assert "status" not in result

    @patch('cclimits.get_copilot_credentials')
    @patch('cclimits.http_get')
    def test_forbidden_403_treated_as_no_subscription(self, mock_get, mock_creds):
        """403 = token type not accepted for this endpoint — same permanent state."""
        mock_creds.return_value = dict(self.CREDS)
        mock_get.return_value = (403, "access to this endpoint is forbidden")

        result = get_copilot_usage()

        assert result["error"] == COPILOT_NO_SUB_ERROR

    @patch('cclimits.get_copilot_credentials')
    @patch('cclimits.http_get')
    def test_invalid_token_401(self, mock_get, mock_creds):
        mock_creds.return_value = dict(self.CREDS)
        mock_get.return_value = (401, "Bad credentials")

        result = get_copilot_usage()

        assert result["error"] == "Invalid API key"

    @patch('cclimits.get_copilot_credentials')
    def test_no_credentials(self, mock_creds):
        mock_creds.return_value = None

        result = get_copilot_usage()

        assert result["error"] == "No credentials found"
        assert "GITHUB_TOKEN" in result["hint"]

    @patch('cclimits.get_copilot_credentials')
    @patch('cclimits.http_get')
    def test_missing_snapshots_still_ok(self, mock_get, mock_creds):
        """A 200 without quota_snapshots (unexpected shape) must not crash."""
        mock_creds.return_value = dict(self.CREDS)
        mock_get.return_value = (200, {"login": "octocat", "copilot_plan": "business"})

        result = get_copilot_usage()

        assert result["status"] == "ok"
        assert "premium_requests" not in result

    def test_no_sub_error_is_not_transient(self):
        """No-subscription is a permanent config state — stale-cache fallback must not mask it."""
        assert _is_transient_error({"error": COPILOT_NO_SUB_ERROR}) is False
