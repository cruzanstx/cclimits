"""
Shared fixtures and mock data for cclimits tests.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
import pytest

# Add lib directory to path so we can import cclimits
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
import cclimits


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """Keep CLI tests from reading or writing the user's real cclimits cache."""
    cache_dir = tmp_path / "cclimits-cache"
    monkeypatch.setattr(cclimits, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(cclimits, "CACHE_FILE", cache_dir / "usage.json")


@pytest.fixture(autouse=True)
def no_ambient_native_codex(monkeypatch):
    """Keep existing Codex HTTP-fallback tests deterministic on developer
    machines that happen to have the Codex CLI installed and authenticated.
    Native app-server behavior has dedicated tests that override this stub.
    """
    monkeypatch.setattr(cclimits, "get_native_codex_usage", lambda: None)


@pytest.fixture(autouse=True)
def no_ambient_copilot_creds(monkeypatch):
    """GITHUB_TOKEN is commonly exported (and gh CLI config commonly present),
    which would make every check-all test hit the live Copilot endpoint.
    Default to no Copilot credentials; Copilot tests patch
    get_copilot_credentials / get_copilot_usage explicitly, and the
    credential-discovery tests call the directly imported function, which
    this module-attribute patch does not affect."""
    monkeypatch.setattr(cclimits, "get_copilot_credentials", lambda: None)


@pytest.fixture
def sample_claude_usage_response():
    """Mock Claude API usage response."""
    return {
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
    }


@pytest.fixture
def sample_claude_expired_response():
    """Mock Claude API response for expired token."""
    return {"error": "Unauthorized"}


@pytest.fixture
def sample_codex_usage_response():
    """Mock Codex/ChatGPT API usage response."""
    return {
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
    }


@pytest.fixture
def sample_gemini_usage_response():
    """Mock Gemini Cloud Code Assist API usage response."""
    return {
        "currentTier": {
            "name": "Free",
            "id": "FREE"
        },
        "cloudaicompanionProject": "my-test-project"
    }


@pytest.fixture
def sample_gemini_quota_response():
    """Mock Gemini quota response."""
    return {
        "buckets": [
            {
                "modelId": "gemini-2.5-flash",
                "remainingFraction": 0.65,
                "resetTime": "2025-01-03T12:00:00Z"
            },
            {
                "modelId": "gemini-2.5-pro",
                "remainingFraction": 0.40,
                "resetTime": "2025-01-03T12:00:00Z"
            }
        ]
    }


@pytest.fixture
def sample_zai_quota_response():
    """Mock Z.AI quota response."""
    return {
        "success": True,
        "data": {
            "limits": [
                {
                    "type": "TOKENS_LIMIT",
                    "usage": 10000000,
                    "currentValue": 3500000,
                    "remaining": 6500000,
                    "percentage": 35.0,
                    "nextResetTime": 1704355200000  # Timestamp in ms
                },
                {
                    "type": "TIME_LIMIT",
                    "usage": 1000,
                    "currentValue": 250,
                    "remaining": 750
                }
            ]
        }
    }


@pytest.fixture
def sample_zai_usage_response():
    """Mock Z.AI historical usage response."""
    return {
        "success": True,
        "data": {
            "totalUsage": {
                "totalModelCallCount": 1523,
                "totalTokensUsage": 4500000
            }
        }
    }


@pytest.fixture
def mock_claude_token():
    """Mock Claude OAuth token."""
    return "sk-ant-test-token-12345"


@pytest.fixture
def mock_openai_credentials():
    """Mock OpenAI credentials."""
    return {
        "access_token": "test-openai-oauth-token",
        "account_id": "test-account-id",
        "api_key": "sk-test-openai-api-key"
    }


@pytest.fixture
def mock_gemini_credentials():
    """Mock Gemini OAuth credentials."""
    return {
        "access_token": "test-gemini-oauth-token",
        "refresh_token": "test-refresh-token",
        "expiry_date": str(int((datetime.now() + timedelta(hours=1)).timestamp() * 1000))
    }


@pytest.fixture
def mock_zai_api_key():
    """Mock Z.AI API key."""
    return "test-zai-api-key-12345"


@pytest.fixture
def mock_iso_times():
    """Various ISO timestamps for testing."""
    now = datetime.now()
    return {
        "future_5h": (now + timedelta(hours=5, minutes=30)).isoformat() + "Z",
        "future_30m": (now + timedelta(minutes=30)).isoformat() + "Z",
        "past": (now - timedelta(hours=1)).isoformat() + "Z",
        "now": now.isoformat() + "Z",
        "invalid": "not-a-valid-timestamp",
        "none": None
    }


@pytest.fixture
def temp_credential_dir(tmp_path):
    """Create temporary directory for credential files."""
    return tmp_path / "credentials"


@pytest.fixture
def mock_requests_available():
    """Mock HAS_REQUESTS = True."""
    with patch('cclimits.HAS_REQUESTS', True):
        with patch('cclimits.requests') as mock_req:
            yield mock_req


@pytest.fixture
def mock_requests_unavailable():
    """Mock HAS_REQUESTS = False."""
    with patch('cclimits.HAS_REQUESTS', False):
        yield


@pytest.fixture
def mock_subprocess():
    """Mock subprocess module."""
    with patch('cclimits.subprocess') as mock_sub:
        yield mock_sub


@pytest.fixture
def sample_copilot_user_response():
    """Mock GitHub copilot_internal/user response (trimmed live capture).

    Reset date is far-future so resets_in always computes in tests."""
    return {
        "login": "octocat",
        "copilot_plan": "individual",
        "access_type_sku": "yearly_subscriber_quota",
        "chat_enabled": True,
        "quota_reset_date": "2099-09-01",
        "quota_reset_date_utc": "2099-09-01T00:00:00.000Z",
        "quota_snapshots": {
            "chat": {"unlimited": True, "percent_remaining": 100.0,
                     "entitlement": 0, "remaining": 0, "overage_count": 0},
            "completions": {"unlimited": True, "percent_remaining": 100.0,
                            "entitlement": 0, "remaining": 0, "overage_count": 0},
            "premium_interactions": {
                "unlimited": False,
                "percent_remaining": 80.0,
                "remaining": 240,
                "entitlement": 300,
                "overage_count": 0,
                "overage_permitted": False,
            },
        },
    }
