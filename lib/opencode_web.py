"""Read-only OpenCode web-session discovery and Zen billing retrieval.

This module intentionally targets only the OpenCode authentication cookie and
never exports the browser cookie jar. It supports Firefox directly and
Chromium-family browsers on Linux using the existing OS keyring / Safe Storage
secret when available.

No login is initiated and browser profiles are never modified.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.parse
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

OPENCODE_BASE_URL = "https://opencode.ai"
OPENCODE_SERVER_URL = "https://opencode.ai/_server"
OPENCODE_WORKSPACES_SERVER_ID = "def39973159c7f0483d8793a822b8dbb10d067e12c65455fcb4608459ba0234f"
OPENCODE_BILLING_SERVER_ID = "c83b78a614689c38ebee981f9b39a8b377716db85c1fd7dbab604adc02d3313d"
OPENCODE_COOKIE_NAMES = ("__Host-auth", "auth")
OPENCODE_COOKIE_HOSTS = ("opencode.ai", ".opencode.ai")
CHROMIUM_EPOCH_OFFSET_SECONDS = 11644473600
ZEN_USD_SCALE = 100_000_000.0
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class _ChromiumSpec:
    name: str
    os_crypt_name: str
    patterns: tuple[str, ...]


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = os.path.normcase(os.path.abspath(str(path)))
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def _expand_cookie_patterns(patterns: tuple[str, ...]) -> list[Path]:
    result: list[Path] = []
    for raw in patterns:
        expanded = os.path.expanduser(raw)
        result.extend(Path(item) for item in sorted(glob.glob(expanded)))
    return _dedupe_paths([path for path in result if path.is_file()])


def _chromium_specs() -> list[_ChromiumSpec]:
    return [
        _ChromiumSpec(
            "chrome",
            "chrome",
            (
                "~/.config/google-chrome*/Default/Network/Cookies",
                "~/.config/google-chrome*/Default/Cookies",
                "~/.config/google-chrome*/Profile */Network/Cookies",
                "~/.config/google-chrome*/Profile */Cookies",
                "~/.var/app/com.google.Chrome/config/google-chrome*/Default/Network/Cookies",
                "~/.var/app/com.google.Chrome/config/google-chrome*/Default/Cookies",
                "~/.var/app/com.google.Chrome/config/google-chrome*/Profile */Network/Cookies",
                "~/.var/app/com.google.Chrome/config/google-chrome*/Profile */Cookies",
            ),
        ),
        _ChromiumSpec(
            "chromium",
            "chromium",
            (
                "~/.config/chromium/Default/Network/Cookies",
                "~/.config/chromium/Default/Cookies",
                "~/.config/chromium/Profile */Network/Cookies",
                "~/.config/chromium/Profile */Cookies",
                "~/snap/chromium/common/chromium/Default/Network/Cookies",
                "~/snap/chromium/common/chromium/Default/Cookies",
                "~/snap/chromium/common/chromium/Profile */Network/Cookies",
                "~/snap/chromium/common/chromium/Profile */Cookies",
                "~/.var/app/org.chromium.Chromium/config/chromium/Default/Network/Cookies",
                "~/.var/app/org.chromium.Chromium/config/chromium/Default/Cookies",
                "~/.var/app/org.chromium.Chromium/config/chromium/Profile */Network/Cookies",
                "~/.var/app/org.chromium.Chromium/config/chromium/Profile */Cookies",
            ),
        ),
        _ChromiumSpec(
            "brave",
            "brave",
            (
                "~/.config/BraveSoftware/Brave-Browser*/Default/Network/Cookies",
                "~/.config/BraveSoftware/Brave-Browser*/Default/Cookies",
                "~/.config/BraveSoftware/Brave-Browser*/Profile */Network/Cookies",
                "~/.config/BraveSoftware/Brave-Browser*/Profile */Cookies",
                "~/.var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser*/Default/Network/Cookies",
                "~/.var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser*/Default/Cookies",
            ),
        ),
        _ChromiumSpec(
            "edge",
            "chromium",
            (
                "~/.config/microsoft-edge*/Default/Network/Cookies",
                "~/.config/microsoft-edge*/Default/Cookies",
                "~/.config/microsoft-edge*/Profile */Network/Cookies",
                "~/.config/microsoft-edge*/Profile */Cookies",
                "~/.var/app/com.microsoft.Edge/config/microsoft-edge*/Default/Network/Cookies",
                "~/.var/app/com.microsoft.Edge/config/microsoft-edge*/Default/Cookies",
            ),
        ),
        _ChromiumSpec(
            "vivaldi",
            "chrome",
            (
                "~/.config/vivaldi*/Default/Network/Cookies",
                "~/.config/vivaldi*/Default/Cookies",
                "~/.config/vivaldi*/Profile */Network/Cookies",
                "~/.config/vivaldi*/Profile */Cookies",
            ),
        ),
    ]


def _firefox_cookie_paths() -> list[Path]:
    patterns = (
        "~/.mozilla/firefox/*/cookies.sqlite",
        "~/snap/firefox/common/.mozilla/firefox/*/cookies.sqlite",
        "~/.var/app/org.mozilla.firefox/.mozilla/firefox/*/cookies.sqlite",
    )
    return _expand_cookie_patterns(patterns)


class _SQLiteSnapshot:
    """Open a browser SQLite DB read-only, copying it only when needed."""

    def __init__(self, path: Path):
        self.path = path
        self.conn: sqlite3.Connection | None = None
        self.tmpdir: tempfile.TemporaryDirectory | None = None

    def __enter__(self) -> sqlite3.Connection:
        uri = self.path.resolve().as_uri()
        for suffix in ("?mode=ro", "?mode=ro&nolock=1", "?mode=ro&immutable=1"):
            conn = None
            try:
                conn = sqlite3.connect(uri + suffix, uri=True, timeout=1)
                conn.execute("SELECT 1 FROM sqlite_master").fetchone()
                self.conn = conn
                return conn
            except sqlite3.Error:
                if conn is not None:
                    try:
                        conn.close()
                    except sqlite3.Error:
                        pass

        self.tmpdir = tempfile.TemporaryDirectory(prefix="cclimits-cookie-")
        target = Path(self.tmpdir.name) / self.path.name
        shutil.copy2(self.path, target)
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(self.path) + suffix)
            if sidecar.is_file():
                try:
                    shutil.copy2(sidecar, Path(str(target) + suffix))
                except OSError:
                    pass
        self.conn = sqlite3.connect(target, timeout=1)
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        if self.conn is not None:
            self.conn.close()
        if self.tmpdir is not None:
            self.tmpdir.cleanup()


def _chromium_cookie_db_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = 'version'").fetchone()
        return int(row[0]) if row else 0
    except (sqlite3.Error, TypeError, ValueError):
        return 0


@lru_cache(maxsize=16)
def _linux_safe_storage_password(application: str) -> bytes | None:
    if not sys.platform.startswith("linux"):
        return None

    schemas = (
        "chrome_libsecret_os_crypt_password_v2",
        "chrome_libsecret_os_crypt_password_v1",
    )

    try:
        import gi  # type: ignore

        gi.require_version("Secret", "1")
        from gi.repository import Secret  # type: ignore

        for schema_name in schemas:
            try:
                schema = Secret.Schema.new(
                    schema_name,
                    Secret.SchemaFlags.NONE,
                    {"application": Secret.SchemaAttributeType.STRING},
                )
                value = Secret.password_lookup_sync(
                    schema,
                    {"application": application},
                    None,
                )
                if isinstance(value, str) and value:
                    return value.encode("utf-8")
                if isinstance(value, bytes) and value:
                    return value
            except Exception:
                continue
    except Exception:
        pass

    secret_tool = shutil.which("secret-tool")
    if secret_tool:
        # Chromium has used several libsecret attribute layouts across Linux
        # desktop environments. Try the modern application-only lookup first,
        # then the explicit schema form, then the older service/account form.
        app_labels = {
            "chrome": ("Chrome Safe Storage", "Chrome"),
            "chromium": ("Chromium Safe Storage", "Chromium"),
            "brave": ("Brave Safe Storage", "Brave"),
        }
        attempts: list[list[str]] = [
            [secret_tool, "lookup", "application", application],
        ]
        for schema_name in schemas:
            attempts.append([
                secret_tool,
                "lookup",
                "xdg:schema",
                schema_name,
                "application",
                application,
            ])
        if application in app_labels:
            service, account = app_labels[application]
            attempts.append([
                secret_tool,
                "lookup",
                "service",
                service,
                "account",
                account,
            ])

        for command in attempts:
            try:
                proc = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    timeout=3,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError):
                continue
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.rstrip(b"\r\n")

    return None


def _aes128_cbc_decrypt(key: bytes, ciphertext: bytes) -> bytes | None:
    """Decrypt AES-128-CBC using an already-installed local crypto primitive."""
    if len(key) != 16 or not ciphertext or len(ciphertext) % 16:
        return None

    try:
        from Cryptodome.Cipher import AES  # type: ignore

        return AES.new(key, AES.MODE_CBC, b" " * 16).decrypt(ciphertext)
    except Exception:
        pass

    try:
        from Crypto.Cipher import AES  # type: ignore

        return AES.new(key, AES.MODE_CBC, b" " * 16).decrypt(ciphertext)
    except Exception:
        pass

    openssl = shutil.which("openssl")
    if not openssl:
        return None
    try:
        proc = subprocess.run(
            [
                openssl,
                "enc",
                "-d",
                "-aes-128-cbc",
                "-K",
                key.hex(),
                "-iv",
                (b" " * 16).hex(),
                "-nosalt",
                "-nopad",
            ],
            input=ciphertext,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def _pkcs7_unpad(data: bytes) -> bytes | None:
    if not data:
        return None
    amount = data[-1]
    if amount < 1 or amount > 16 or len(data) < amount:
        return None
    if data[-amount:] != bytes([amount]) * amount:
        return None
    return data[:-amount]


def _decrypt_chromium_cookie(
    host: str,
    value: object,
    encrypted_value: object,
    db_version: int,
    os_crypt_name: str,
) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, bytes) and value:
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return None

    if isinstance(encrypted_value, memoryview):
        encrypted = encrypted_value.tobytes()
    elif isinstance(encrypted_value, bytes):
        encrypted = encrypted_value
    else:
        return None

    prefix = encrypted[:3]
    if prefix not in (b"v10", b"v11"):
        return None
    ciphertext = encrypted[3:]

    passwords: list[bytes] = []
    if prefix == b"v10":
        passwords.append(b"peanuts")
    else:
        if password := _linux_safe_storage_password(os_crypt_name):
            passwords.append(password)
        passwords.append(b"")

    for password in passwords:
        key = hashlib.pbkdf2_hmac(
            "sha1",
            password,
            b"saltysalt",
            1,
            dklen=16,
        )
        raw = _aes128_cbc_decrypt(key, ciphertext)
        if raw is None:
            continue
        plain = _pkcs7_unpad(raw)
        if plain is None:
            continue

        if db_version >= 24:
            expected = hashlib.sha256(host.encode("utf-8")).digest()
            if len(plain) < 32 or plain[:32] != expected:
                continue
            plain = plain[32:]

        try:
            decoded = plain.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if decoded:
            return decoded
    return None


def _chromium_expired(expires_utc: object) -> bool:
    try:
        value = float(expires_utc)
    except (TypeError, ValueError):
        return False
    if value <= 0:
        return False
    unix = value / 1_000_000.0 - CHROMIUM_EPOCH_OFFSET_SECONDS
    return unix <= time.time()


def _allowed_cookie_host(host: object, name: object) -> bool:
    """Accept only cookies that can belong to the opencode.ai site.

    ``__Host-`` cookies are host-only by definition and therefore must not be
    read from a domain cookie row such as ``.opencode.ai``. The legacy
    ``auth`` cookie may be host-only or scoped to the exact parent domain, but
    never to a lookalike or arbitrary subdomain.
    """
    if not isinstance(host, str) or not isinstance(name, str):
        return False
    normalized_host = host.casefold()
    if name == "__Host-auth":
        return normalized_host == "opencode.ai"
    return normalized_host in OPENCODE_COOKIE_HOSTS


def _read_chromium_session(spec: _ChromiumSpec, path: Path) -> dict | None:
    try:
        with _SQLiteSnapshot(path) as conn:
            version = _chromium_cookie_db_version(conn)
            rows = conn.execute(
                """
                SELECT host_key, name, value, encrypted_value, expires_utc
                FROM cookies
                WHERE host_key IN (?, ?) AND name IN (?, ?)
                ORDER BY last_access_utc DESC
                """,
                (*OPENCODE_COOKIE_HOSTS, *OPENCODE_COOKIE_NAMES),
            ).fetchall()
    except (OSError, sqlite3.Error, PermissionError):
        return None

    for host, name, value, encrypted_value, expires_utc in rows:
        if not _allowed_cookie_host(host, name):
            continue
        if _chromium_expired(expires_utc):
            continue
        cookie = _decrypt_chromium_cookie(
            str(host),
            value,
            encrypted_value,
            version,
            spec.os_crypt_name,
        )
        if cookie:
            return {
                "cookie_header": f"{name}={cookie}",
                "browser": spec.name,
                "source": f"{spec.name} browser profile",
            }
    return None


def _read_firefox_session(path: Path) -> dict | None:
    try:
        with _SQLiteSnapshot(path) as conn:
            rows = conn.execute(
                """
                SELECT host, name, value, expiry
                FROM moz_cookies
                WHERE host IN (?, ?) AND name IN (?, ?)
                ORDER BY lastAccessed DESC
                """,
                (*OPENCODE_COOKIE_HOSTS, *OPENCODE_COOKIE_NAMES),
            ).fetchall()
    except (OSError, sqlite3.Error, PermissionError):
        return None

    now = time.time()
    for host, name, value, expiry in rows:
        if not _allowed_cookie_host(host, name):
            continue
        try:
            expired = float(expiry) > 0 and float(expiry) <= now
        except (TypeError, ValueError):
            expired = False
        if expired or not isinstance(value, str) or not value:
            continue
        return {
            "cookie_header": f"{name}={value}",
            "browser": "firefox",
            "source": "firefox browser profile",
        }
    return None


def discover_web_sessions() -> list[dict]:
    """Find existing opencode.ai authenticated browser sessions, read-only."""
    sessions: list[dict] = []

    if sys.platform.startswith("linux"):
        for spec in _chromium_specs():
            for path in _expand_cookie_patterns(spec.patterns):
                if session := _read_chromium_session(spec, path):
                    sessions.append(session)
        for path in _firefox_cookie_paths():
            if session := _read_firefox_session(path):
                sessions.append(session)

    seen = set()
    result = []
    for session in sessions:
        fingerprint = hashlib.sha256(session["cookie_header"].encode("utf-8")).hexdigest()[:12]
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        public = dict(session)
        public["fingerprint"] = fingerprint
        result.append(public)
    return result


def _server_get_url(server_id: str, args: list | None = None) -> str:
    query = {"id": server_id}
    if args:
        query["args"] = json.dumps(args, separators=(",", ":"))
    return OPENCODE_SERVER_URL + "?" + urllib.parse.urlencode(query)


def _server_headers(server_id: str, cookie_header: str, referer: str) -> dict:
    return {
        "Cookie": cookie_header,
        "X-Server-Id": server_id,
        "X-Server-Instance": "server-fn:" + str(uuid.uuid4()),
        "User-Agent": _USER_AGENT,
        "Origin": OPENCODE_BASE_URL,
        "Referer": referer,
        "Accept": "text/javascript, application/json;q=0.9, */*;q=0.8",
    }


def _workspace_ids(text: object) -> list[str]:
    if isinstance(text, (dict, list)):
        text = json.dumps(text, separators=(",", ":"))
    if not isinstance(text, str):
        return []
    ids = re.findall(r"\bwrk_[A-Za-z0-9]+\b", text)
    return list(dict.fromkeys(ids))


def _find_billing_dict(value: object) -> dict | None:
    if isinstance(value, dict):
        if "monthlyUsage" in value and ("balance" in value or "customerID" in value):
            return value
        for child in value.values():
            if found := _find_billing_dict(child):
                return found
    elif isinstance(value, list):
        for child in value:
            if found := _find_billing_dict(child):
                return found
    return None


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _payload_number(text: str, field: str) -> float | None:
    pattern = (
        r'(?:"' + re.escape(field) + r'"|' + re.escape(field) + r')\s*:\s*'
        r'(?:\$R\[\d+\]\s*=\s*)?(-?[0-9]+(?:\.[0-9]+)?)'
    )
    match = re.search(pattern, text)
    return float(match.group(1)) if match else None


def parse_billing_payload(payload: object) -> dict | None:
    """Parse OpenCode's billing.get response (JSON or SolidStart $R payload)."""
    if isinstance(payload, (dict, list)):
        billing = _find_billing_dict(payload)
        if billing:
            raw_usage = _number(billing.get("monthlyUsage"))
            raw_balance = _number(billing.get("balance"))
            monthly_limit = _number(billing.get("monthlyLimit"))
            if raw_usage is not None:
                return {
                    "monthly_usage_usd": raw_usage / ZEN_USD_SCALE,
                    "monthly_limit_usd": monthly_limit,
                    "balance_usd": None if raw_balance is None else raw_balance / ZEN_USD_SCALE,
                    "usage_updated_at": billing.get("timeMonthlyUsageUpdated"),
                }
        payload = json.dumps(payload, separators=(",", ":"))

    if not isinstance(payload, str):
        return None

    raw_usage = _payload_number(payload, "monthlyUsage")
    if raw_usage is None:
        return None
    raw_balance = _payload_number(payload, "balance")
    monthly_limit = _payload_number(payload, "monthlyLimit")
    return {
        "monthly_usage_usd": raw_usage / ZEN_USD_SCALE,
        "monthly_limit_usd": monthly_limit,
        "balance_usd": None if raw_balance is None else raw_balance / ZEN_USD_SCALE,
        "usage_updated_at": None,
    }


