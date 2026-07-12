#!/usr/bin/env python3
"""
AI CLI Usage Checker
Fetches remaining quota/usage for Claude Code, Codex, Gemini, Z.AI, OpenRouter,
Kimi, Google Antigravity, and Synthetic.new
"""

from __future__ import annotations
import json
import os
import subprocess
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

# Optional: use requests if available, fallback to urllib
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    requests = None
    HAS_REQUESTS = False

# Always import urllib modules for fallback
import urllib.request
import urllib.error
import urllib.parse




GEMINI_TIERS = {
    "3-Flash": ["gemini-3-flash-preview"],
    "Flash": ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"],
    "Pro": ["gemini-2.5-pro", "gemini-3-pro-preview"],
}

ANTIGRAVITY_CLIENT_ID = "1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com"
ANTIGRAVITY_CLIENT_SECRET = "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"
ANTIGRAVITY_ENDPOINTS = [
    "https://cloudcode-pa.googleapis.com",
    "https://daily-cloudcode-pa.sandbox.googleapis.com",
    "https://autopush-cloudcode-pa.sandbox.googleapis.com",
]
ANTIGRAVITY_TOKEN_PATHS = [
    Path.home() / ".gemini" / "antigravity-cli" / "antigravity-oauth-token",
    Path.home() / ".config" / "antigravity-cli" / "antigravity-oauth-token",
]

COLORS = {
    'green': '\033[32m',
    'yellow': '\033[33m',
    'red': '\033[31m',
    'bold_red': '\033[1;31m',
    'reset': '\033[0m'
}

# Cache configuration
CACHE_DIR = Path.home() / ".cache" / "cclimits"
CACHE_FILE = CACHE_DIR / "usage.json"
DEFAULT_CACHE_TTL = 60  # seconds

def get_cache_path() -> Path:
    """Get cache file path, creating directory if needed"""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError):
        pass  # Silently fail if we can't create directory
    return CACHE_FILE

def read_cache(ttl: int) -> tuple[dict, int] | None:
    """Read cache if fresh (younger than TTL seconds), return (data, age_seconds) or None"""
    try:
        cache_file = get_cache_path()
        if not cache_file.exists():
            return None

        with open(cache_file, 'r') as f:
            cache_data = json.load(f)

        # Check cache structure
        if not isinstance(cache_data, dict) or "timestamp" not in cache_data or "data" not in cache_data:
            return None

        # Check if cache is fresh
        import time
        cache_age = time.time() - cache_data["timestamp"]
        if cache_age < ttl:
            return cache_data["data"], int(cache_age)

        return None
    except (json.JSONDecodeError, KeyError, TypeError, OSError, PermissionError):
        return None

NO_CREDS_ERROR = "No credentials found"

def format_cache_age(seconds: int) -> str:
    """Format cache age compactly: 42s, 3m, 2h"""
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    return f"{seconds // 3600}h"

def merge_cache_data(old: dict, new: dict) -> dict:
    """Merge new results over previous cache, keeping earlier good entries
    for providers this run couldn't check (missing credentials in this
    environment shouldn't erase data cached from an environment that has them)."""
    merged = dict(old) if isinstance(old, dict) else {}
    for key, value in new.items():
        prev = merged.get(key)
        if (isinstance(value, dict) and value.get("error") == NO_CREDS_ERROR
                and isinstance(prev, dict) and prev.get("error") != NO_CREDS_ERROR):
            continue
        merged[key] = value
    return merged

def write_cache(data: dict) -> bool:
    """Write data to cache file, return success status"""
    try:
        cache_file = get_cache_path()
        import time
        old_data = {}
        try:
            with open(cache_file, 'r') as f:
                old_data = json.load(f).get("data") or {}
        except (json.JSONDecodeError, KeyError, TypeError, OSError, PermissionError, AttributeError):
            old_data = {}
        cache_data = {
            "timestamp": time.time(),
            "data": merge_cache_data(old_data, data)
        }
        # Atomic write: concurrent runs (cron/statusline vs interactive) must
        # never see a half-written cache file
        tmp_file = cache_file.with_suffix(".json.tmp")
        with open(tmp_file, 'w') as f:
            json.dump(cache_data, f, indent=2)
        os.replace(tmp_file, cache_file)
        return True
    except (OSError, PermissionError, TypeError):
        return False


### OpenRouter Functions

def get_openrouter_credentials() -> str | None:
    """Get OpenRouter API key from environment variables"""
    for var in ["OPENROUTER_API_KEY", "OPENROUTER_KEY"]:
        if key := os.environ.get(var):
            return key
    return None


def get_openrouter_usage() -> dict:
    """Fetch OpenRouter account balance/credits"""
    key = get_openrouter_credentials()
    if not key:
        return {
            "error": "No credentials found",
            "hint": "Set OPENROUTER_API_KEY environment variable"
        }

    headers = {"Authorization": f"Bearer {key}"}
    status, data = http_get("https://openrouter.ai/api/v1/credits", headers)

    if status == 200 and isinstance(data, dict) and "data" in data:
        credits_data = data["data"]
        total_credits = float(credits_data.get("total_credits", 0))
        total_usage = float(credits_data.get("total_usage", 0))
        balance = total_credits - total_usage

        result = {
            "status": "ok",
            "balance_usd": balance,
            "total_credits_usd": total_credits,
            "total_usage_usd": total_usage,
            "dashboard_url": "https://openrouter.ai/credits"
        }
        return result
    elif status == 401:
        return {"error": "Invalid API key", "hint": "Check OPENROUTER_API_KEY"}
    elif status == 403:
        return {"error": "Forbidden", "hint": "Account may be suspended"}
    else:
        error_msg = data if isinstance(data, str) else str(data)
        return {"error": f"API error ({status})", "hint": error_msg}


def http_get(url: str, headers: dict) -> tuple[int, dict | str]:
    """Make HTTP GET request, return (status_code, response_data)"""
    if HAS_REQUESTS and requests is not None:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            try:
                return resp.status_code, resp.json()
            except:
                return resp.status_code, resp.text
        except Exception as e:
            return 0, f"Connection error: {e}"
    else:
        req = urllib.request.Request(url, headers=headers)
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            data = resp.read().decode('utf-8')
            try:
                return resp.status, json.loads(data)
            except:
                return resp.status, data
        except urllib.error.HTTPError as e:
            return e.code, e.reason
        except Exception as e:
            return 0, str(e)


def http_post(url: str, headers: dict, body: dict) -> tuple[int, dict | str]:
    """Make HTTP POST request, return (status_code, response_data)"""
    if HAS_REQUESTS and requests is not None:
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=10)
            try:
                return resp.status_code, resp.json()
            except:
                return resp.status_code, resp.text
        except Exception as e:
            return 0, f"Connection error: {e}"
    else:
        req = urllib.request.Request(
            url,
            headers=headers,
            data=json.dumps(body).encode('utf-8'),
            method='POST'
        )
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            data = resp.read().decode('utf-8')
            try:
                return resp.status, json.loads(data)
            except:
                return resp.status, data
        except urllib.error.HTTPError as e:
            return e.code, e.reason
        except Exception as e:
            return 0, str(e)


def format_reset_time(iso_time: str | None) -> str:
    """Format ISO timestamp to human-readable relative time"""
    if not iso_time:
        return "N/A"
    try:
        # Parse ISO format
        reset_dt = datetime.fromisoformat(iso_time.replace('Z', '+00:00'))
        now = datetime.now(reset_dt.tzinfo)
        delta = reset_dt - now

        if delta.total_seconds() < 0:
            return "Now"

        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes = remainder // 60

        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    except:
        return iso_time[:19] if iso_time else "N/A"


def get_claude_credentials() -> str | None:
    """Get Claude Code OAuth token from various sources"""

    # Method 1: macOS Keychain
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                creds = json.loads(result.stdout.strip())
                # Handle nested structure: claudeAiOauth.accessToken
                if "claudeAiOauth" in creds:
                    return creds["claudeAiOauth"].get("accessToken")
                return creds.get("accessToken")
        except:
            pass

    # Method 2: Linux credentials file (actual location)
    cred_paths = [
        Path.home() / ".claude" / ".credentials.json",  # Actual location
        Path.home() / ".claude" / "credentials.json",
        Path.home() / ".config" / "claude" / "credentials.json",
    ]
    for cred_path in cred_paths:
        if cred_path.exists():
            try:
                creds = json.loads(cred_path.read_text())
                # Handle nested structure: claudeAiOauth.accessToken
                if "claudeAiOauth" in creds:
                    return creds["claudeAiOauth"].get("accessToken")
                return creds.get("accessToken")
            except:
                pass

    # Method 3: Environment variable
    return os.environ.get("CLAUDE_ACCESS_TOKEN")


