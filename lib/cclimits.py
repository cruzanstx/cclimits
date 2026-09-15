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
from datetime import datetime, timedelta, timezone
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

from codex_native import get_native_codex_usage




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
STALE_CACHE_MAX_AGE = 24 * 60 * 60  # 24h — don't serve stale fallback data older than this

def get_cache_path() -> Path:
    """Get cache file path, creating directory if needed"""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError):
        pass  # Silently fail if we can't create directory
    return CACHE_FILE

def read_cache(ttl: int, max_age: int | None = None) -> tuple[dict, int] | None:
    """Read cache if fresh, return (data, age_seconds) or None.

    Normally freshness is bounded by *ttl*.  When *max_age* is given the ttl
    is ignored and entries up to *max_age* seconds old are returned — used by
    the stale-cache fallback to serve the last good reading when a live
    fetch hits a transient error.
    """
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
        bound = max_age if max_age is not None else ttl
        if cache_age < bound:
            return cache_data["data"], int(cache_age)

        return None
    except (json.JSONDecodeError, KeyError, TypeError, OSError, PermissionError):
        return None

NO_CREDS_ERROR = "No credentials found"
COPILOT_NO_SUB_ERROR = "No Copilot subscription"

# Error strings that signal a config/auth problem the user must fix, not a
# transient outage.  These are excluded from stale-cache fallback.
_NON_TRANSIENT_ERRORS = frozenset({
    NO_CREDS_ERROR,
    COPILOT_NO_SUB_ERROR,
    "Token expired",
    "Invalid API key",
    "Forbidden",
    "Authentication failed",
})


def _is_transient_error(data: object) -> bool:
    """True if *data* is a transient fetch error (network blip, HTTP 5xx,
    generic ``API error`` / ``Could not fetch usage``) suitable for
    stale-cache fallback.  Config issues the user must fix — missing
    credentials, expired tokens, 401/invalid-key, 403/forbidden — are NOT
    transient.
    """
    if not isinstance(data, dict) or "error" not in data:
        return False
    if data.get("token_status") == "expired":
        return False
    err = data.get("error")
    if not isinstance(err, str):
        return False
    if err in _NON_TRANSIENT_ERRORS:
        return False
    if "401" in err or "403" in err:
        return False
    return True


def _is_good_cache_entry(data: object) -> bool:
    """A cached entry is 'good' if it carries a successful status."""
    return isinstance(data, dict) and data.get("status") in ("ok", "authenticated")


def format_cache_age(seconds: int) -> str:
    """Format cache age compactly: 42s, 3m, 2h"""
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    return f"{seconds // 3600}h"

def merge_cache_data(old: dict, new: dict) -> dict:
    """Merge new results over previous cache, keeping earlier good entries
    for providers this run couldn't check or hit a transient error on
    (missing credentials in this environment shouldn't erase data cached
    from an environment that has them; a network blip shouldn't either)."""
    merged = dict(old) if isinstance(old, dict) else {}
    for key, value in new.items():
        prev = merged.get(key)
        if isinstance(value, dict) and isinstance(prev, dict):
            if value.get("error") == NO_CREDS_ERROR and prev.get("error") != NO_CREDS_ERROR:
                continue
            if _is_transient_error(value) and _is_good_cache_entry(prev):
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


def apply_stale_fallback(results: dict, cached_data: dict, cached_age: int,
                         max_age: int = STALE_CACHE_MAX_AGE) -> dict:
    """Replace transient-error entries with stale-but-good cached entries.

    A substituted entry is annotated with ``stale_age_seconds`` and
    ``stale_fallback = True`` so output renderers can label it.  Entries
    whose cached age meets or exceeds *max_age*, or whose live error is
    non-transient (no creds, expired token, 401/invalid key), are left
    unchanged.
    """
    if cached_age >= max_age:
        return results
    updated = dict(results)
    for key, data in results.items():
        if _is_transient_error(data):
            cached_entry = cached_data.get(key)
            if isinstance(cached_entry, dict) and _is_good_cache_entry(cached_entry):
                stale = dict(cached_entry)
                stale["stale_age_seconds"] = cached_age
                stale["stale_fallback"] = True
                updated[key] = stale
    return updated


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

        days, remainder = divmod(int(delta.total_seconds()), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes = remainder // 60

        if days > 0:
            return f"{days}d {hours}h"
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



# Claude Desktop OAuth discovery is intentionally read-only. We borrow only a
# currently valid access token maintained by the official Desktop app and never
# refresh or write it back, because OAuth refresh-token rotation could invalidate
# Claude Desktop's own copy.
#
# Windows safeStorage implementation adapted from the MIT-licensed
# huanchong-99/claude-usage-assistant project. Its MIT notice is preserved in
# THIRD_PARTY_NOTICES.md. Profile discovery also covers the Microsoft Store/MSIX
# layout used by current Claude Desktop releases.
CLAUDE_DESKTOP_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
CLAUDE_DESKTOP_TOKEN_SAFETY_SECONDS = 120


def _claude_desktop_dir_candidates() -> list[Path]:
    """Return likely Claude Desktop user-data directories, zero-config."""
    candidates: list[Path] = []

    if sys.platform.startswith("win"):
        roaming = os.environ.get("APPDATA")
        if roaming:
            candidates.append(Path(roaming) / "Claude")
        else:
            candidates.append(Path.home() / "AppData" / "Roaming" / "Claude")

        local = os.environ.get("LOCALAPPDATA")
        packages = Path(local) / "Packages" if local else Path.home() / "AppData" / "Local" / "Packages"
        try:
            if packages.exists():
                store_profiles = []
                for entry in packages.iterdir():
                    name = entry.name.lower()
                    if not (name.startswith("claude_") or "anthropic" in name):
                        continue
                    profile = entry / "LocalCache" / "Roaming" / "Claude"
                    if profile.exists():
                        try:
                            mtime = profile.stat().st_mtime
                        except OSError:
                            mtime = 0
                        has_cookie_db = any(
                            p.exists()
                            for p in (
                                profile / "Network" / "Cookies",
                                profile / "Cookies",
                                profile / "Default" / "Network" / "Cookies",
                                profile / "Default" / "Cookies",
                            )
                        )
                        store_profiles.append((has_cookie_db, mtime, profile))
                store_profiles.sort(key=lambda item: (item[0], item[1]), reverse=True)
                candidates.extend(item[2] for item in store_profiles)
        except (OSError, PermissionError):
            pass
    else:
        # Desktop safeStorage extraction is currently implemented only for Windows.
        # Avoid detecting profiles on platforms where we cannot read their OAuth token.
        return []

    seen = set()
    result = []
    for path in candidates:
        key = os.path.normcase(os.path.abspath(str(path)))
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def _win_dpapi_unprotect(blob: bytes) -> bytes | None:
    """Decrypt a Windows DPAPI blob using only Python stdlib ctypes."""
    if not sys.platform.startswith("win") or not blob:
        return None
    try:
        import ctypes
        import ctypes.wintypes as wt

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", wt.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_char)),
            ]

        in_buf = ctypes.create_string_buffer(blob, len(blob))
        in_blob = DATA_BLOB(
            len(blob),
            ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_char)),
        )
        out_blob = DATA_BLOB()

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
        )
        if not ok:
            return None
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            kernel32.LocalFree(out_blob.pbData)
    except Exception:
        return None


