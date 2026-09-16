"""Tests for read-only OpenCode web-session billing discovery."""

import json
import sqlite3
import time
from unittest.mock import patch

import pytest
import cclimits
import opencode_web


def test_parse_billing_json_fixed_point_units():
    result = opencode_web.parse_billing_payload({
        "data": {
            "customerID": "cus_test",
            "balance": 1_250_000_000,
            "monthlyUsage": 345_000_000,
            "monthlyLimit": 20,
            "timeMonthlyUsageUpdated": "2026-08-30T18:00:00Z",
        }
    })

    assert result is not None
    assert result["balance_usd"] == 12.5
    assert result["monthly_usage_usd"] == 3.45
    assert result["monthly_limit_usd"] == 20
    assert result["usage_updated_at"] == "2026-08-30T18:00:00Z"


def test_parse_billing_solidstart_payload():
    payload = (
        'customerID:"cus_test",'
        'balance:$R[1]=1250000000,'
        'monthlyUsage:$R[2]=345000000,'
        'monthlyLimit:20'
    )

    result = opencode_web.parse_billing_payload(payload)

    assert result is not None
    assert result["balance_usd"] == 12.5
    assert result["monthly_usage_usd"] == 3.45
    assert result["monthly_limit_usd"] == 20


def test_reads_firefox_opencode_auth_cookie_read_only(tmp_path):
    db = tmp_path / "cookies.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE moz_cookies (
            id INTEGER PRIMARY KEY,
            host TEXT,
            name TEXT,
            value TEXT,
            expiry INTEGER,
            lastAccessed INTEGER
        )
        """
    )
    conn.execute(
        "INSERT INTO moz_cookies(host, name, value, expiry, lastAccessed) VALUES (?, ?, ?, ?, ?)",
        (
            "opencode.ai",
            "__Host-auth",
            "secret-web-session",
            int(time.time()) + 3600,
            123,
        ),
    )
    conn.commit()
    conn.close()

    before = db.stat().st_mtime_ns
    session = opencode_web._read_firefox_session(db)
    after = db.stat().st_mtime_ns

    assert session is not None
    assert session["cookie_header"] == "__Host-auth=secret-web-session"
    assert session["browser"] == "firefox"
    assert before == after


@pytest.mark.parametrize("host", [".evilopencode.ai", ".sub.opencode.ai"])
def test_rejects_firefox_lookalike_and_subdomain_cookies(tmp_path, host):
    db = tmp_path / "cookies.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE moz_cookies (
            id INTEGER PRIMARY KEY,
            host TEXT,
            name TEXT,
            value TEXT,
            expiry INTEGER,
            lastAccessed INTEGER
        )
        """
    )
    conn.execute(
        "INSERT INTO moz_cookies(host, name, value, expiry, lastAccessed) VALUES (?, ?, ?, ?, ?)",
        (host, "auth", "unrelated-secret", int(time.time()) + 3600, 123),
    )
    conn.commit()
    conn.close()

    assert opencode_web._read_firefox_session(db) is None