def get_claude_usage() -> dict:
    """Fetch Claude Code usage from Anthropic API"""
    token = get_claude_credentials()
    if not token:
        return {"error": "No credentials found", "hint": "Run 'claude' and authenticate first"}

    headers = {
        "Authorization": f"Bearer {token}",
        "anthropic-beta": "oauth-2025-04-20",
        "Content-Type": "application/json",
    }

    status, data = http_get("https://api.anthropic.com/api/oauth/usage", headers)

    if status == 200 and isinstance(data, dict):
        result: dict = {"status": "ok"}

        if "five_hour" in data and data["five_hour"]:
            result["five_hour"] = {
                "used": f"{data['five_hour'].get('utilization', 0):.1f}%",
                "remaining": f"{100 - data['five_hour'].get('utilization', 0):.1f}%",
                "resets_in": format_reset_time(data['five_hour'].get('resets_at')),
            }

        if "seven_day" in data and data["seven_day"]:
            result["seven_day"] = {
                "used": f"{data['seven_day'].get('utilization', 0):.1f}%",
                "remaining": f"{100 - data['seven_day'].get('utilization', 0):.1f}%",
                "resets_in": format_reset_time(data['seven_day'].get('resets_at')),
            }

        if "seven_day_opus" in data and data["seven_day_opus"]:
            result["opus"] = {
                "used": f"{data['seven_day_opus'].get('utilization', 0):.1f}%",
            }

        return result
    elif status == 401:
        return {"error": "Token expired", "hint": "Run 'claude' to re-authenticate"}
    else:
        return {"error": f"HTTP {status}", "details": str(data)[:200]}


def get_openai_credentials() -> dict:
    """Get OpenAI API key and OAuth token from environment or config"""
    result = {}

    # Environment variable
    if key := os.environ.get("OPENAI_API_KEY"):
        result["api_key"] = key

    # Codex auth file (actual location: ~/.codex/auth.json)
    auth_paths = [
        Path.home() / ".codex" / "auth.json",
        Path.home() / ".config" / "codex" / "auth.json",
    ]
    for auth_path in auth_paths:
        if auth_path.exists():
            try:
                auth = json.loads(auth_path.read_text())
                # Get API key if stored
                if "api_key" not in result and (key := auth.get("OPENAI_API_KEY")):
                    result["api_key"] = key
                # Get OAuth tokens and account ID
                if tokens := auth.get("tokens"):
                    if token := tokens.get("access_token"):
                        result["access_token"] = token
                    if account_id := tokens.get("account_id"):
                        result["account_id"] = account_id
            except:
                pass

    return result


def get_codex_usage() -> dict:
    """Fetch Codex usage via ChatGPT backend API"""
    creds = get_openai_credentials()

    if not creds.get("access_token") and not creds.get("api_key"):
        return {"error": "No credentials found", "hint": "Run 'codex login' or set OPENAI_API_KEY"}

    result = {}

    # Try the ChatGPT backend usage API (requires OAuth token + account ID)
    if creds.get("access_token") and creds.get("account_id"):
        headers = {
            "Authorization": f"Bearer {creds['access_token']}",
            "chatgpt-account-id": creds["account_id"],
            "User-Agent": "codex-cli",
            "Content-Type": "application/json",
        }

        status, data = http_get("https://chatgpt.com/backend-api/wham/usage", headers)

        if status == 200 and isinstance(data, dict):
            result["status"] = "ok"
            result["auth"] = "OAuth (ChatGPT)"

            # Plan type
            if plan := data.get("plan_type"):
                result["plan"] = plan

            # Primary rate limit (5-hour window)
            if rate_limit := data.get("rate_limit", {}):
                if primary := rate_limit.get("primary_window"):
                    window_hours = primary.get("limit_window_seconds", 18000) // 3600
                    result["primary_window"] = {
                        "used": f"{primary.get('used_percent', 0)}%",
                        "remaining": f"{100 - primary.get('used_percent', 0)}%",
                        "window": f"{window_hours}h",
                    }
                    # Calculate reset time
                    reset_secs = primary.get("reset_after_seconds", 0)
                    if reset_secs > 0:
                        hours, remainder = divmod(reset_secs, 3600)
                        minutes = remainder // 60
                        if hours > 0:
                            result["primary_window"]["resets_in"] = f"{hours}h {minutes}m"
                        else:
                            result["primary_window"]["resets_in"] = f"{minutes}m"

                # Secondary rate limit (7-day window)
                if secondary := rate_limit.get("secondary_window"):
                    window_days = secondary.get("limit_window_seconds", 604800) // 86400
                    result["secondary_window"] = {
                        "used": f"{secondary.get('used_percent', 0)}%",
                        "remaining": f"{100 - secondary.get('used_percent', 0)}%",
                        "window": f"{window_days}d",
                    }
                    reset_secs = secondary.get("reset_after_seconds", 0)
                    if reset_secs > 0:
                        days, remainder = divmod(reset_secs, 86400)
                        hours = remainder // 3600
                        if days > 0:
                            result["secondary_window"]["resets_in"] = f"{days}d {hours}h"
                        else:
                            result["secondary_window"]["resets_in"] = f"{hours}h"

                # Limit status
                if rate_limit.get("limit_reached"):
                    result["limit_reached"] = True

            # Code review quota (separate)
            if review_limit := data.get("code_review_rate_limit", {}):
                if review_primary := review_limit.get("primary_window"):
                    result["code_review"] = {
                        "used": f"{review_primary.get('used_percent', 0)}%",
                    }

            return result

        elif status == 401:
            result["token_status"] = "expired"
            result["hint_refresh"] = "Run 'codex login' to re-authenticate"

    # Fallback: Try basic API key validation
    if creds.get("api_key"):
        headers = {
            "Authorization": f"Bearer {creds['api_key']}",
            "Content-Type": "application/json",
        }
        status, data = http_get("https://api.openai.com/v1/models", headers)
        if status == 200:
            result["auth"] = result.get("auth", "API Key")
            result["api_key_valid"] = True
            result["note"] = "API key valid but no subscription quota API"
            result["hint"] = "Check usage at https://platform.openai.com/usage"
            return result

    if result:
        return result

    return {
        "error": "Authentication failed",
        "hint": "Run 'codex login' to re-authenticate"
    }


def _extract_oauth_from_file(path: Path) -> tuple[str, str] | None:
    """Extract CLIENT_ID and CLIENT_SECRET from oauth2.js file"""
    try:
        content = path.read_text()
        import re
        id_match = re.search(r'CLIENT_ID\s*=\s*["\']([^"\']+)["\']', content)
        secret_match = re.search(r'CLIENT_SECRET\s*=\s*["\']([^"\']+)["\']', content)
        if id_match and secret_match:
            return id_match.group(1), secret_match.group(1)
    except:
        pass
    return None


def get_gemini_oauth_creds() -> tuple[str, str] | None:
    """
    Get Gemini OAuth client credentials.
    These are public credentials for installed apps from the Gemini CLI.
    Source: @google/gemini-cli-core npm package
    """
    # Try environment variables first
    client_id = os.environ.get("GEMINI_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GEMINI_OAUTH_CLIENT_SECRET")
    if client_id and client_secret:
        return client_id, client_secret

    import glob

    # Method 1: Find via `which gemini` and resolve to installation
    try:
        proc = subprocess.run(
            ["which", "gemini"],
            capture_output=True, text=True, timeout=5
        )
        if proc.returncode == 0 and proc.stdout.strip():
            gemini_bin = Path(proc.stdout.strip())
            # Resolve symlinks to get actual installation path
            resolved = gemini_bin.resolve()
            # Navigate up to find node_modules, then down to oauth2.js
            # Typical structure: .../node_modules/@google/gemini-cli/bin/cli.js
            #                 or .../node_modules/.bin/gemini -> ../gemini-cli/...
            current = resolved.parent
            for _ in range(10):  # Walk up max 10 levels
                # Check if we're in a node_modules structure
                oauth_path = current / "node_modules" / "@google" / "gemini-cli-core" / "dist" / "src" / "code_assist" / "oauth2.js"
                if oauth_path.exists():
                    if result := _extract_oauth_from_file(oauth_path):
                        return result
                # Also check if gemini-cli has it nested
                oauth_path2 = current / "node_modules" / "@google" / "gemini-cli" / "node_modules" / "@google" / "gemini-cli-core" / "dist" / "src" / "code_assist" / "oauth2.js"
                if oauth_path2.exists():
                    if result := _extract_oauth_from_file(oauth_path2):
                        return result
                # Move up one directory
                parent = current.parent
                if parent == current:
                    break
                current = parent
    except:
        pass

    # Method 2: Use npm root -g to find global node_modules
    try:
        proc = subprocess.run(
            ["npm", "root", "-g"],
            capture_output=True, text=True, timeout=10
        )
        if proc.returncode == 0 and proc.stdout.strip():
            npm_global = Path(proc.stdout.strip())
            for oauth_path in [
                npm_global / "@google" / "gemini-cli-core" / "dist" / "src" / "code_assist" / "oauth2.js",
                npm_global / "@google" / "gemini-cli" / "node_modules" / "@google" / "gemini-cli-core" / "dist" / "src" / "code_assist" / "oauth2.js",
            ]:
                if oauth_path.exists():
                    if result := _extract_oauth_from_file(oauth_path):
                        return result
    except:
        pass

    # Method 3: Fallback to common paths with globs
    fallback_patterns = [
        # npx cache
        str(Path.home() / ".npm" / "_npx" / "*" / "node_modules" / "@google" / "gemini-cli-core" / "dist" / "src" / "code_assist" / "oauth2.js"),
        str(Path.home() / ".npm" / "_npx" / "*" / "node_modules" / "@google" / "gemini-cli" / "node_modules" / "@google" / "gemini-cli-core" / "dist" / "src" / "code_assist" / "oauth2.js"),
        # nvm
        str(Path.home() / ".nvm" / "versions" / "node" / "*" / "lib" / "node_modules" / "@google" / "gemini-cli" / "node_modules" / "@google" / "gemini-cli-core" / "dist" / "src" / "code_assist" / "oauth2.js"),
        str(Path.home() / ".nvm" / "versions" / "node" / "*" / "lib" / "node_modules" / "@google" / "gemini-cli-core" / "dist" / "src" / "code_assist" / "oauth2.js"),
        # Global installs
        "/usr/local/lib/node_modules/@google/gemini-cli/node_modules/@google/gemini-cli-core/dist/src/code_assist/oauth2.js",
        "/usr/local/lib/node_modules/@google/gemini-cli-core/dist/src/code_assist/oauth2.js",
        # Homebrew (macOS)
        "/opt/homebrew/lib/node_modules/@google/gemini-cli/node_modules/@google/gemini-cli-core/dist/src/code_assist/oauth2.js",
        # Yarn global
        str(Path.home() / ".config" / "yarn" / "global" / "node_modules" / "@google" / "gemini-cli-core" / "dist" / "src" / "code_assist" / "oauth2.js"),
        # pnpm global
        str(Path.home() / ".local" / "share" / "pnpm" / "global" / "*" / "node_modules" / "@google" / "gemini-cli-core" / "dist" / "src" / "code_assist" / "oauth2.js"),
    ]

    for pattern in fallback_patterns:
        for path in glob.glob(pattern):
            if result := _extract_oauth_from_file(Path(path)):
                return result

    return None