def _win_gcm_decrypt(key: bytes, nonce: bytes, ciphertext: bytes, tag: bytes) -> bytes | None:
    """AES-256-GCM through Windows CNG/BCrypt, with no third-party package."""
    if not sys.platform.startswith("win"):
        return None
    try:
        import ctypes
        import ctypes.wintypes as wt

        bcrypt = ctypes.windll.bcrypt

        class BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wt.ULONG),
                ("dwInfoVersion", wt.ULONG),
                ("pbNonce", ctypes.c_void_p),
                ("cbNonce", wt.ULONG),
                ("pbAuthData", ctypes.c_void_p),
                ("cbAuthData", wt.ULONG),
                ("pbTag", ctypes.c_void_p),
                ("cbTag", wt.ULONG),
                ("pbMacContext", ctypes.c_void_p),
                ("cbMacContext", wt.ULONG),
                ("cbAAD", wt.ULONG),
                ("cbData", ctypes.c_ulonglong),
                ("dwFlags", wt.ULONG),
            ]

        h_alg = ctypes.c_void_p()
        h_key = ctypes.c_void_p()
        key_buf = ctypes.create_string_buffer(key, len(key))
        nonce_buf = ctypes.create_string_buffer(nonce, len(nonce))
        tag_buf = ctypes.create_string_buffer(tag, len(tag))
        ct_buf = ctypes.create_string_buffer(ciphertext, len(ciphertext))
        out = ctypes.create_string_buffer(max(1, len(ciphertext)))
        out_len = wt.ULONG(0)

        if bcrypt.BCryptOpenAlgorithmProvider(ctypes.byref(h_alg), "AES", None, 0) != 0:
            return None
        try:
            mode = "ChainingModeGCM".encode("utf-16-le") + b"\x00\x00"
            mode_buf = ctypes.create_string_buffer(mode, len(mode))
            if bcrypt.BCryptSetProperty(
                h_alg, "ChainingMode", mode_buf, len(mode), 0
            ) != 0:
                return None
            if bcrypt.BCryptGenerateSymmetricKey(
                h_alg,
                ctypes.byref(h_key),
                None,
                0,
                key_buf,
                len(key),
                0,
            ) != 0:
                return None
            try:
                auth = BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO()
                auth.cbSize = ctypes.sizeof(auth)
                auth.dwInfoVersion = 1
                auth.pbNonce = ctypes.cast(nonce_buf, ctypes.c_void_p)
                auth.cbNonce = len(nonce)
                auth.pbTag = ctypes.cast(tag_buf, ctypes.c_void_p)
                auth.cbTag = len(tag)

                status = bcrypt.BCryptDecrypt(
                    h_key,
                    ct_buf,
                    len(ciphertext),
                    ctypes.byref(auth),
                    None,
                    0,
                    out,
                    len(ciphertext),
                    ctypes.byref(out_len),
                    0,
                )
                if status != 0:
                    return None
                return out.raw[:out_len.value]
            finally:
                if h_key:
                    bcrypt.BCryptDestroyKey(h_key)
        finally:
            if h_alg:
                bcrypt.BCryptCloseAlgorithmProvider(h_alg, 0)
    except Exception:
        return None


def _claude_desktop_safestorage_key(profile_dir: Path) -> bytes | None:
    """Get Claude Desktop's Chromium safeStorage key on Windows, read-only."""
    if not sys.platform.startswith("win"):
        return None
    try:
        import base64

        local_state = json.loads((profile_dir / "Local State").read_text(encoding="utf-8"))
        encrypted = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
        if not encrypted.startswith(b"DPAPI"):
            return None
        return _win_dpapi_unprotect(encrypted[5:])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _claude_desktop_decrypt(value: str, key: bytes) -> bytes | None:
    """Decrypt one Electron safeStorage base64 value on Windows."""
    try:
        import base64

        blob = base64.b64decode(value)
    except (ValueError, TypeError):
        return None

    if blob[:3] in (b"v10", b"v11"):
        payload = blob[3:]
        if len(payload) < 12 + 16:
            return None
        nonce = payload[:12]
        ciphertext_and_tag = payload[12:]
        return _win_gcm_decrypt(
            key,
            nonce,
            ciphertext_and_tag[:-16],
            ciphertext_and_tag[-16:],
        )

    # Older Electron/Chromium builds can store safeStorage values as raw DPAPI.
    return _win_dpapi_unprotect(blob)


def _claude_desktop_tokens() -> list[dict]:
    """Discover live OAuth access tokens maintained by Claude Desktop.

    The Desktop token cache is encrypted with Electron safeStorage. On Windows
    that ultimately uses the current user's DPAPI-protected Chromium key. We do
    not return refresh tokens and never write anything to the Desktop profile.
    """
    if not sys.platform.startswith("win"):
        return []

    import time

    candidates: list[dict] = []
    now = time.time()

    for profile_dir in _claude_desktop_dir_candidates():
        config_path = profile_dir / "config.json"
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(config, dict):
            continue

        key = _claude_desktop_safestorage_key(profile_dir)
        if not key:
            continue

        merged: dict = {}
        for cache_name in ("oauth:tokenCacheV2", "oauth:tokenCache"):
            encrypted = config.get(cache_name)
            if not isinstance(encrypted, str):
                continue
            raw = _claude_desktop_decrypt(encrypted, key)
            if not raw:
                continue
            try:
                decoded = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(decoded, dict):
                for cache_key, entry in decoded.items():
                    merged.setdefault(cache_key, entry)

        for cache_key, entry in merged.items():
            if not isinstance(cache_key, str) or not isinstance(entry, dict):
                continue
            if "api.anthropic.com" not in cache_key or "user:profile" not in cache_key:
                continue

            token = entry.get("token") or entry.get("accessToken")
            if not isinstance(token, str) or not token.strip():
                continue

            try:
                expires_at = float(entry.get("expiresAt") or 0)
            except (TypeError, ValueError):
                expires_at = 0
            if expires_at > 1_000_000_000_000:
                expires_at /= 1000.0
            if expires_at and expires_at <= now + CLAUDE_DESKTOP_TOKEN_SAFETY_SECONDS:
                continue

            full_scope = "user:inference" in cache_key
            production_client = CLAUDE_DESKTOP_CLIENT_ID in cache_key
            candidates.append({
                "access_token": token,
                "expires_at": expires_at,
                "subscription_type": entry.get("subscriptionType"),
                "rate_limit_tier": entry.get("rateLimitTier"),
                "source": "claude_desktop_oauth",
                "_rank": (
                    1 if production_client and full_scope else 0,
                    1 if full_scope else 0,
                    expires_at,
                ),
            })

    candidates.sort(key=lambda item: item["_rank"], reverse=True)
    for item in candidates:
        item.pop("_rank", None)
    return candidates


