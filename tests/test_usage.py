"""
Tests for API usage functions (mock both credentials and HTTP).
"""

from unittest.mock import patch, MagicMock, call
import pytest
from cclimits import (
    get_claude_usage,
    get_codex_usage,
    get_gemini_usage,
    get_zai_usage,
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
        """Test when no credentials are found."""
        mock_creds.return_value = None

        result = get_claude_usage()

        assert result["error"] == "No credentials found"
        assert "authenticate first" in result["hint"]

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