def refresh_gemini_token(refresh_token: str) -> dict | None:
    """Refresh Gemini OAuth token using refresh_token"""
    creds = get_gemini_oauth_creds()
    if not creds:
        return None

    client_id, client_secret = creds
    body = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    try:
        if requests is not None:
            resp = requests.post(
                "https://oauth2.googleapis.com/token",
                data=body,
                timeout=10
            )
            if resp.status_code == 200:
                return resp.json()
        else:
            data = urllib.parse.urlencode(body).encode('utf-8')
            req = urllib.request.Request(
                "https://oauth2.googleapis.com/token",
                data=data,
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode('utf-8'))
    except Exception:
        pass
    return None


def get_gemini_credentials() -> dict | None:
    """Get Gemini API key or OAuth token, auto-refreshing if expired"""
    result = {}
    oauth_path = None

    # API key from environment
    if key := os.environ.get("GEMINI_API_KEY"):
        result["api_key"] = key
    if key := os.environ.get("GOOGLE_API_KEY"):
        result["api_key"] = key

    # OAuth credentials from Gemini CLI (actual location: ~/.gemini/oauth_creds.json)
    oauth_paths = [
        Path.home() / ".gemini" / "oauth_creds.json",
        Path.home() / ".config" / "gemini" / "oauth_creds.json",
    ]
    for path in oauth_paths:
        if path.exists():
            oauth_path = path
            try:
                oauth = json.loads(path.read_text())
                if token := oauth.get("access_token"):
                    result["access_token"] = token
                if expiry := oauth.get("expiry_date"):
                    result["expiry_date"] = expiry
                if refresh := oauth.get("refresh_token"):
                    result["refresh_token"] = refresh
                result["oauth_path"] = path
            except:
                pass
            break

    # Auto-refresh if token is expired and we have a refresh_token
    if result.get("refresh_token") and result.get("expiry_date"):
        try:
            expiry_ts = int(result["expiry_date"]) / 1000  # Convert ms to seconds
            expiry_dt = datetime.fromtimestamp(expiry_ts)
            now = datetime.now()

            if now >= expiry_dt:
                # Token expired, try to refresh
                new_tokens = refresh_gemini_token(result["refresh_token"])
                if new_tokens and "access_token" in new_tokens:
                    result["access_token"] = new_tokens["access_token"]
                    result["token_refreshed"] = True

                    # Calculate new expiry (expires_in is in seconds)
                    expires_in = new_tokens.get("expires_in", 3600)
                    new_expiry_ms = int((now.timestamp() + expires_in) * 1000)
                    result["expiry_date"] = new_expiry_ms

                    # Save updated credentials to file
                    if oauth_path:
                        try:
                            # Read existing file to preserve all fields
                            oauth_data = json.loads(oauth_path.read_text())
                            oauth_data["access_token"] = new_tokens["access_token"]
                            oauth_data["expiry_date"] = new_expiry_ms
                            
                            # Atomic write pattern to avoid corruption
                            temp_path = oauth_path.with_suffix(".tmp")
                            temp_path.write_text(json.dumps(oauth_data, indent=2))
                            temp_path.rename(oauth_path)
                        except Exception as e:
                            # Log warning but continue - in-memory token still works
                            print(f"Warning: Could not save refreshed OAuth token: {e}")
                            pass
        except:
            pass

    # Check for gcloud auth
    try:
        proc = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True, text=True, timeout=5
        )
        if proc.returncode == 0 and proc.stdout.strip():
            result["gcp_project"] = proc.stdout.strip()
    except:
        pass

    return result if result else None


def get_gemini_usage() -> dict:
    """Fetch Gemini usage via Cloud Code Assist API"""
    creds = get_gemini_credentials()
    if not creds:
        return {
            "error": "No credentials found",
            "hint": "Set GEMINI_API_KEY or run 'gemini' to authenticate"
        }

    result = {}

    # Check if token was auto-refreshed
    if creds.get("token_refreshed"):
        result["token_refreshed"] = True

    # If we have OAuth token from Gemini CLI, use the Cloud Code Assist API
    if "access_token" in creds:
        token = creds["access_token"]
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # Check token expiry (field is "expiry_date" in ms)
        if expiry := creds.get("expiry_date"):
            try:
                expiry_ts = int(expiry) / 1000  # Convert ms to seconds
                expiry_dt = datetime.fromtimestamp(expiry_ts)
                now = datetime.now()
                if expiry_dt > now:
                    delta = expiry_dt - now
                    total_secs = int(delta.total_seconds())
                    hours, remainder = divmod(total_secs, 3600)
                    minutes = remainder // 60
                    if hours > 0:
                        result["token_expires_in"] = f"{hours}h {minutes}m"
                    else:
                        result["token_expires_in"] = f"{minutes}m"
                else:
                    result["token_status"] = "expired"
                    result["hint_refresh"] = "Run 'gemini' to refresh token"
                    return result
            except:
                pass

        # Step 1: Get project ID via loadCodeAssist API
        load_body = {
            "metadata": {
                "ideType": "IDE_UNSPECIFIED",
                "platform": "PLATFORM_UNSPECIFIED",
                "pluginType": "GEMINI"
            }
        }
        status, data = http_post(
            "https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist",
            headers,
            load_body
        )

        if status == 200 and isinstance(data, dict):
            result["auth"] = "OAuth (Google Account)"
            result["status"] = "ok"

            # Extract tier info
            if tier := data.get("currentTier", {}):
                result["tier"] = tier.get("name", tier.get("id", "unknown"))

            # Get project ID for quota lookup
            project_id = data.get("cloudaicompanionProject")

            if project_id:
                # Step 2: Get quota via retrieveUserQuota API
                quota_status, quota_data = http_post(
                    "https://cloudcode-pa.googleapis.com/v1internal:retrieveUserQuota",
                    headers,
                    {"project": project_id}
                )

                if quota_status == 200 and isinstance(quota_data, dict):
                    buckets = quota_data.get("buckets", [])
                    if buckets:
                        result["models"] = {}
                        for bucket in buckets:
                            model_id = bucket.get("modelId", "unknown")
                            remaining = bucket.get("remainingFraction", 0)
                            reset_time = bucket.get("resetTime")

                            # Convert to percentage used
                            used_pct = round((1 - remaining) * 100, 1)
                            remaining_pct = round(remaining * 100, 1)

                            result["models"][model_id] = {
                                "used": f"{used_pct}%",
                                "remaining": f"{remaining_pct}%",
                            }
                            if reset_time:
                                result["models"][model_id]["resets_in"] = format_reset_time(reset_time)

        elif status == 401:
            result["token_status"] = "expired"
            result["hint_refresh"] = "Run 'gemini' to refresh token"
        else:
            # Fallback: verify token with userinfo API
            status, data = http_get("https://www.googleapis.com/oauth2/v1/userinfo", headers)
            if status == 200 and isinstance(data, dict):
                result["auth"] = "OAuth (Google Account)"
                result["account"] = data.get("email", "authenticated")
                result["status"] = "authenticated"
                result["note"] = "Quota API failed, token may have limited scopes"
            elif status == 401:
                result["token_status"] = "expired"
                result["hint_refresh"] = "Run 'gemini' to refresh token"

    # Fallback info for API key users
    if "api_key" in creds and "auth" not in result:
        result["auth"] = "API Key"
        result["hint"] = "API key doesn't support quota API. Check https://aistudio.google.com"

    if result:
        if "status" not in result:
            result["status"] = "authenticated" if result.get("auth") else "unknown"
        return result

    return {
        "error": "Could not fetch usage",
        "hint": "Check https://aistudio.google.com for quota status"
    }