def get_claude_desktop_credentials() -> dict | None:
    """Return the healthiest live Claude Desktop OAuth access token, if any."""
    tokens = _claude_desktop_tokens()
    return tokens[0] if tokens else None


def _claude_desktop_detected() -> bool:
    """True when a Claude Desktop profile exists even if auth cannot be read."""
    for profile_dir in _claude_desktop_dir_candidates():
        if (profile_dir / "config.json").exists() or (profile_dir / "Local State").exists():
            return True
    return False

CLAUDE_LOCAL_USAGE_STALE_SECONDS = 30 * 60


def get_claude_cached_usage() -> dict | None:
    """Read Claude Code's own cached subscription quota without authentication.

    Claude Code writes the latest server-provided usage snapshot to the
    account-wide ~/.claude.json file under cachedUsageUtilization. Reading
    this file is zero-setup, read-only, and does not expose or refresh OAuth
    credentials. Only timestamped snapshots younger than the local freshness
    threshold are returned, so compact output cannot silently present stale or
    undated quota as live data.
    """
    state_paths = []

    if custom_state := os.environ.get("CLAUDE_CONFIG_JSON"):
        state_paths.append(Path(custom_state).expanduser())

    # Claude Code keeps this account-wide file at ~/.claude.json even when the
    # normal config directory is ~/.claude.
    state_paths.append(Path.home() / ".claude.json")

    # Tolerate custom profiles that explicitly colocate a state file.
    if config_dir := os.environ.get("CLAUDE_CONFIG_DIR"):
        state_paths.append(Path(config_dir).expanduser() / ".claude.json")

    seen = set()
    for state_path in state_paths:
        path_key = str(state_path)
        if path_key in seen:
            continue
        seen.add(path_key)

        try:
            root = json.loads(state_path.read_text())
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(root, dict):
            continue

        cached = root.get("cachedUsageUtilization")
        if not isinstance(cached, dict):
            continue
        utilization = cached.get("utilization")
        if not isinstance(utilization, dict):
            continue

        result: dict = {
            "status": "ok",
            "source": "claude_code_cache",
        }

        for source_key, result_key in (
            ("five_hour", "five_hour"),
            ("seven_day", "seven_day"),
            ("seven_day_opus", "opus"),
        ):
            window = utilization.get(source_key)
            if not isinstance(window, dict):
                continue
            used = window.get("utilization")
            if not isinstance(used, (int, float)):
                continue
            entry = {
                "used": f"{used:.1f}%",
                "remaining": f"{max(0.0, 100 - used):.1f}%",
            }
            if resets_at := window.get("resets_at"):
                entry["resets_at"] = resets_at
                entry["resets_in"] = format_reset_time(resets_at)
            result[result_key] = entry

        # A recognized cache with no numeric quota windows is not useful.
        if not any(key in result for key in ("five_hour", "seven_day", "opus")):
            continue

        fetched_at_ms = cached.get("fetchedAtMs")
        # Undated or stale local snapshots are not safe automatic fallbacks:
        # compact output must never present them as live/healthy quota.
        if not isinstance(fetched_at_ms, (int, float)) or fetched_at_ms <= 0:
            continue

        now_ms = datetime.now(timezone.utc).timestamp() * 1000
        age_seconds = max(0, int((now_ms - fetched_at_ms) / 1000))
        if age_seconds > CLAUDE_LOCAL_USAGE_STALE_SECONDS:
            continue

        result["source_age_seconds"] = age_seconds
        return result

    return None