def test_firefox_allows_domain_auth_but_not_host_cookie_on_domain(tmp_path):
    db = tmp_path / "cookies.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE moz_cookies (
            id INTEGER PRIMARY KEY,
            host TEXT,
            name TEXT,
            value TEXT,
            expiry INTEGER,
            lastAccessed INTEGER
        )
        """
    )
    conn.executemany(
        "INSERT INTO moz_cookies(host, name, value, expiry, lastAccessed) VALUES (?, ?, ?, ?, ?)",
        [
            (".opencode.ai", "__Host-auth", "invalid-host-cookie", int(time.time()) + 3600, 200),
            (".opencode.ai", "auth", "valid-domain-cookie", int(time.time()) + 3600, 100),
        ],
    )
    conn.commit()
    conn.close()

    session = opencode_web._read_firefox_session(db)

    assert session is not None
    assert session["cookie_header"] == "auth=valid-domain-cookie"


def test_reads_plaintext_chromium_cookie_without_crypto(tmp_path):
    db = tmp_path / "Cookies"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO meta(key, value) VALUES ('version', '23')")
    conn.execute(
        """
        CREATE TABLE cookies (
            host_key TEXT,
            name TEXT,
            value TEXT,
            encrypted_value BLOB,
            expires_utc INTEGER,
            last_access_utc INTEGER
        )
        """
    )
    conn.execute(
        "INSERT INTO cookies VALUES (?, ?, ?, ?, ?, ?)",
        (".opencode.ai", "auth", "plain-session", b"", 0, 100),
    )
    conn.commit()
    conn.close()

    spec = opencode_web._ChromiumSpec("chrome", "chrome", ())
    session = opencode_web._read_chromium_session(spec, db)

    assert session is not None
    assert session["cookie_header"] == "auth=plain-session"
    assert session["browser"] == "chrome"


def test_rejects_chromium_lookalike_cookie(tmp_path):
    db = tmp_path / "Cookies"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO meta(key, value) VALUES ('version', '23')")
    conn.execute(
        """
        CREATE TABLE cookies (
            host_key TEXT,
            name TEXT,
            value TEXT,
            encrypted_value BLOB,
            expires_utc INTEGER,
            last_access_utc INTEGER
        )
        """
    )
    conn.execute(
        "INSERT INTO cookies VALUES (?, ?, ?, ?, ?, ?)",
        (".evilopencode.ai", "auth", "unrelated-secret", b"", 0, 100),
    )
    conn.commit()
    conn.close()

    spec = opencode_web._ChromiumSpec("chrome", "chrome", ())
    assert opencode_web._read_chromium_session(spec, db) is None


def test_fetch_billing_from_existing_session_never_returns_cookie():
    session = {
        "cookie_header": "__Host-auth=very-secret-cookie",
        "browser": "chrome",
        "source": "chrome browser profile",
        "fingerprint": "abc123",
    }
    seen_headers = []

    def fake_get(url, headers):
        seen_headers.append(headers)
        if "id=" + opencode_web.OPENCODE_WORKSPACES_SERVER_ID in url:
            return 200, 'id:"wrk_TEST123"'
        assert "id=" + opencode_web.OPENCODE_BILLING_SERVER_ID in url
        return 200, {
            "customerID": "cus_test",
            "balance": 2_000_000_000,
            "monthlyUsage": 500_000_000,
            "monthlyLimit": 30,
        }

    result = opencode_web.fetch_billing_from_session(session, fake_get)

    assert result is not None
    assert result["balance_usd"] == 20.0
    assert result["monthly_usage_usd"] == 5.0
    assert result["monthly_limit_usd"] == 30
    assert result["browser"] == "chrome"
    assert "very-secret-cookie" not in json.dumps(result)
    assert any(h["Cookie"] == "__Host-auth=very-secret-cookie" for h in seen_headers)


def test_zen_usage_overlays_authoritative_web_billing():
    identities = [{
        "key": "existing-key",
        "fingerprint": "api-fingerprint",
        "harnesses": ["pi", "omp"],
        "sources": ["pi/auth.json", "omp/agent.db"],
    }]
    billing = {
        "balance_usd": 9.75,
        "monthly_usage_usd": 4.25,
        "monthly_limit_usd": 25.0,
        "workspace_count": 1,
        "browser": "chrome",
        "browser_source": "chrome browser profile",
        "usage_updated_at": "2026-08-30T18:00:00Z",
    }

    with patch("cclimits.discover_opencode_zen_credentials", return_value=identities), \
         patch("cclimits._opencode_zen_key_status", return_value=("valid_no_go", 403, {})), \
         patch("cclimits.discover_opencode_zen_billing", return_value=billing):
        result = cclimits.get_opencode_zen_usage(allow_browser_billing=True)

    assert result["status"] == "authenticated"
    assert result["balance_status"] == "ok"
    assert result["balance_usd"] == 9.75
    assert result["monthly_usage_usd"] == 4.25
    assert result["monthly_limit_usd"] == 25.0
    assert result["billing_source"] == "opencode_web_session"
    assert result["browser"] == "chrome"
    assert result["browser_source"] == "chrome browser profile"
    assert "cookie_header" not in result
    assert "workspace_id" not in result
    assert "web_session_fingerprint" not in result
    assert "key_fingerprint" not in result
    assert "very-secret-cookie" not in json.dumps(result)
    assert "/home/test" not in json.dumps(result)


def test_zen_usage_does_not_inspect_browser_by_default():
    identities = [{
        "key": "existing-key",
        "fingerprint": "api-fingerprint",
        "harnesses": ["pi"],
        "sources": ["pi/auth.json"],
    }]

    with patch("cclimits.discover_opencode_zen_credentials", return_value=identities), \
         patch("cclimits._opencode_zen_key_status", return_value=("valid_no_go", 403, {})), \
         patch("cclimits.discover_opencode_zen_billing") as discover_billing:
        result = cclimits.get_opencode_zen_usage()

    assert result["status"] == "authenticated"
    assert result["balance_status"] == "unavailable_by_api"
    assert "balance_usd" not in result
    discover_billing.assert_not_called()


def test_non_linux_billing_guidance_is_accurate():
    identities = [{
        "key": "existing-key",
        "fingerprint": "api-fingerprint",
        "harnesses": ["pi"],
        "sources": ["Pi auth.json"],
    }]

    with patch("cclimits.sys.platform", "darwin"), \
         patch("cclimits.discover_opencode_zen_credentials", return_value=identities), \
         patch("cclimits._opencode_zen_key_status", return_value=("valid_no_go", 403, {})), \
         patch("cclimits.discover_opencode_zen_billing", return_value=None):
        result = cclimits.get_opencode_zen_usage()

    assert result["status"] == "authenticated"
    assert "Linux-only" in result["balance_note"]