def get_zai_credentials() -> str | None:
    """Get Z.AI API key from environment"""
    # Check various env var names
    for var in ["ZAI_API_KEY", "ZAI_KEY", "ZHIPU_API_KEY", "ZHIPUAI_API_KEY"]:
        if key := os.environ.get(var):
            return key
    return None


def get_zai_usage() -> dict:
    """Fetch Z.AI usage from their monitor API"""
    api_key = get_zai_credentials()

    if not api_key:
        return {
            "error": "No credentials found",
            "hint": "Set ZAI_API_KEY environment variable",
            "dashboard": "https://z.ai/billing"
        }

    result = {}
    headers = {
        "Authorization": api_key,  # Without Bearer for api.z.ai endpoints
        "Content-Type": "application/json",
    }

    # Get quota limits (the key endpoint!)
    status, data = http_get("https://api.z.ai/api/monitor/usage/quota/limit", headers)
    if status == 200 and isinstance(data, dict) and data.get("success"):
        result["status"] = "ok"
        if plan := data.get("data", {}).get("level"):
            result["plan"] = plan
        limits = data.get("data", {}).get("limits", [])

        for limit in limits:
            limit_type = limit.get("type")
            if limit_type == "TOKENS_LIMIT":
                # The API often returns only percentage + nextResetTime here;
                # raw token counts appear only when the API provides them
                result["token_quota"] = {
                    "percentage": limit.get("percentage", 0),
                }
                for src, dst in (("usage", "limit"), ("currentValue", "used"), ("remaining", "remaining")):
                    if src in limit:
                        result["token_quota"][dst] = limit[src]

                # Parse reset time
                if reset_ts := limit.get("nextResetTime"):
                    try:
                        reset_dt = datetime.fromtimestamp(reset_ts / 1000)
                        now = datetime.now()
                        delta = reset_dt - now
                        if delta.total_seconds() > 0:
                            hours, remainder = divmod(int(delta.total_seconds()), 3600)
                            minutes = remainder // 60
                            result["token_quota"]["resets_in"] = f"{hours}h {minutes}m"
                    except:
                        pass

            elif limit_type == "TIME_LIMIT":
                total = limit.get("usage", 0)
                used = limit.get("currentValue", 0)
                remaining = limit.get("remaining", 0)

                result["request_quota"] = {
                    "limit": total,
                    "used": used,
                    "remaining": remaining,
                }

    # Get historical usage (last 7 days) for additional context
    now = datetime.now()
    start_date = (now - __import__("datetime").timedelta(days=7)).strftime("%Y-%m-%d+00:00:00")
    end_date = now.strftime("%Y-%m-%d+23:59:59")

    usage_url = f"https://api.z.ai/api/monitor/usage/model-usage?startTime={start_date}&endTime={end_date}"
    status, data = http_get(usage_url, headers)
    if status == 200 and isinstance(data, dict) and data.get("success"):
        usage_data = data.get("data", {})
        total = usage_data.get("totalUsage", {})

        if total:
            if "status" not in result:
                result["status"] = "ok"
            result["weekly_usage"] = {
                "calls": total.get("totalModelCallCount", 0),
                "tokens": total.get("totalTokensUsage", 0),
            }

    # Fallback: get user info if main APIs failed
    if "status" not in result:
        auth_headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        status, data = http_get("https://chat.z.ai/api/v1/auths/", auth_headers)
        if status == 200:
            result["status"] = "authenticated"
        else:
            result["error"] = "Could not fetch usage"

    # Add hints
    result["hint"] = "Dashboard: https://z.ai/manage-apikey/billing"

    return result


def get_kimi_credentials() -> str | None:
    """Get Kimi (Moonshot AI) API key from environment variables"""
    for var in ["MOONSHOT_API_KEY", "KIMI_API_KEY", "KIMI_KEY"]:
        if key := os.environ.get(var):
            return key
    return None


def get_kimi_usage() -> dict:
    """Fetch Kimi account balance"""
    key = get_kimi_credentials()
    if not key:
        return {
            "error": "No credentials found",
            "hint": "Set MOONSHOT_API_KEY environment variable"
        }

    headers = {"Authorization": f"Bearer {key}"}
    status, data = http_get("https://api.moonshot.ai/v1/users/me/balance", headers)

    if status == 200 and isinstance(data, dict):
        # Response format:
        # {
        #   "code": 0,
        #   "data": {
        #     "available_balance": 49.58894,
        #     "voucher_balance": 46.58893,
        #     "cash_balance": 3.00001
        #   },
        #   "status": true
        # }
        if data.get("status") is True and "data" in data:
            balance_data = data["data"]
            available = float(balance_data.get("available_balance", 0))
            cash = float(balance_data.get("cash_balance", 0))
            voucher = float(balance_data.get("voucher_balance", 0))

            return {
                "status": "ok",
                "balance": available,
                "cash_balance": cash,
                "voucher_balance": voucher,
                "currency": "USD",  # Documentation says USD
                "dashboard_url": "https://platform.moonshot.ai/console"
            }
        else:
            return {"error": "API returned error status", "details": str(data)}
    elif status == 401:
        return {"error": "Invalid API key", "hint": "Check MOONSHOT_API_KEY"}
    else:
        return {"error": f"API error ({status})", "details": str(data)}


def _read_antigravity_token_file() -> dict | None:
    """Read tokens from the Antigravity CLI's on-disk credentials file.

    File shape: {"token": {"access_token", "refresh_token", "expiry"}, "auth_method": "..."}
    where expiry is an RFC3339 timestamp written by the Go CLI.
    """
    for path in ANTIGRAVITY_TOKEN_PATHS:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
            tok = data.get("token") or {}
            if tok.get("refresh_token") or tok.get("access_token"):
                return {
                    "access_token": tok.get("access_token"),
                    "refresh_token": tok.get("refresh_token"),
                    "expiry": tok.get("expiry"),
                }
        except Exception:
            continue
    return None


def refresh_antigravity_token(refresh_token: str) -> dict | None:
    """Refresh Antigravity OAuth token using its public installed-app client."""
    body = {
        "client_id": ANTIGRAVITY_CLIENT_ID,
        "client_secret": ANTIGRAVITY_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    try:
        data = urllib.parse.urlencode(body).encode('utf-8')
        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=data,
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode('utf-8'))
    except Exception:
        pass
    return None


def get_antigravity_credentials() -> dict | None:
    """Get Antigravity OAuth tokens from the CLI's on-disk file or env vars."""
    result = {}

    if file_creds := _read_antigravity_token_file():
        if file_creds.get("refresh_token"):
            result["refresh_token"] = file_creds["refresh_token"]
        if file_creds.get("access_token"):
            result["access_token"] = file_creds["access_token"]
        if file_creds.get("expiry"):
            result["expiry"] = file_creds["expiry"]
        if result:
            result["source"] = "file"

    if not result:
        if refresh := os.environ.get("ANTIGRAVITY_REFRESH_TOKEN"):
            result["refresh_token"] = refresh
        if access := os.environ.get("ANTIGRAVITY_ACCESS_TOKEN"):
            result["access_token"] = access
        if result:
            result["source"] = "env"

    if result.get("refresh_token") and not result.get("access_token"):
        refreshed = refresh_antigravity_token(result["refresh_token"])
        if refreshed and refreshed.get("access_token"):
            result["access_token"] = refreshed["access_token"]
            result["token_refreshed"] = True

    return result or None


def _antigravity_headers(access_token: str, user_agent: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": user_agent,
    }


def _extract_antigravity_project(data: dict) -> str | None:
    project = data.get("cloudaicompanionProject")
    if isinstance(project, str):
        return project
    if isinstance(project, dict):
        if project_id := project.get("id"):
            return project_id
    return None


def _normalize_antigravity_models(data: dict) -> list[dict]:
    raw_models = data.get("models", {})
    models = []

    if isinstance(raw_models, dict):
        iterable = raw_models.items()
    elif isinstance(raw_models, list):
        iterable = ((model.get("name") or model.get("id"), model) for model in raw_models if isinstance(model, dict))
    else:
        iterable = []

    for name, model_data in iterable:
        if not name or not isinstance(model_data, dict):
            continue
        quota = model_data.get("quotaInfo", {})
        if not isinstance(quota, dict):
            quota = {}
        remaining_fraction = quota.get("remainingFraction")
        try:
            remaining_pct = int(round(float(remaining_fraction if remaining_fraction is not None else 0) * 100))
        except (TypeError, ValueError):
            remaining_pct = 0
        models.append({
            "name": name,
            "remaining_pct": max(0, min(100, remaining_pct)),
            "reset_time": quota.get("resetTime") or "",
        })

    return sorted(models, key=lambda item: (item["remaining_pct"], item["name"]))