def get_claude_usage() -> dict:
    """Fetch Claude subscription usage from an already-authenticated local source."""
    token = get_claude_credentials()
    source = "claude_code_oauth" if token else None
    desktop = None

    # Zero-config Desktop fallback. Borrow only a current access token from the
    # official app; never refresh or mutate Claude Desktop's credential store.
    if not token:
        desktop = get_claude_desktop_credentials()
        if desktop:
            token = desktop.get("access_token")
            source = "claude_desktop_oauth"

    if not token:
        # Claude Code itself may still have a recent server usage snapshot.
        if cached := get_claude_cached_usage():
            return cached

        if sys.platform.startswith("win") and _claude_desktop_detected():
            hint = (
                "Claude Desktop detected, but no readable live OAuth token was found. "
                "Keep Claude Desktop signed in and retry; no Claude CLI login is required."
            )
        elif sys.platform.startswith("win"):
            hint = "No existing Claude Code or readable Claude Desktop session was detected"
        else:
            hint = (
                "No existing Claude Code session was detected; "
                "Claude Desktop OAuth discovery is currently Windows-only"
            )
        return {
            "error": "No credentials found",
            "hint": hint,
        }

    headers = {
        "Authorization": f"Bearer {token}",
        "anthropic-beta": "oauth-2025-04-20",
        "Content-Type": "application/json",
    }

    status, data = http_get("https://api.anthropic.com/api/oauth/usage", headers)

    if status == 200 and isinstance(data, dict):
        result: dict = {"status": "ok"}
        if source:
            result["source"] = source
        if desktop:
            if desktop.get("subscription_type"):
                result["plan"] = desktop["subscription_type"]
            elif desktop.get("rate_limit_tier"):
                result["plan"] = desktop["rate_limit_tier"]

        if "five_hour" in data and data["five_hour"]:
            result["five_hour"] = {
                "used": f"{data['five_hour'].get('utilization', 0):.1f}%",
                "remaining": f"{100 - data['five_hour'].get('utilization', 0):.1f}%",
                "resets_at": data['five_hour'].get('resets_at'),
                "resets_in": format_reset_time(data['five_hour'].get('resets_at')),
            }

        if "seven_day" in data and data["seven_day"]:
            result["seven_day"] = {
                "used": f"{data['seven_day'].get('utilization', 0):.1f}%",
                "remaining": f"{100 - data['seven_day'].get('utilization', 0):.1f}%",
                "resets_at": data['seven_day'].get('resets_at'),
                "resets_in": format_reset_time(data['seven_day'].get('resets_at')),
            }

        if "seven_day_opus" in data and data["seven_day_opus"]:
            result["opus"] = {
                "used": f"{data['seven_day_opus'].get('utilization', 0):.1f}%",
            }

        return result
    elif status == 401:
        if source == "claude_desktop_oauth":
            if cached := get_claude_cached_usage():
                return cached
            return {
                "error": "Token expired",
                "hint": "Claude Desktop's cached access token is stale; keep Claude Desktop signed in and retry",
            }
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
    """Fetch Codex quota, preferring the native read-only app-server RPC.

    The direct ChatGPT usage endpoint remains a compatibility fallback for
    machines where Codex is absent, too old, or its app-server surface fails.
    """
    native = get_native_codex_usage()
    if isinstance(native, dict) and native.get("status") == "ok":
        return native

    native_error = native if isinstance(native, dict) else None
    creds = get_openai_credentials()

    if not creds.get("access_token") and not creds.get("api_key"):
        if native_error:
            return {
                "error": native_error.get("error", "Codex native quota unavailable"),
                "details": "Codex app-server did not return a usable quota snapshot",
                "hint": "Codex was detected but its native rate-limit snapshot was unavailable and no fallback credentials were found",
                "native_source": "codex_app_server",
            }
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
            result["source"] = "chatgpt_wham_fallback"
            if native_error:
                # The reason is useful provenance; low-level details may contain
                # local executable/profile paths and are not needed on success.
                result["native_fallback_reason"] = native_error.get("error")

            # Plan type
            if plan := data.get("plan_type"):
                result["plan"] = plan

            # Rate-limit windows. OpenAI does NOT guarantee primary=5h /
            # secondary=7d by slot position — free/reset accounts return a
            # single window, sometimes the weekly one in the primary slot
            # (quotio#356). Classify each window by its own duration instead:
            # <=24h -> session (5h) bucket, anything longer -> weekly (7d).
            if rate_limit := data.get("rate_limit", {}):
                for raw in (rate_limit.get("primary_window"),
                            rate_limit.get("secondary_window")):
                    if not raw:
                        continue
                    win_secs = raw.get("limit_window_seconds", 0)
                    used = raw.get("used_percent", 0)
                    reset_secs = raw.get("reset_after_seconds", 0)
                    reset_at = raw.get("reset_at")
                    resets_in = None
                    if win_secs and win_secs <= 86400:
                        key = "primary_window"
                        window_label = f"{win_secs // 3600}h"
                        if reset_secs > 0:
                            hours, remainder = divmod(reset_secs, 3600)
                            minutes = remainder // 60
                            resets_in = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                    else:
                        key = "secondary_window"
                        window_label = f"{win_secs // 86400}d" if win_secs else "7d"
                        if reset_secs > 0:
                            days, remainder = divmod(reset_secs, 86400)
                            hours = remainder // 3600
                            resets_in = f"{days}d {hours}h" if days > 0 else f"{hours}h"
                    entry = {
                        "used": f"{used}%",
                        "remaining": f"{100 - used}%",
                        "window": window_label,
                        "window_duration_minutes": (
                            win_secs // 60 if isinstance(win_secs, (int, float)) and win_secs > 0 else None
                        ),
                    }
                    if isinstance(reset_at, (int, float)) and reset_at > 0:
                        entry["resets_at"] = (
                            datetime.fromtimestamp(reset_at, tz=timezone.utc)
                            .isoformat()
                            .replace("+00:00", "Z")
                        )
                    if resets_in:
                        entry["resets_in"] = resets_in
                    result[key] = entry

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
            result["source"] = "openai_api_key_fallback"
            result["api_key_valid"] = True
            if native_error:
                result["native_fallback_reason"] = native_error.get("error")
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


# Z.AI peak window (docs.z.ai/devpack/overview + /devpack/notice/usage-revision):
# Mon-Fri 14:00-18:00 UTC+8 = 06:00-10:00 UTC; weekends are off-peak all day.
# Quota-based plans burn 3x peak / 1x off-peak on GLM-5.2/5-Turbo; the newer
# credits-based plans use 1x peak / 0.5x off-peak. Not exposed by any API endpoint.
ZAI_PEAK_START_UTC = 6
ZAI_PEAK_END_UTC = 10


def zai_quota_rate(now: datetime | None = None) -> dict:
    """Compute Z.AI peak/off-peak status and quota multiplier client-side."""
    now = now or datetime.now(timezone.utc)
    is_peak = now.weekday() < 5 and ZAI_PEAK_START_UTC <= now.hour < ZAI_PEAK_END_UTC

    if is_peak:
        multiplier = "3x"
        boundary = now.replace(hour=ZAI_PEAK_END_UTC, minute=0, second=0, microsecond=0)
    else:
        multiplier = "1x"
        boundary = now.replace(hour=ZAI_PEAK_START_UTC, minute=0, second=0, microsecond=0)
        if now.hour >= ZAI_PEAK_START_UTC:
            boundary += timedelta(days=1)
        while boundary.weekday() >= 5:
            boundary += timedelta(days=1)

    hours, remainder = divmod(int((boundary - now).total_seconds()), 3600)
    return {
        "peak": is_peak,
        "multiplier": multiplier,
        "changes_in": f"{hours}h {remainder // 60}m",
    }


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
                # Monthly quota for MCP tools (Web Search / Web Reader / Zread),
                # separate from the 5h GLM token pool
                total = limit.get("usage", 0)
                used = limit.get("currentValue", 0)
                remaining = limit.get("remaining", 0)

                result["mcp_quota"] = {
                    "limit": total,
                    "used": used,
                    "remaining": remaining,
                }

                if tools := limit.get("usageDetails"):
                    result["mcp_quota"]["tools"] = {
                        t["modelCode"]: t["usage"] for t in tools
                        if t.get("modelCode") is not None
                    }

                if reset_ts := limit.get("nextResetTime"):
                    try:
                        delta = datetime.fromtimestamp(reset_ts / 1000) - datetime.now()
                        if delta.total_seconds() > 0:
                            days, remainder = divmod(int(delta.total_seconds()), 86400)
                            hours = remainder // 3600
                            result["mcp_quota"]["resets_in"] = f"{days}d {hours}h"
                    except:
                        pass

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

    if result.get("status") == "ok":
        result["quota_rate"] = zai_quota_rate()

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


def _earliest_antigravity_reset(models: list[dict]) -> str | None:
    """Earliest parseable reset_time ISO string across models (next bucket to refill)."""
    parsed = []
    for m in models:
        ts = m.get("reset_time")
        if not ts:
            continue
        try:
            parsed.append((datetime.fromisoformat(ts.replace('Z', '+00:00')), ts))
        except ValueError:
            continue
    return min(parsed, key=lambda p: p[0])[1] if parsed else None


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
        if earliest := _earliest_antigravity_reset(models):
            summary["next_reset_in"] = format_reset_time(earliest)
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