def fetch_billing_from_session(
    session: dict,
    http_get: Callable[[str, dict], tuple[int, object]],
) -> dict | None:
    """Fetch workspace billing using an already-authenticated web session."""
    cookie_header = session.get("cookie_header")
    if not isinstance(cookie_header, str) or not cookie_header:
        return None

    workspace_url = _server_get_url(OPENCODE_WORKSPACES_SERVER_ID)
    status, payload = http_get(
        workspace_url,
        _server_headers(
            OPENCODE_WORKSPACES_SERVER_ID,
            cookie_header,
            OPENCODE_BASE_URL,
        ),
    )
    if status != 200:
        return None

    workspace_ids = _workspace_ids(payload)
    if not workspace_ids:
        return None

    for workspace_id in workspace_ids:
        referer = f"{OPENCODE_BASE_URL}/workspace/{workspace_id}"
        billing_url = _server_get_url(OPENCODE_BILLING_SERVER_ID, [workspace_id])
        b_status, b_payload = http_get(
            billing_url,
            _server_headers(
                OPENCODE_BILLING_SERVER_ID,
                cookie_header,
                referer,
            ),
        )
        if b_status != 200:
            continue
        billing = parse_billing_payload(b_payload)
        if billing is None:
            continue
        return {
            **billing,
            "workspace_count": len(workspace_ids),
            "browser": session.get("browser"),
            "browser_source": session.get("source"),
        }

    return None


def discover_billing(
    http_get: Callable[[str, dict], tuple[int, object]],
) -> dict | None:
    """Try existing browser sessions until one yields authoritative Zen billing."""
    for session in discover_web_sessions():
        if billing := fetch_billing_from_session(session, http_get):
            return billing
    return None