def get_antigravity_usage() -> dict:
    """Fetch Antigravity per-model quota via Cloud Code Assist."""
    creds = get_antigravity_credentials()
    if not creds or not creds.get("access_token"):
        return {
            "error": "No credentials found",
            "hint": "Run 'antigravity auth login' or set ANTIGRAVITY_REFRESH_TOKEN"
        }

    access_token = creds["access_token"]
    refreshed_once = bool(creds.get("token_refreshed"))
    last_error = None

    for base_url in ANTIGRAVITY_ENDPOINTS:
        load_url = f"{base_url}/v1internal:loadCodeAssist"
        fetch_url = f"{base_url}/v1internal:fetchAvailableModels"

        load_headers = _antigravity_headers(access_token, "antigravity/windows/amd64")
        status, data = http_post(load_url, load_headers, {"metadata": {"ideType": "ANTIGRAVITY"}})
        if status == 401 and creds.get("refresh_token") and not refreshed_once:
            refreshed = refresh_antigravity_token(creds["refresh_token"])
            if refreshed and refreshed.get("access_token"):
                access_token = refreshed["access_token"]
                refreshed_once = True
                load_headers = _antigravity_headers(access_token, "antigravity/windows/amd64")
                status, data = http_post(load_url, load_headers, {"metadata": {"ideType": "ANTIGRAVITY"}})
        if status == 401:
            return {"error": "Authentication failed", "hint": "Run 'antigravity auth login' to refresh credentials"}
        if status < 200 or status >= 300 or not isinstance(data, dict):
            last_error = f"{base_url} loadCodeAssist returned {status}: {data}"
            continue

        project_id = _extract_antigravity_project(data)
        if not project_id:
            last_error = f"{base_url} did not return cloudaicompanionProject"
            continue

        tier = data.get("currentTier") or data.get("paidTier") or {}
        if isinstance(tier, dict):
            subscription_tier = tier.get("id") or "free"
        elif isinstance(tier, str):
            subscription_tier = tier
        else:
            subscription_tier = "free"

        fetch_headers = _antigravity_headers(access_token, "antigravity/1.11.5 windows/amd64")
        quota_status, quota_data = http_post(fetch_url, fetch_headers, {"project": project_id})
        if quota_status == 401 and creds.get("refresh_token") and not refreshed_once:
            refreshed = refresh_antigravity_token(creds["refresh_token"])
            if refreshed and refreshed.get("access_token"):
                access_token = refreshed["access_token"]
                refreshed_once = True
                fetch_headers = _antigravity_headers(access_token, "antigravity/1.11.5 windows/amd64")
                quota_status, quota_data = http_post(fetch_url, fetch_headers, {"project": project_id})
        if quota_status == 401:
            return {"error": "Authentication failed", "hint": "Run 'antigravity auth login' to refresh credentials"}
        if quota_status < 200 or quota_status >= 300 or not isinstance(quota_data, dict):
            last_error = f"{base_url} fetchAvailableModels returned {quota_status}: {quota_data}"
            continue

        models = _normalize_antigravity_models(quota_data)
        remaining_values = [model["remaining_pct"] for model in models]
        summary = {
            "model_count": len(models),
            "min_remaining_pct": min(remaining_values) if remaining_values else 0,
            "avg_remaining_pct": int(round(sum(remaining_values) / len(remaining_values))) if remaining_values else 0,
        }
        result = {
            "status": "ok",
            "project_id": project_id,
            "subscription_tier": subscription_tier,
            "models": models,
            "summary": summary,
            "dashboard_url": "https://antigravity.google",
        }
        if creds.get("source"):
            result["source"] = creds["source"]
        if refreshed_once:
            result["token_refreshed"] = True
        return result

    return {"error": "API error", "details": last_error or "No Antigravity endpoint returned quota data"}


### Synthetic.new Functions

def get_synthetic_credentials() -> str | None:
    """Get Synthetic.new API key from environment variables"""
    for var in ["SYNTHETIC_API_KEY", "SYNTHETIC_KEY"]:
        if key := os.environ.get(var):
            return key
    return None


def _format_resets_in(iso_ts: str) -> str | None:
    """Format an ISO-8601 'Z' timestamp as 'Xd Yh' / 'Xh Ym' delta from now (UTC)."""
    if not iso_ts:
        return None
    try:
        s = iso_ts.rstrip("Z")
        # strip subsecond precision so Python 3.9's fromisoformat is happy
        if "." in s:
            s = s.split(".")[0]
        target = datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
        delta_secs = int((target - datetime.now(timezone.utc)).total_seconds())
        if delta_secs <= 0:
            return None
        if delta_secs >= 86400:
            days, remainder = divmod(delta_secs, 86400)
            hours = remainder // 3600
            return f"{days}d {hours}h"
        hours, remainder = divmod(delta_secs, 3600)
        minutes = remainder // 60
        return f"{hours}h {minutes}m"
    except Exception:
        return None


def get_synthetic_usage() -> dict:
    """Fetch Synthetic.new subscription / rolling-5h / weekly-credit quotas."""
    api_key = get_synthetic_credentials()
    if not api_key:
        return {
            "error": "No credentials found",
            "hint": "Set SYNTHETIC_API_KEY environment variable",
            "dashboard": "https://synthetic.new"
        }

    headers = {"Authorization": f"Bearer {api_key}"}
    status, data = http_get("https://api.synthetic.new/v2/quotas", headers)

    if status != 200 or not isinstance(data, dict):
        return {
            "error": f"API error (HTTP {status})",
            "details": data if isinstance(data, str) else json.dumps(data)[:200],
            "dashboard": "https://synthetic.new"
        }

    result: dict = {"status": "ok"}

    # Daily subscription bucket
    sub = data.get("subscription") or {}
    if isinstance(sub, dict) and sub.get("limit") is not None:
        limit = int(sub.get("limit") or 0)
        used = int(sub.get("requests") or 0)
        remaining = max(0, limit - used)
        pct = int(round((used / limit) * 100)) if limit > 0 else 0
        result["daily_subscription"] = {
            "limit": limit,
            "used": used,
            "remaining": remaining,
            "percentage": pct,
        }
        if resets := _format_resets_in(sub.get("renewsAt", "")):
            result["daily_subscription"]["resets_in"] = resets

    # Rolling 5h bucket
    r5h = data.get("rollingFiveHourLimit") or {}
    if isinstance(r5h, dict) and r5h.get("max") is not None:
        limit = int(r5h.get("max") or 0)
        remaining = int(r5h.get("remaining") or 0)
        used = max(0, limit - remaining)
        pct = int(round((used / limit) * 100)) if limit > 0 else 0
        result["rolling_5h"] = {
            "limit": limit,
            "used": used,
            "remaining": remaining,
            "percentage": pct,
            "limited": bool(r5h.get("limited", False)),
        }
        if resets := _format_resets_in(r5h.get("nextTickAt", "")):
            result["rolling_5h"]["next_tick_in"] = resets

    # Weekly credit bucket
    wk = data.get("weeklyTokenLimit") or {}
    if isinstance(wk, dict) and wk.get("percentRemaining") is not None:
        pct_remaining = int(wk.get("percentRemaining") or 0)
        result["weekly_credits"] = {
            "percent_remaining": pct_remaining,
            "percent_used": max(0, 100 - pct_remaining),
            "max_credits": str(wk.get("maxCredits", "")),
            "remaining_credits": str(wk.get("remainingCredits", "")),
            "next_regen_credits": str(wk.get("nextRegenCredits", "")),
        }
        if regen := _format_resets_in(wk.get("nextRegenAt", "")):
            result["weekly_credits"]["next_regen_in"] = regen

    result["hint"] = "Dashboard: https://synthetic.new"
    return result