### GitHub Copilot Functions

def _copilot_token_from_json(path: Path) -> str | None:
    """Extract a github.com oauth_token from a Copilot editor credential file
    (apps.json keys look like "github.com:Iv1.xxx", hosts.json uses bare
    "github.com")."""
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    for host_key, entry in data.items():
        if "github.com" in host_key and isinstance(entry, dict):
            if token := entry.get("oauth_token"):
                return token
    return None


def _copilot_token_from_gh_hosts(path: Path) -> str | None:
    """Extract the github.com oauth_token from the gh CLI hosts.yml.
    Parsed by indentation to avoid a YAML dependency; the token may be
    absent when gh keeps it in the system keyring."""
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return None
    in_github = False
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith((" ", "\t")):
            in_github = line.split(":")[0].strip().strip('"') == "github.com"
            continue
        if in_github and (stripped := line.strip()).startswith("oauth_token:"):
            return stripped.split(":", 1)[1].strip().strip("\"'") or None
    return None


def get_copilot_credentials() -> dict | None:
    """Find a GitHub token for the Copilot quota check.

    Copilot editor plugin files first (their OAuth app tokens are what the
    plugins themselves send), then the gh CLI config, then env vars.
    Returns {"token", "source"} or None.
    """
    copilot_dir = Path.home() / ".config" / "github-copilot"
    for name in ["apps.json", "hosts.json"]:
        if token := _copilot_token_from_json(copilot_dir / name):
            return {"token": token, "source": f"~/.config/github-copilot/{name}"}
    if token := _copilot_token_from_gh_hosts(Path.home() / ".config" / "gh" / "hosts.yml"):
        return {"token": token, "source": "gh CLI (hosts.yml)"}
    for var in ["GITHUB_TOKEN", "GH_TOKEN"]:
        if token := os.environ.get(var):
            return {"token": token, "source": f"${var}"}
    return None


def get_copilot_usage() -> dict:
    """Fetch GitHub Copilot premium-request quota.

    Uses the undocumented endpoint the Copilot editor plugins read
    (api.github.com/copilot_internal/user); the check itself consumes no
    premium requests.
    """
    creds = get_copilot_credentials()
    if not creds:
        return {
            "error": NO_CREDS_ERROR,
            "hint": "Sign in to a Copilot editor/CLI or set GITHUB_TOKEN",
        }

    headers = {
        "Authorization": f"Bearer {creds['token']}",
        "Accept": "application/json",
        "Editor-Version": "vscode/1.96.0",
    }
    status, data = http_get("https://api.github.com/copilot_internal/user", headers)

    if status == 401:
        return {"error": "Invalid API key",
                "hint": f"GitHub token from {creds['source']} was rejected"}
    if status in (403, 404):
        return {
            "error": COPILOT_NO_SUB_ERROR,
            "hint": f"Token from {creds['source']} has no Copilot access "
                    "(no subscription, or token type not accepted)",
            "dashboard": "https://github.com/settings/copilot",
        }
    if status != 200 or not isinstance(data, dict):
        return {
            "error": f"API error (HTTP {status})",
            "details": data if isinstance(data, str) else json.dumps(data)[:200],
        }

    result: dict = {"status": "ok", "auth": creds["source"]}
    if login := data.get("login"):
        result["account"] = login
    if plan := data.get("copilot_plan"):
        result["plan"] = plan

    snapshots = data.get("quota_snapshots") or {}
    premium = snapshots.get("premium_interactions")
    if isinstance(premium, dict):
        pr: dict = {}
        if premium.get("unlimited"):
            pr["unlimited"] = True
        else:
            entitlement = int(premium.get("entitlement") or 0)
            remaining = max(0, int(premium.get("remaining") or 0))
            used = max(0, entitlement - remaining)
            if premium.get("percent_remaining") is not None:
                pct = max(0, min(100, int(round(100 - float(premium["percent_remaining"])))))
            else:
                pct = int(round(used / entitlement * 100)) if entitlement else 0
            pr.update({
                "used": used,
                "entitlement": entitlement,
                "remaining": remaining,
                "percentage": pct,
            })
            if overage := int(premium.get("overage_count") or 0):
                pr["overage_count"] = overage
        reset_iso = data.get("quota_reset_date_utc") or (
            f"{data['quota_reset_date']}T00:00:00Z" if data.get("quota_reset_date") else ""
        )
        if resets := _format_resets_in(reset_iso):
            pr["resets_in"] = resets
        if data.get("quota_reset_date"):
            pr["reset_date"] = data["quota_reset_date"]
        result["premium_requests"] = pr

    unlimited = sorted(
        key for key, snap in snapshots.items()
        if key != "premium_interactions" and isinstance(snap, dict) and snap.get("unlimited")
    )
    if unlimited:
        result["unlimited_buckets"] = unlimited

    result["dashboard_url"] = "https://github.com/settings/copilot/features"
    return result


