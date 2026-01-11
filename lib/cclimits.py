#!/usr/bin/env python3
"""
AI CLI Usage Checker
Fetches remaining quota/usage for Claude Code, Codex, Gemini, and Z.AI
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Optional: use requests if available, fallback to urllib
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
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

def read_cache(ttl: int) -> dict | None:
    """Read cache if fresh (younger than TTL seconds), return None if stale/missing"""
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
            return cache_data["data"]
        
        return None
    except (json.JSONDecodeError, KeyError, TypeError, OSError, PermissionError):
        return None

def write_cache(data: dict) -> bool:
    """Write data to cache file, return success status"""
    try:
        cache_file = get_cache_path()
        import time
        cache_data = {
            "timestamp": time.time(),
            "data": data
        }
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)
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
    if HAS_REQUESTS:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            try:
                return resp.status_code, resp.json()
            except:
                return resp.status_code, resp.text
        except Exception as e:
            return 0, str(e)
    else:
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
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
    if HAS_REQUESTS:
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=10)
            try:
                return resp.status_code, resp.json()
            except:
                return resp.status_code, resp.text
        except Exception as e:
            return 0, str(e)
    else:
        req = urllib.request.Request(
            url,
            headers=headers,
            data=json.dumps(body).encode('utf-8'),
            method='POST'
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
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
        result = {"status": "ok"}

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
        if HAS_REQUESTS:
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
        limits = data.get("data", {}).get("limits", [])

        for limit in limits:
            limit_type = limit.get("type")
            if limit_type == "TOKENS_LIMIT":
                total = limit.get("usage", 0)
                used = limit.get("currentValue", 0)
                remaining = limit.get("remaining", 0)
                pct = limit.get("percentage", 0)

                result["token_quota"] = {
                    "limit": total,
                    "used": used,
                    "remaining": remaining,
                    "percentage": pct,
                }

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

    # Add hints
    result["hint"] = "Dashboard: https://z.ai/manage-apikey/billing"

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
        print(f"    Remaining: {fh['remaining']}")
        print(f"    Resets in: {fh['resets_in']}")

    if "seven_day" in data:
        sd = data["seven_day"]
        print(f"\n  7-Day Window:")
        print(f"    Used:      {sd['used']}")
        print(f"    Remaining: {sd['remaining']}")
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
        print(f"    Remaining: {pw['remaining']}")
        if "resets_in" in pw:
            print(f"    Resets in: {pw['resets_in']}")

    if "secondary_window" in data:
        sw = data["secondary_window"]
        window = sw.get("window", "7d")
        print(f"\n  {window} Window:")
        print(f"    Used:      {sw['used']}")
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

    # Gemini tier quotas
    if "models" in data:
        print(f"\n  Quota by Tier:")
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
                    print(f"    {tier_name}: {used} used, {remaining} remaining{reset_str}")
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
        # Show actual numbers
        if tq.get("limit"):
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


def print_oneline(results: dict, window: str = "5h", use_color: bool = False):
    """Print compact one-liner output"""
    parts = []
    error_icon = f"{COLORS['bold_red']}ERR{COLORS['reset']}" if use_color else "❌"

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
        elif "error" in data:
            parts.append(f"Claude: {error_icon}")

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
        elif "error" in data:
            parts.append(f"Codex: {error_icon}")

    # Z.AI (5h shared quota across GLM models)
    if "zai" in results:
        data = results["zai"]
        if data.get("status") == "ok" and "token_quota" in data:
            pct = data["token_quota"].get("percentage", 0)
            pct_str = f"{pct}% (5h)"
            if use_color:
                parts.append(f"Z.AI: {colorize_pct(pct_str, pct)}")
            else:
                parts.append(f"Z.AI: {pct_str} {get_status_icon(pct)}")
        elif "error" in data:
            parts.append(f"Z.AI: {error_icon}")

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
        elif "error" in data:
            parts.append(f"Gemini: {error_icon}")


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
        elif "error" in data:
            parts.append(f"OpenRouter: {error_icon}")

    print(" | ".join(parts))


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

Setup (one-time):
  claude           # Login to Claude Code
  codex login      # Login to OpenAI Codex
  gemini           # Login to Gemini CLI
  export ZAI_KEY=your-key  # Add to ~/.zshrc or ~/.bashrc

Examples:
  cclimits              # Check all tools (detailed)
  cclimits --claude     # Claude only
  cclimits --json       # JSON output
  cclimits --oneline      # Compact one-liner (5h window)
  cclimits --oneline 7d   # Compact one-liner (7d window)
  cclimits --oneline both # Compact one-liner (5h/7d window)

Example Output:
  # One-liner (5h window)
  Claude: 4.0% (5h) ✅ | Codex: 0% (5h) ✅ | Z.AI: 1% (5h) ✅ | Gemini: ( 3-Flash 7% ✅ | Flash 1% ✅ | Pro 10% ✅ )
"""

    parser = argparse.ArgumentParser(
        description="Check AI CLI usage/quota for Claude, Codex, Gemini, Z.AI, OpenRouter",
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
    parser.add_argument("--cached", action="store_true", help="Use cached data if fresh (< TTL), fetch if stale")
    parser.add_argument("--cache-ttl", type=int, metavar="SECONDS",
                        help="Override default TTL (default: 60, implies --cached)")
    args = parser.parse_args()

    # Determine cache settings
    use_cache = args.cached or args.cache_ttl is not None
    cache_ttl = args.cache_ttl if args.cache_ttl is not None else DEFAULT_CACHE_TTL

    # Try to read from cache if caching is enabled
    results = None
    if use_cache:
        cached_results = read_cache(cache_ttl)
        if cached_results is not None:
            results = cached_results

    # If no specific tool selected, check all
    check_all = not (args.claude or args.codex or args.gemini or args.zai or args.openrouter)

    skip_fetch = results is not None
    if not skip_fetch:
        results = {}

    if not skip_fetch and (check_all or args.claude):
        results["claude"] = get_claude_usage()
    if not skip_fetch and (check_all or args.codex):
        results["codex"] = get_codex_usage()
    if not skip_fetch and (check_all or args.gemini):
        results["gemini"] = get_gemini_usage()
    if not skip_fetch and (check_all or args.zai):
        results["zai"] = get_zai_usage()
    if check_all or args.openrouter:
        results["openrouter"] = get_openrouter_usage()

    # Always write cache for future --cached calls
    if not skip_fetch:
        write_cache(results)

    if args.json:
        print(json.dumps(results, indent=2))
    elif args.oneline:
        window = args.oneline if args.oneline in ("5h", "7d", "both") else "5h"
        print_oneline(results, window, use_color=args.noemoji)
    else:
        print("\n🔍 AI CLI Usage Checker")
        print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

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

        print("\n" + "="*50)
        print("  Done!")
        print("="*50 + "\n")


if __name__ == "__main__":
    main()