def print_section(name: str, data: dict):
    """Pretty print a section"""
    print(f"\n{'='*50}")
    print(f"  {name}")
    print('='*50)

    # Show auth info first if available
    if "auth" in data:
        print(f"  🔑 Auth: {data['auth']}")
    if "account" in data:
        print(f"  👤 Account: {data['account']}")
    if "api_key_valid" in data:
        print(f"  🔑 API Key: valid")

    # Show status
    if data.get("status") == "ok":
        print("  ✅ Connected")
    elif data.get("status") == "authenticated":
        print("  ✅ Authenticated")

    # Claude-specific usage data
    if "five_hour" in data:
        fh = data["five_hour"]
        print(f"\n  5-Hour Window:")
        print(f"    Used:      {fh['used']}")
        if "remaining" in fh:
            print(f"    Remaining: {fh['remaining']}")
        if "resets_in" in fh:
            print(f"    Resets in: {fh['resets_in']}")

    if "seven_day" in data:
        sd = data["seven_day"]
        print(f"\n  7-Day Window:")
        print(f"    Used:      {sd['used']}")
        if "remaining" in sd:
            print(f"    Remaining: {sd['remaining']}")
        if "resets_in" in sd:
            print(f"    Resets in: {sd['resets_in']}")

    if "opus" in data:
        print(f"\n  Opus (7-day): {data['opus']['used']} used")

    # Codex-specific (ChatGPT subscription quotas)
    if "plan" in data:
        print(f"  📊 Plan: {data['plan']}")

    if "primary_window" in data:
        pw = data["primary_window"]
        window = pw.get("window", "5h")
        print(f"\n  {window} Window:")
        print(f"    Used:      {pw['used']}")
        if "remaining" in pw:
            print(f"    Remaining: {pw['remaining']}")
        if "resets_in" in pw:
            print(f"    Resets in: {pw['resets_in']}")

    if "secondary_window" in data:
        sw = data["secondary_window"]
        window = sw.get("window", "7d")
        print(f"\n  {window} Window:")
        print(f"    Used:      {sw['used']}")
        if "remaining" in sw:
            print(f"    Remaining: {sw['remaining']}")
        if "resets_in" in sw:
            print(f"    Resets in: {sw['resets_in']}")

    if "code_review" in data:
        cr = data["code_review"]
        print(f"\n  Code Review Quota: {cr['used']} used")

    if "limit_reached" in data:
        print(f"  ⚠️  Rate limit reached!")

    # OpenAI rate limits (legacy/API key mode)
    if "rate_limits" in data:
        rl = data["rate_limits"]
        print(f"\n  API Rate Limits (per minute):")
        if "remaining-requests" in rl and "limit-requests" in rl:
            print(f"    Requests: {rl['remaining-requests']}/{rl['limit-requests']} remaining")
        if "remaining-tokens" in rl and "limit-tokens" in rl:
            remaining = int(rl['remaining-tokens'])
            limit = int(rl['limit-tokens'])
            print(f"    Tokens:   {remaining:,}/{limit:,} remaining")

    # Gemini-specific
    if "tier" in data:
        print(f"  📊 Tier: {data['tier']}")
    if "token_refreshed" in data:
        print(f"  🔄 Token auto-refreshed")
    if "token_expires_in" in data:
        print(f"  ⏱️  Token expires in: {data['token_expires_in']}")
    if "token_status" in data:
        print(f"  ⚠️  Token: {data['token_status']}")
    if "gcp_project" in data:
        print(f"  📦 GCP Project: {data['gcp_project']}")

    # Antigravity per-model quotas
    if isinstance(data.get("models"), list) and "summary" in data:
        if "project_id" in data:
            print(f"  📦 Project: {data['project_id']}")
        if "subscription_tier" in data:
            print(f"  📊 Tier: {data['subscription_tier']}")
        summary = data["summary"]
        print(f"\n  Model Quotas:")
        print(f"    Models:    {summary.get('model_count', 0)}")
        print(f"    Tightest:  {summary.get('min_remaining_pct', 0)}% remaining")
        print(f"    Average:   {summary.get('avg_remaining_pct', 0)}% remaining")
        print(f"\n    {'Model':<32} {'Remaining':>10}  Reset")
        print(f"    {'-'*32} {'-'*10}  {'-'*16}")
        sorted_models = sorted(data["models"], key=lambda item: (item.get("remaining_pct", 0), item.get("name", "")))
        for model in sorted_models[:10]:
            name = str(model.get("name", "?"))[:32]
            remaining = model.get("remaining_pct", 0)
            reset = model.get("reset_time") or ""
            print(f"    {name:<32} {remaining:>9}%  {reset}")
        hidden_count = len(sorted_models) - 10
        if hidden_count > 0:
            print(f"    ... {hidden_count} more models hidden")

    # Gemini tier quotas
    if isinstance(data.get("models"), dict):
        print(f"\n  Model Quotas by Tier:")
        tier_order = ["3-Flash", "Flash", "Pro"]
        for tier_name in tier_order:
            tier_models = GEMINI_TIERS.get(tier_name, [])
            for model_id in tier_models:
                if model_id in data["models"]:
                    model_data = data["models"][model_id]
                    used = model_data.get("used", "?")
                    remaining = model_data.get("remaining", "?")
                    reset = model_data.get("resets_in", "")
                    reset_str = f" (resets: {reset})" if reset else ""
                    print(f"    {tier_name} ({model_id}): {used} used, {remaining} remaining{reset_str}")
                    break  # Only need first model from each tier


    # Z.AI-specific
    if "token_quota" in data:
        tq = data["token_quota"]
        used_pct = tq.get("percentage", 0)
        remaining_pct = 100 - used_pct
        print(f"\n  Token Quota:")
        print(f"    Used:      {used_pct}%")
        print(f"    Remaining: {remaining_pct}%")
        if "resets_in" in tq:
            print(f"    Resets in: {tq['resets_in']}")
        # Show actual numbers (only when the API provided them)
        if tq.get("limit") and "used" in tq:
            print(f"    ({tq['used']:,} / {tq['limit']:,} tokens)")

    if "request_quota" in data:
        rq = data["request_quota"]
        if rq.get("limit"):
            print(f"\n  Request Quota:")
            print(f"    Used:      {rq['used']:,} / {rq['limit']:,}")
            print(f"    Remaining: {rq['remaining']:,}")

    if "weekly_usage" in data:
        wu = data["weekly_usage"]
        print(f"\n  7-Day Historical:")
        print(f"    API Calls: {wu['calls']:,}")
        print(f"    Tokens:    {wu['tokens']:,}")

    # Synthetic.new (subscription + rolling 5h + weekly credits)
    if "daily_subscription" in data:
        ds = data["daily_subscription"]
        print(f"\n  Subscription:")
        print(f"    Used:      {ds['used']:,} / {ds['limit']:,} ({ds['percentage']}%)")
        print(f"    Remaining: {ds['remaining']:,}")
        if "resets_in" in ds:
            print(f"    Renews in: {ds['resets_in']}")

    if "rolling_5h" in data:
        r5h = data["rolling_5h"]
        print(f"\n  5-Hour Rolling:")
        print(f"    Used:      {r5h['used']:,} / {r5h['limit']:,} ({r5h['percentage']}%)")
        print(f"    Remaining: {r5h['remaining']:,}")
        if r5h.get("limited"):
            print(f"    ⚠️  Currently rate-limited")
        if "next_tick_in" in r5h:
            print(f"    Next tick: {r5h['next_tick_in']}")

    if "weekly_credits" in data:
        wc = data["weekly_credits"]
        print(f"\n  Weekly Credits:")
        print(f"    Remaining: {wc['remaining_credits']} / {wc['max_credits']} ({wc['percent_remaining']}%)")
        if wc.get("next_regen_credits"):
            extra = f" (+{wc['next_regen_credits']})"
        else:
            extra = ""
        if "next_regen_in" in wc:
            print(f"    Next regen: {wc['next_regen_in']}{extra}")

    # OpenRouter-specific
    if "balance_usd" in data:
        balance = data["balance_usd"]
        total_credits = data.get("total_credits_usd", 0)
        total_usage = data.get("total_usage_usd", 0)
        print(f"\n  Balance:")
        print(f"    Current:   ${balance:.2f}")
        print(f"    Purchased: ${total_credits:.2f}")
        print(f"    Used:      ${total_usage:.2f}")
    if "dashboard_url" in data:
        print(f"  🔗 {data['dashboard_url']}")

    # Kimi-specific
    if "balance" in data and "cash_balance" in data:
        balance = data["balance"]
        cash = data["cash_balance"]
        voucher = data["voucher_balance"]
        currency = data.get("currency", "USD")
        symbol = "$" if currency == "USD" else "¥"
        
        print(f"\n  Balance ({currency}):")
        print(f"    Total:     {symbol}{balance:.4f}")
        print(f"    Cash:      {symbol}{cash:.4f}")
        print(f"    Voucher:   {symbol}{voucher:.4f}")
        
    # General info
    if "source" in data:
        print(f"  📡 Source: {data['source']}")

    # Error/info messages
    if "error" in data:
        # Only show as error if we don't have auth info
        if "auth" not in data and "account" not in data and "api_key_valid" not in data:
            print(f"  ❌ {data['error']}")
        else:
            print(f"  ⚠️  {data['error']}")
    if "hint" in data:
        print(f"  💡 {data['hint']}")
    if "note" in data:
        print(f"  📝 {data['note']}")
    if "fallback" in data:
        print(f"  🔗 {data['fallback']}")
    if "dashboard" in data:
        print(f"  🔗 {data['dashboard']}")
    if "hint_refresh" in data:
        print(f"  🔄 {data['hint_refresh']}")


def get_color_for_pct(pct: float) -> str:
    """Get ANSI color code based on usage percentage"""
    if pct >= 100:
        return COLORS['bold_red']
    elif pct >= 90:
        return COLORS['red']
    elif pct >= 70:
        return COLORS['yellow']
    else:
        return COLORS['green']


def colorize_pct(pct_str: str, pct: float) -> str:
    """Wrap percentage string in appropriate color"""
    color = get_color_for_pct(pct)
    return f"{color}{pct_str}{COLORS['reset']}"