def print_section(name: str, data: dict):
    """Pretty print a section"""
    print(f"\n{'='*50}")
    print(f"  {name}")
    print('='*50)

    # Show auth info first if available
    if "auth" in data:
        print(f"  🔑 Auth: {data['auth']}")
    if data.get("source") == "codex_app_server":
        print("  📍 Source: Codex native app-server RPC (read-only)")
    if "account" in data:
        print(f"  👤 Account: {data['account']}")
    if "api_key_valid" in data:
        print(f"  🔑 API Key: valid")

    # Show status
    if data.get("status") == "ok":
        print("  ✅ Connected")
    elif data.get("status") == "authenticated":
        print("  ✅ Authenticated")

    # Stale-cache fallback notice
    if "stale_fallback" in data:
        age = data.get("stale_age_seconds", 0)
        print(f"  💤 Stale fallback (last good: {format_cache_age(age)} ago)")

    # Claude can provide quota from already-authenticated local apps without setup.
    if data.get("source") == "claude_desktop_oauth":
        print("  📍 Source: Claude Desktop OAuth (read-only)")
    elif data.get("source") == "claude_code_oauth":
        print("  📍 Source: Claude Code OAuth")

    # Claude Code can also provide quota without credentials via its own local cache.
    if data.get("source") == "claude_code_cache":
        age = data.get("source_age_seconds")
        age_text = f" ({format_cache_age(age)} old)" if isinstance(age, int) else ""
        stale_text = " [stale]" if data.get("source_stale") else ""
        print(f"  📍 Source: Claude Code local usage cache{age_text}{stale_text}")

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

    if "reset_credits_available" in data:
        print(f"  ♻️  Reset credits available: {data['reset_credits_available']} (read-only)")

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
        if "next_reset_in" in summary:
            print(f"    Next reset: {summary['next_reset_in']}")
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

    if "quota_rate" in data:
        qr = data["quota_rate"]
        if qr["peak"]:
            print(f"\n  Quota Rate: ⚡ {qr['multiplier']} peak — ends in {qr['changes_in']}")
        else:
            print(f"\n  Quota Rate: {qr['multiplier']} off-peak — peak in {qr['changes_in']}")

    if "mcp_quota" in data:
        rq = data["mcp_quota"]
        if rq.get("limit"):
            print(f"\n  MCP Tools (monthly):")
            print(f"    Used:      {rq['used']:,} / {rq['limit']:,}")
            print(f"    Remaining: {rq['remaining']:,}")
            if "resets_in" in rq:
                print(f"    Resets in: {rq['resets_in']}")
            for tool, count in rq.get("tools", {}).items():
                print(f"      {tool}: {count:,}")

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

    # GitHub Copilot premium requests (monthly)
    if "premium_requests" in data:
        pr = data["premium_requests"]
        print(f"\n  Premium Requests (monthly):")
        if pr.get("unlimited"):
            print(f"    Unlimited")
        else:
            print(f"    Used:      {pr.get('used', 0):,} / {pr.get('entitlement', 0):,} ({pr.get('percentage', 0)}%)")
            print(f"    Remaining: {pr.get('remaining', 0):,}")
            if pr.get("overage_count"):
                print(f"    Overage:   {pr['overage_count']:,}")
        if "resets_in" in pr:
            date_note = f" ({pr['reset_date']})" if pr.get("reset_date") else ""
            print(f"    Resets in: {pr['resets_in']}{date_note}")
        if data.get("unlimited_buckets"):
            print(f"    ({', '.join(data['unlimited_buckets'])}: unlimited)")

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


# Shared oneline formatting helpers

def _reset_suffix(*resets):
    """Compact '↻a/b' suffix from reset strings; None if nothing usable."""
    vals = [r.replace(" ", "") for r in resets if r and r != "N/A"]
    return f"↻{'/'.join(vals)}" if vals else None


def _fmt_both(label, s5, s7, use_color):
    """Dual-window: 'Label: X%/Y% <icon>'"""
    m = max(float(s5), float(s7))
    d = f"{s5}%/{s7}%"
    return f"{label}: {colorize_pct(d, m)}" if use_color else f"{label}: {d} {get_status_icon(m)}"


def _fmt_single(label, inner, pct, suffix, use_color):
    """Single window; *suffix* goes outside the color span."""
    if use_color:
        s = f"{label}: {colorize_pct(inner, pct)}"
        return f"{s} {suffix}" if suffix else s
    if suffix:
        return f"{label}: {inner} {suffix} {get_status_icon(pct)}"
    return f"{label}: {inner} {get_status_icon(pct)}"


def _fmt_balance(label, balance_str, balance, use_color):
    """Prepaid-balance line with shared threshold ladder."""
    if use_color:
        c = COLORS['bold_red'] if balance <= 0 else COLORS['red'] if balance < 1.0 else COLORS['yellow'] if balance < 5.0 else COLORS['green']
        return f"{label}: {c}{balance_str}{COLORS['reset']}"
    return f"{label}: {balance_str} {'❌' if balance <= 0 else '🔴' if balance < 1.0 else '⚠️' if balance < 5.0 else '✅'}"


# Per-provider oneline renderers

def _make_str_pct_renderer(label, ok_check, w5_key, w7d_key):
    """Factory for Claude/Codex-style percent-dual renderers (string percents)."""
    def _r(data, window, use_color, show_resets=False):
        if not ok_check(data):
            return None
        has5, has7 = w5_key in data, w7d_key in data
        if window == "both" and has5 and has7:
            s = _fmt_both(label, data[w5_key]["used"].rstrip("%"), data[w7d_key]["used"].rstrip("%"), use_color)
            if show_resets and (suf := _reset_suffix(data[w5_key].get("resets_in"), data[w7d_key].get("resets_in"))):
                s += f" {suf}"
            return s
        # Single-window (or degraded `both`): render whichever window exists,
        # preferring the requested one but falling back so a provider that
        # only exposes one window (e.g. Codex weekly-only) still shows up.
        order = [w7d_key, w5_key] if window == "7d" else [w5_key, w7d_key]
        for key in order:
            if key in data:
                s = data[key]["used"]
                suffix = "(7d)" if key == w7d_key else "(5h)"
                out = _fmt_single(label, s, float(s.rstrip("%")), suffix, use_color)
                if show_resets and (suf := _reset_suffix(data[key].get("resets_in"))):
                    out += f" {suf}"
                return out
        return None
    return _r


def _make_balance_renderer(label, ok_key, get_balance):
    """Factory for OpenRouter/Kimi-style balance renderers."""
    def _r(data, window, use_color, show_resets=False):
        if not (data.get("status") == "ok" and ok_key in data):
            return None
        bal, s = get_balance(data)
        return _fmt_balance(label, s, bal, use_color)
    return _r


def _render_zai(data, window, use_color, show_resets=False):
    if not (data.get("status") == "ok" and "token_quota" in data):
        return None
    pct = data["token_quota"].get("percentage", 0)
    rq = data.get("mcp_quota", {})
    if window == "both" and rq.get("limit"):
        s = _fmt_both("Z.AI", str(pct), str(round(rq.get("used", 0) / rq["limit"] * 100)), use_color)
        resets = (data["token_quota"].get("resets_in"), rq.get("resets_in"))
    else:
        s = _fmt_single("Z.AI", f"{pct}% (5h)", pct, "", use_color)
        resets = (data["token_quota"].get("resets_in"),)
    if data.get("quota_rate", {}).get("peak"):
        s += " 3x" if use_color else " ⚡3x"
    if show_resets and (suf := _reset_suffix(*resets)):
        s += f" {suf}"
    return s


def _render_synthetic(data, window, use_color, show_resets=False):
    if data.get("status") != "ok":
        return None
    p5 = data.get("rolling_5h", {}).get("percentage")
    p7 = data.get("weekly_credits", {}).get("percent_used")
    r5 = data.get("rolling_5h", {}).get("next_tick_in")
    r7 = data.get("weekly_credits", {}).get("next_regen_in")
    if window == "both" and p5 is not None and p7 is not None:
        s, resets = _fmt_both("Synthetic", str(p5), str(p7), use_color), (r5, r7)
    elif window == "7d" and p7 is not None:
        s, resets = _fmt_single("Synthetic", f"{p7}% (7d)", float(p7), "", use_color), (r7,)
    elif p5 is not None:
        s, resets = _fmt_single("Synthetic", f"{p5}% (5h)", float(p5), "", use_color), (r5,)
    else:
        return None
    if show_resets and (suf := _reset_suffix(*resets)):
        s += f" {suf}"
    return s