def get_status_icon(pct: float) -> str:
    """Get status emoji based on usage percentage"""
    if pct >= 100:
        return "❌"
    elif pct >= 90:
        return "🔴"
    elif pct >= 70:
        return "⚠️"
    else:
        return "✅"


def print_oneline(results: dict, window: str = "5h", use_color: bool = False, cache_age: int | None = None):
    """Print compact one-liner output"""
    if window not in ("5h", "7d", "both"):
        window = "5h"

    parts = []
    error_icon = f"{COLORS['bold_red']}ERR{COLORS['reset']}" if use_color else "❌"
    nokey_icon = f"{COLORS['yellow']}no key{COLORS['reset']}" if use_color else "🔑"
    expired_icon = f"{COLORS['yellow']}expired{COLORS['reset']}" if use_color else "⏰"

    def fail_icon(data: dict) -> str:
        """Missing credentials / expired tokens are config issues, not outages — show them differently"""
        if data.get("error") == NO_CREDS_ERROR:
            return nokey_icon
        if data.get("token_status") == "expired" or data.get("error") == "Token expired":
            return expired_icon
        return error_icon

    # Claude
    if "claude" in results:
        data = results["claude"]
        if data.get("status") == "ok" or "five_hour" in data:
            if window == "both" and "five_hour" in data and "seven_day" in data:
                pct_5h = data["five_hour"]["used"].rstrip("%")
                pct_7d = data["seven_day"]["used"].rstrip("%")
                max_pct = max(float(pct_5h), float(pct_7d))
                pct_display = f"{pct_5h}%/{pct_7d}%"
                if use_color:
                    parts.append(f"Claude: {colorize_pct(pct_display, max_pct)}")
                else:
                    parts.append(f"Claude: {pct_display} {get_status_icon(max_pct)}")
            elif window == "5h" and "five_hour" in data:
                pct_str = data["five_hour"]["used"]
                pct = float(pct_str.rstrip("%"))
                if use_color:
                    parts.append(f"Claude: {colorize_pct(pct_str, pct)} (5h)")
                else:
                    parts.append(f"Claude: {pct_str} (5h) {get_status_icon(pct)}")
            elif window == "7d" and "seven_day" in data:
                pct_str = data["seven_day"]["used"]
                pct = float(pct_str.rstrip("%"))
                if use_color:
                    parts.append(f"Claude: {colorize_pct(pct_str, pct)} (7d)")
                else:
                    parts.append(f"Claude: {pct_str} (7d) {get_status_icon(pct)}")
        elif "error" in data or data.get("token_status") == "expired":
            parts.append(f"Claude: {fail_icon(data)}")

    # Codex
    if "codex" in results:
        data = results["codex"]
        if data.get("status") == "ok":
            if window == "both" and "primary_window" in data and "secondary_window" in data:
                pct_5h = data["primary_window"]["used"].rstrip("%")
                pct_7d = data["secondary_window"]["used"].rstrip("%")
                max_pct = max(float(pct_5h), float(pct_7d))
                pct_display = f"{pct_5h}%/{pct_7d}%"
                if use_color:
                    parts.append(f"Codex: {colorize_pct(pct_display, max_pct)}")
                else:
                    parts.append(f"Codex: {pct_display} {get_status_icon(max_pct)}")
            elif window == "5h" and "primary_window" in data:
                pct_str = data["primary_window"]["used"]
                pct = float(pct_str.rstrip("%"))
                if use_color:
                    parts.append(f"Codex: {colorize_pct(pct_str, pct)} (5h)")
                else:
                    parts.append(f"Codex: {pct_str} (5h) {get_status_icon(pct)}")
            elif window == "7d" and "secondary_window" in data:
                pct_str = data["secondary_window"]["used"]
                pct = float(pct_str.rstrip("%"))
                if use_color:
                    parts.append(f"Codex: {colorize_pct(pct_str, pct)} (7d)")
                else:
                    parts.append(f"Codex: {pct_str} (7d) {get_status_icon(pct)}")
        elif "error" in data or data.get("token_status") == "expired":
            parts.append(f"Codex: {fail_icon(data)}")

    # Z.AI (5h shared quota across GLM models)
    if "zai" in results:
        data = results["zai"]
        if data.get("status") == "ok" and "token_quota" in data:
            pct = data["token_quota"].get("percentage", 0)
            rq = data.get("request_quota", {})
            if window == "both" and rq.get("limit"):
                # Second value: request quota (tokens% / requests%)
                req_pct = round(rq.get("used", 0) / rq["limit"] * 100)
                max_pct = max(float(pct), float(req_pct))
                pct_display = f"{pct}%/{req_pct}%"
                if use_color:
                    parts.append(f"Z.AI: {colorize_pct(pct_display, max_pct)}")
                else:
                    parts.append(f"Z.AI: {pct_display} {get_status_icon(max_pct)}")
            else:
                pct_str = f"{pct}% (5h)"
                if use_color:
                    parts.append(f"Z.AI: {colorize_pct(pct_str, pct)}")
                else:
                    parts.append(f"Z.AI: {pct_str} {get_status_icon(pct)}")
        elif "error" in data or data.get("token_status") == "expired":
            parts.append(f"Z.AI: {fail_icon(data)}")

    # Synthetic.new (5h rolling + weekly credits)
    if "synthetic" in results:
        data = results["synthetic"]
        if data.get("status") == "ok":
            pct_5h = data.get("rolling_5h", {}).get("percentage")
            pct_7d = data.get("weekly_credits", {}).get("percent_used")
            if window == "both" and pct_5h is not None and pct_7d is not None:
                max_pct = max(float(pct_5h), float(pct_7d))
                pct_display = f"{pct_5h}%/{pct_7d}%"
                if use_color:
                    parts.append(f"Synthetic: {colorize_pct(pct_display, max_pct)}")
                else:
                    parts.append(f"Synthetic: {pct_display} {get_status_icon(max_pct)}")
            elif window == "7d" and pct_7d is not None:
                pct_str = f"{pct_7d}% (7d)"
                if use_color:
                    parts.append(f"Synthetic: {colorize_pct(pct_str, float(pct_7d))}")
                else:
                    parts.append(f"Synthetic: {pct_str} {get_status_icon(float(pct_7d))}")
            elif pct_5h is not None:
                pct_str = f"{pct_5h}% (5h)"
                if use_color:
                    parts.append(f"Synthetic: {colorize_pct(pct_str, float(pct_5h))}")
                else:
                    parts.append(f"Synthetic: {pct_str} {get_status_icon(float(pct_5h))}")
        elif "error" in data or data.get("token_status") == "expired":
            parts.append(f"Synthetic: {fail_icon(data)}")

    # Gemini (group by quota tier)
    if "gemini" in results:
        data = results["gemini"]
        if data.get("status") == "ok" and "models" in data:
            gemini_parts = []
            # Display tiers in order: 3-Flash, Flash, Pro
            for tier_name in ["3-Flash", "Flash", "Pro"]:
                if tier_name not in GEMINI_TIERS:
                    continue
                # Find first model in this tier with data
                for model_id in GEMINI_TIERS[tier_name]:
                    if model_id in data["models"]:
                        pct_str = data["models"][model_id]["used"]
                        pct = float(pct_str.rstrip("%"))
                        if use_color:
                            gemini_parts.append(f"{tier_name} {colorize_pct(pct_str, pct)}")
                        else:
                            gemini_parts.append(f"{tier_name} {pct_str} {get_status_icon(pct)}")
                        break  # Only show once per tier
            if gemini_parts:
                parts.append(f"Gemini: ( {' | '.join(gemini_parts)} )")
        elif "error" in data or data.get("token_status") == "expired":
            parts.append(f"Gemini: {fail_icon(data)}")


    # OpenRouter
    if "openrouter" in results:
        data = results["openrouter"]
        if data.get("status") == "ok" and "balance_usd" in data:
            balance = data["balance_usd"]
            balance_str = f"${balance:.2f}"
            # Status thresholds: >$5 ✅, $1-5 ⚠️, <$1 🔴, $0 ❌
            if use_color:
                if balance <= 0:
                    color = COLORS['bold_red']
                elif balance < 1.0:
                    color = COLORS['red']
                elif balance < 5.0:
                    color = COLORS['yellow']
                else:
                    color = COLORS['green']
                parts.append(f"OpenRouter: {color}{balance_str}{COLORS['reset']}")
            else:
                if balance <= 0:
                    status_icon = "❌"
                elif balance < 1.0:
                    status_icon = "🔴"
                elif balance < 5.0:
                    status_icon = "⚠️"
                else:
                    status_icon = "✅"
                parts.append(f"OpenRouter: {balance_str} {status_icon}")
        elif "error" in data or data.get("token_status") == "expired":
            parts.append(f"OpenRouter: {fail_icon(data)}")

    # Kimi
    if "kimi" in results:
        data = results["kimi"]
        if data.get("status") == "ok" and "balance" in data:
            balance = data["balance"]
            currency = data.get("currency", "USD")
            symbol = "$" if currency == "USD" else "¥"
            balance_str = f"{symbol}{balance:.2f}"
            
            # Status thresholds: >$5 ✅, $1-5 ⚠️, <$1 🔴, $0 ❌
            if use_color:
                if balance <= 0:
                    color = COLORS['bold_red']
                elif balance < 1.0:
                    color = COLORS['red']
                elif balance < 5.0:
                    color = COLORS['yellow']
                else:
                    color = COLORS['green']
                parts.append(f"Kimi: {color}{balance_str}{COLORS['reset']}")
            else:
                if balance <= 0:
                    status_icon = "❌"
                elif balance < 1.0:
                    status_icon = "🔴"
                elif balance < 5.0:
                    status_icon = "⚠️"
                else:
                    status_icon = "✅"
                parts.append(f"Kimi: {balance_str} {status_icon}")
        elif "error" in data or data.get("token_status") == "expired":
            parts.append(f"Kimi: {fail_icon(data)}")

    # Antigravity
    if "antigravity" in results:
        data = results["antigravity"]
        if data.get("status") == "ok" and "summary" in data:
            summary = data["summary"]
            min_pct = int(summary.get("min_remaining_pct", 0))
            model_count = int(summary.get("model_count", 0))
            used_pct = max(0, 100 - min_pct)
            pct_str = f"{used_pct}%"
            if use_color:
                parts.append(f"Antigravity: {colorize_pct(pct_str, used_pct)} ({model_count} models)")
            else:
                parts.append(f"Antigravity: {pct_str} ({model_count} models) {get_status_icon(used_pct)}")
        elif "error" in data or data.get("token_status") == "expired":
            parts.append(f"Antigravity: {fail_icon(data)}")

    line = " | ".join(parts)
    if cache_age is not None:
        line += f" (cached {format_cache_age(cache_age)})"
    print(line)