def _render_gemini(data, window, use_color, show_resets=False):
    if not (data.get("status") == "ok" and "models" in data):
        return None
    parts = []
    for tier in ["3-Flash", "Flash", "Pro"]:
        for mid in GEMINI_TIERS.get(tier, []):
            if mid in data["models"]:
                s = data["models"][mid]["used"]
                p = float(s.rstrip("%"))
                part = f"{tier} {colorize_pct(s, p)}" if use_color else f"{tier} {s} {get_status_icon(p)}"
                if show_resets and (suf := _reset_suffix(data["models"][mid].get("resets_in"))):
                    part += f" {suf}"
                parts.append(part)
                break
    return f"Gemini: ( {' | '.join(parts)} )" if parts else None


def _render_antigravity(data, window, use_color, show_resets=False):
    if not (data.get("status") == "ok" and "summary" in data):
        return None
    s = data["summary"]
    used = max(0, 100 - int(s.get("min_remaining_pct", 0)))
    mc = int(s.get("model_count", 0))
    if use_color:
        out = f"Antigravity: {colorize_pct(f'{used}%', used)} ({mc} models)"
    else:
        out = f"Antigravity: {used}% ({mc} models) {get_status_icon(used)}"
    if show_resets and (suf := _reset_suffix(s.get("next_reset_in"))):
        out += f" {suf}"
    return out


def _render_copilot(data, window, use_color, show_resets=False):
    if data.get("status") != "ok" or "premium_requests" not in data:
        return None
    pr = data["premium_requests"]
    if pr.get("unlimited"):
        return _fmt_single("Copilot", "∞ (mo)", 0.0, "", use_color)
    pct = pr.get("percentage", 0)
    s = _fmt_single("Copilot", f"{pct}% (mo)", float(pct), "", use_color)
    if show_resets and (suf := _reset_suffix(pr.get("resets_in"))):
        s += f" {suf}"
    return s


# Provider registry — single source of truth.  Adding a provider: one entry
# here + a fetch function (+ a custom renderer if the shared ones don't fit).

PROVIDERS = [
    {"key": "claude", "title": "Claude Code", "oneline_label": "Claude",
     "arg_help": "Only check Claude Code (Claude Desktop OAuth auto-discovery on Windows)", "fetch": "get_claude_usage",
     "gated": False, "creds": None, "oneline_order": 0,
     "render_oneline": _make_str_pct_renderer("Claude", lambda d: d.get("status") == "ok" or "five_hour" in d, "five_hour", "seven_day")},
    {"key": "codex", "title": "OpenAI Codex", "oneline_label": "Codex",
     "arg_help": "Only check Codex", "fetch": "get_codex_usage",
     "gated": False, "creds": None, "oneline_order": 1,
     "render_oneline": _make_str_pct_renderer("Codex", lambda d: d.get("status") == "ok", "primary_window", "secondary_window")},
    {"key": "gemini", "title": "Gemini CLI", "oneline_label": "Gemini",
     "arg_help": "Only check Gemini", "fetch": "get_gemini_usage",
     "gated": False, "creds": None, "oneline_order": 4,
     "render_oneline": _render_gemini},
    {"key": "zai", "title": "Z.AI (5h shared - GLM-4.x)", "oneline_label": "Z.AI",
     "arg_help": "Only check Z.AI", "fetch": "get_zai_usage",
     "gated": False, "creds": None, "oneline_order": 2,
     "render_oneline": _render_zai},
    {"key": "openrouter", "title": "OpenRouter", "oneline_label": "OpenRouter",
     "arg_help": "Only check OpenRouter", "fetch": "get_openrouter_usage",
     "gated": True, "creds": "get_openrouter_credentials", "oneline_order": 5,
     "render_oneline": _make_balance_renderer("OpenRouter", "balance_usd", lambda d: (d["balance_usd"], f"${d['balance_usd']:.2f}"))},
    {"key": "kimi", "title": "Kimi K2 (Moonshot AI)", "oneline_label": "Kimi",
     "arg_help": "Only check Kimi (Moonshot AI)", "fetch": "get_kimi_usage",
     "gated": True, "creds": "get_kimi_credentials", "oneline_order": 6,
     "render_oneline": _make_balance_renderer("Kimi", "balance", lambda d: (d["balance"], f"{'$' if d.get('currency', 'USD') == 'USD' else '¥'}{d['balance']:.2f}"))},
    {"key": "antigravity", "title": "Google Antigravity", "oneline_label": "Antigravity",
     "arg_help": "Only check Google Antigravity", "fetch": "get_antigravity_usage",
     "gated": True, "creds": "get_antigravity_credentials", "oneline_order": 7,
     "render_oneline": _render_antigravity},
    {"key": "synthetic", "title": "Synthetic.new", "oneline_label": "Synthetic",
     "arg_help": "Only check Synthetic.new", "fetch": "get_synthetic_usage",
     "gated": True, "creds": "get_synthetic_credentials", "oneline_order": 3,
     "render_oneline": _render_synthetic},
    {"key": "copilot", "title": "GitHub Copilot", "oneline_label": "Copilot",
     "arg_help": "Only check GitHub Copilot", "fetch": "get_copilot_usage",
     "gated": True, "creds": "get_copilot_credentials", "oneline_order": 8,
     "render_oneline": _render_copilot},
]


def print_oneline(results: dict, window: str = "5h", use_color: bool = False, cache_age: int | None = None,
                  show_resets: bool = False):
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

    for p in sorted(PROVIDERS, key=lambda p: p["oneline_order"]):
        key = p["key"]
        if key not in results:
            continue
        data = results[key]
        rendered = p["render_oneline"](data, window, use_color, show_resets)
        if rendered is not None:
            if "stale_fallback" in data:
                age = data.get("stale_age_seconds", 0)
                tag = f"(stale {format_cache_age(age)})"
                if use_color:
                    tag = f"{COLORS['yellow']}{tag}{COLORS['reset']}"
                rendered = f"{rendered} {tag}"
            parts.append(rendered)
        elif "error" in data or data.get("token_status") == "expired":
            parts.append(f"{p['oneline_label']}: {fail_icon(data)}")

    line = " | ".join(parts)
    if cache_age is not None:
        line += f" (cached {format_cache_age(cache_age)})"
    print(line)