def main():
    import argparse

    epilog = """
Credential Locations (auto-discovered):
  Claude     ~/.claude/.credentials.json (Linux)
              macOS Keychain "Claude Code-credentials" (macOS)
  Codex      ~/.codex/auth.json
  Gemini     ~/.gemini/oauth_creds.json (auto-refreshes expired tokens)
  Z.AI       $ZAI_KEY or $ZAI_API_KEY environment variable
  OpenRouter $OPENROUTER_API_KEY environment variable
  Kimi       $MOONSHOT_API_KEY environment variable
  Antigravity system keyring, or $ANTIGRAVITY_REFRESH_TOKEN
  Synthetic  $SYNTHETIC_API_KEY environment variable

Setup (one-time):
  claude           # Login to Claude Code
  codex login      # Login to OpenAI Codex
  gemini           # Login to Gemini CLI
  antigravity auth login  # Login to Google Antigravity
  export ZAI_KEY=your-key         # Add to ~/.zshrc or ~/.bashrc
  export MOONSHOT_API_KEY=key     # Add to ~/.zshrc or ~/.bashrc
  export SYNTHETIC_API_KEY=key    # Add to ~/.zshrc or ~/.bashrc

Examples:
  cclimits              # Check all tools (detailed)
  cclimits --claude     # Claude only
  cclimits --kimi       # Kimi only
  cclimits --antigravity # Antigravity only
  cclimits --synthetic  # Synthetic.new only
  cclimits --json       # JSON output
  cclimits --oneline      # Compact one-liner (5h window)
  cclimits --oneline 7d   # Compact one-liner (7d window)
  cclimits --oneline both # Compact one-liner (5h/7d window)

Example Output:
  # One-liner (5h window)
  Claude: 4.0% (5h) ✅ | Codex: 0% (5h) ✅ | Z.AI: 1% (5h) ✅ | Gemini: ( 3-Flash 7% ✅ ... ) | Kimi: $49.59 ✅ | Antigravity: 65% (8 models) ✅ | Synthetic: 0% (5h) ✅
"""

    parser = argparse.ArgumentParser(
        description="Check AI CLI usage/quota for Claude, Codex, Gemini, Z.AI, OpenRouter, Kimi, Antigravity, Synthetic.new",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--oneline", nargs="?", const="5h", metavar="WINDOW",
                        help="Compact one-liner output (5h, 7d, or both; default: 5h)")
    parser.add_argument("--noemoji", action="store_true",
                        help="Use colored text instead of emojis (for terminals without emoji support)")
    parser.add_argument("--claude", action="store_true", help="Only check Claude Code")
    parser.add_argument("--codex", action="store_true", help="Only check Codex")
    parser.add_argument("--gemini", action="store_true", help="Only check Gemini")
    parser.add_argument("--zai", action="store_true", help="Only check Z.AI")
    parser.add_argument("--openrouter", action="store_true", help="Only check OpenRouter")
    parser.add_argument("--kimi", action="store_true", help="Only check Kimi (Moonshot AI)")
    parser.add_argument("--antigravity", action="store_true", help="Only check Google Antigravity")
    parser.add_argument("--synthetic", action="store_true", help="Only check Synthetic.new")
    parser.add_argument("--cached", action="store_true", help="Use cached data if fresh (< TTL), fetch if stale")
    parser.add_argument("--cache-ttl", type=int, metavar="SECONDS",
                        help="Override default TTL (default: 60, implies --cached)")
    args = parser.parse_args()

    # Determine cache settings
    use_cache = args.cached or args.cache_ttl is not None
    cache_ttl = args.cache_ttl if args.cache_ttl is not None else DEFAULT_CACHE_TTL

    # Which providers were explicitly requested (empty = check all)
    requested = [name for name in
                 ("claude", "codex", "gemini", "zai", "openrouter", "kimi", "antigravity", "synthetic")
                 if getattr(args, name)]
    check_all = not requested

    # Try to read from cache if caching is enabled
    results = None
    cache_age = None
    if use_cache:
        cached = read_cache(cache_ttl)
        if cached is not None:
            cached_data, age = cached
            if check_all:
                results, cache_age = cached_data, age
            elif all(name in cached_data for name in requested):
                # Honor provider filters on cache hits; refetch if any requested provider is missing
                results = {name: cached_data[name] for name in requested}
                cache_age = age

    skip_fetch = results is not None
    if not skip_fetch:
        results = {}

        # Build the work list using the same dispatch logic as before.
        # Credential discovery for the gated providers (openrouter, kimi,
        # antigravity, synthetic) runs before submission — same as the
        # original sequential code — so that check_all runs without
        # credentials simply omit the provider.  The actual HTTP fetches
        # then run concurrently in a thread pool so the total wall time
        # approximates the slowest single provider rather than the sum.
        work: list[tuple[str, Callable[[], dict]]] = []

        if check_all or args.claude:
            work.append(("claude", get_claude_usage))
        if check_all or args.codex:
            work.append(("codex", get_codex_usage))
        if check_all or args.gemini:
            work.append(("gemini", get_gemini_usage))
        if check_all or args.zai:
            work.append(("zai", get_zai_usage))

        if args.openrouter or (check_all and get_openrouter_credentials()):
            work.append(("openrouter", get_openrouter_usage))
        if args.kimi or (check_all and get_kimi_credentials()):
            work.append(("kimi", get_kimi_usage))
        if args.antigravity or (check_all and get_antigravity_credentials()):
            work.append(("antigravity", get_antigravity_usage))
        if args.synthetic or (check_all and get_synthetic_credentials()):
            work.append(("synthetic", get_synthetic_usage))

        if work:
            with ThreadPoolExecutor(max_workers=len(work)) as executor:
                future_map = {
                    name: executor.submit(fn) for name, fn in work
                }
                # Collect results in canonical provider order, not
                # completion order, so output (especially --json key
                # order) is deterministic.
                for name in ("claude", "codex", "gemini", "zai",
                             "openrouter", "kimi", "antigravity",
                             "synthetic"):
                    if name in future_map:
                        try:
                            results[name] = future_map[name].result()
                        except Exception as exc:
                            results[name] = {"error": str(exc)}

        # Always write cache for future --cached calls
        write_cache(results)

    if args.json:
        print(json.dumps(results, indent=2))
    elif args.oneline:
        window = args.oneline if args.oneline in ("5h", "7d", "both") else "5h"
        print_oneline(results, window, use_color=args.noemoji, cache_age=cache_age)
    else:
        print("\n🔍 AI CLI Usage Checker")
        cached_note = f"  (cached {format_cache_age(cache_age)} ago)" if cache_age is not None else ""
        print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{cached_note}")

        if "claude" in results:
            print_section("Claude Code", results["claude"])
        if "codex" in results:
            print_section("OpenAI Codex", results["codex"])
        if "gemini" in results:
            print_section("Gemini CLI", results["gemini"])
        if "zai" in results:
            print_section("Z.AI (5h shared - GLM-4.x)", results["zai"])
        if "openrouter" in results:
            print_section("OpenRouter", results["openrouter"])
        if "kimi" in results:
            print_section("Kimi K2 (Moonshot AI)", results["kimi"])
        if "antigravity" in results:
            print_section("Google Antigravity", results["antigravity"])
        if "synthetic" in results:
            print_section("Synthetic.new", results["synthetic"])

        print("\n" + "="*50)
        print("  Done!")
        print("="*50 + "\n")


if __name__ == "__main__":
    main()