def main():
    import argparse

    epilog = """
Credential Locations (auto-discovered):
  Claude     ~/.claude.json cached usage (fresh snapshots only)
              ~/.claude/.credentials.json (Linux)
              macOS Keychain "Claude Code-credentials" (macOS)
              Claude Desktop OAuth (Windows only, read-only; standard + MSIX profiles)
  Codex      ~/.codex/auth.json
  Gemini     ~/.gemini/oauth_creds.json (auto-refreshes expired tokens)
  Z.AI       $ZAI_KEY or $ZAI_API_KEY environment variable
  OpenRouter $OPENROUTER_API_KEY environment variable
  Kimi       $MOONSHOT_API_KEY environment variable
  Antigravity system keyring, or $ANTIGRAVITY_REFRESH_TOKEN
  Synthetic  $SYNTHETIC_API_KEY environment variable
  Copilot    ~/.config/github-copilot/apps.json, gh CLI hosts.yml, or $GITHUB_TOKEN

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
  cclimits --copilot    # GitHub Copilot only
  cclimits --json       # JSON output
  cclimits --oneline      # Compact one-liner (5h window)
  cclimits --oneline 7d   # Compact one-liner (7d window)
  cclimits --oneline both # Compact one-liner (5h/7d window)
  cclimits --oneline both --resets  # One-liner with reset countdowns (↻3h24m/4d12h)

Example Output:
  # One-liner (5h window)
  Claude: 4.0% (5h) ✅ | Codex: 0% (5h) ✅ | Z.AI: 1% (5h) ✅ | Gemini: ( 3-Flash 7% ✅ ... ) | Kimi: $49.59 ✅ | Antigravity: 65% (8 models) ✅ | Synthetic: 0% (5h) ✅
"""

    parser = argparse.ArgumentParser(
        description="Check AI CLI usage/quota for Claude, Codex, Gemini, Z.AI, OpenRouter, Kimi, Antigravity, Synthetic.new, GitHub Copilot",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--oneline", nargs="?", const="5h", metavar="WINDOW",
                        help="Compact one-liner output (5h, 7d, or both; default: 5h)")
    parser.add_argument("--noemoji", action="store_true",
                        help="Use colored text instead of emojis (for terminals without emoji support)")
    parser.add_argument("--resets", "--timeremaining", action="store_true", dest="resets",
                        help="Append reset countdowns (↻2h15m) to --oneline output")
    for _p in PROVIDERS:
        parser.add_argument(f"--{_p['key']}", action="store_true", help=_p["arg_help"])
    parser.add_argument("--cached", action="store_true", help="Use cached data if fresh (< TTL), fetch if stale")
    parser.add_argument("--cache-ttl", type=int, metavar="SECONDS",
                        help="Override default TTL (default: 60, implies --cached)")
    parser.add_argument("--no-stale-fallback", action="store_true",
                        help="Disable stale-cache fallback for transient API errors")
    parser.add_argument("--no-cache-write", action="store_true",
                        help="Do not write fetched results to the local cache")
    args = parser.parse_args()

    # Determine cache settings
    use_cache = args.cached or args.cache_ttl is not None
    cache_ttl = args.cache_ttl if args.cache_ttl is not None else DEFAULT_CACHE_TTL

    # Which providers were explicitly requested (empty = check all)
    requested = [p["key"] for p in PROVIDERS if getattr(args, p["key"])]
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

        # Build the work list from the PROVIDERS registry.
        # Credential discovery for gated providers runs before submission
        # so that check_all without credentials simply omits the provider.
        # The actual HTTP fetches then run concurrently in a thread pool so
        # the total wall time approximates the slowest single provider
        # rather than the sum.
        work: list[tuple[str, Callable[[], dict]]] = []

        for p in PROVIDERS:
            pkey = p["key"]
            if p["gated"]:
                cred_fn = globals()[p["creds"]]
                if getattr(args, pkey) or (check_all and cred_fn()):
                    work.append((pkey, globals()[p["fetch"]]))
            else:
                if check_all or getattr(args, pkey):
                    work.append((pkey, globals()[p["fetch"]]))

        if work:
            with ThreadPoolExecutor(max_workers=len(work)) as executor:
                future_map = {
                    name: executor.submit(fn) for name, fn in work
                }
                # Collect results in canonical provider order, not
                # completion order, so output (especially --json key
                # order) is deterministic.
                for p in PROVIDERS:
                    if p["key"] in future_map:
                        try:
                            results[p["key"]] = future_map[p["key"]].result()
                        except Exception as exc:
                            results[p["key"]] = {"error": str(exc)}

        # Read stale cache BEFORE writing so the fallback age reflects the
        # previous good entry, not the write we're about to do.  Bounded by
        # STALE_CACHE_MAX_AGE (ignores normal TTL).
        stale_cached = None
        if not args.no_stale_fallback:
            stale_cached = read_cache(cache_ttl, max_age=STALE_CACHE_MAX_AGE)

        # Write cache for future --cached calls unless a read-only embedding
        # explicitly disables it.  This lets tools such as Token Harness invoke
        # cclimits as a pure observer without changing ~/.cache/cclimits.
        if not args.no_cache_write:
            write_cache(results)

        # Apply stale-cache fallback: replace transient errors with the
        # last good cached entry (annotated with its age).
        if stale_cached is not None:
            cached_data, cached_age = stale_cached
            results = apply_stale_fallback(results, cached_data, cached_age)

    # Gemini CLI was retired upstream (2026-06), so an expired OAuth token
    # generally can't be refreshed and missing credentials can't be recreated
    # — a perpetual ⏰/🔑 row is noise.  Hide it from check-all display
    # output; explicit --gemini and --json still surface the real state
    # (and the cache keeps the full data).
    gem = results.get("gemini", {})
    if check_all and not args.json and (
        gem.get("token_status") == "expired" or gem.get("error") == NO_CREDS_ERROR
    ):
        del results["gemini"]

    # A GITHUB_TOKEN on a box whose account has no Copilot subscription is
    # common (CI, non-Copilot users) — that permanent state would be noise
    # in check-all display output.  Explicit --copilot and --json still
    # surface it.
    if check_all and not args.json and results.get("copilot", {}).get("error") == COPILOT_NO_SUB_ERROR:
        del results["copilot"]

    if args.json:
        print(json.dumps(results, indent=2))
    elif args.oneline:
        window = args.oneline if args.oneline in ("5h", "7d", "both") else "5h"
        print_oneline(results, window, use_color=args.noemoji, cache_age=cache_age, show_resets=args.resets)
    else:
        print("\n🔍 AI CLI Usage Checker")
        cached_note = f"  (cached {format_cache_age(cache_age)} ago)" if cache_age is not None else ""
        print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{cached_note}")

        for p in PROVIDERS:
            if p["key"] in results:
                print_section(p["title"], results[p["key"]])

        print("\n" + "="*50)
        print("  Done!")
        print("="*50 + "\n")


if __name__ == "__main__":
    main()
