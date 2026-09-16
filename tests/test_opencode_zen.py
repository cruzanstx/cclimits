"""Tests for zero-config OpenCode Zen discovery across OpenCode, Pi and OMP."""

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import cclimits
import opencode_zen


def _empty_env():
    return {
        "HOME": str(Path.home()),
        "USERPROFILE": str(Path.home()),
    }


def test_discovers_native_opencode_auth_json(tmp_path):
    auth = tmp_path / "opencode" / "auth.json"
    auth.parent.mkdir()
    auth.write_text(json.dumps({"opencode": {"type": "api", "key": "zen-key"}}))

    with patch.dict(opencode_zen.os.environ, {"XDG_DATA_HOME": str(tmp_path)}, clear=True), \
         patch.object(opencode_zen.Path, "home", return_value=tmp_path / "home"):
        result = opencode_zen.discover_credentials()

    assert len(result) == 1
    assert result[0]["key"] == "zen-key"
    assert result[0]["harnesses"] == ["opencode"]
    assert "OpenCode auth.json" in result[0]["sources"]
    assert str(tmp_path) not in json.dumps(result)


def test_discovers_pi_auth_json(tmp_path):
    agent = tmp_path / "pi-agent"
    agent.mkdir()
    auth = agent / "auth.json"
    auth.write_text(json.dumps({"opencode": {"type": "api_key", "key": "pi-zen-key"}}))

    with patch.dict(opencode_zen.os.environ, {"PI_CODING_AGENT_DIR": str(agent)}, clear=True), \
         patch.object(opencode_zen.Path, "home", return_value=tmp_path / "home"):
        result = opencode_zen.discover_credentials()

    assert len(result) == 1
    assert result[0]["key"] == "pi-zen-key"
    assert "pi" in result[0]["harnesses"]


def test_discovers_omp_sqlite_credential_read_only(tmp_path):
    home = tmp_path / "home"
    agent = home / ".omp" / "agent"
    agent.mkdir(parents=True)
    db = agent / "agent.db"

    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE auth_credentials (
            id INTEGER PRIMARY KEY,
            provider TEXT NOT NULL,
            credential_type TEXT NOT NULL,
            data TEXT NOT NULL,
            disabled_cause TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO auth_credentials(provider, credential_type, data, disabled_cause) VALUES (?, ?, ?, NULL)",
        ("opencode-zen", "api_key", json.dumps({"key": "omp-zen-key", "source": "login"})),
    )
    conn.commit()
    conn.close()

    before = db.stat().st_mtime_ns
    with patch.dict(opencode_zen.os.environ, {}, clear=True), \
         patch.object(opencode_zen.Path, "home", return_value=home):
        result = opencode_zen.discover_credentials()
    after = db.stat().st_mtime_ns

    assert len(result) == 1
    assert result[0]["key"] == "omp-zen-key"
    assert "omp" in result[0]["harnesses"]
    assert "OMP agent.db" in result[0]["sources"]
    assert str(home) not in json.dumps(result)
    assert before == after


def test_same_key_across_harnesses_is_one_billing_identity(tmp_path):
    home = tmp_path / "home"

    xdg = tmp_path / "xdg"
    oc_auth = xdg / "opencode" / "auth.json"
    oc_auth.parent.mkdir(parents=True)
    oc_auth.write_text(json.dumps({"opencode": {"type": "api", "key": "shared-key"}}))

    pi_agent = home / ".pi" / "agent"
    pi_agent.mkdir(parents=True)
    (pi_agent / "auth.json").write_text(
        json.dumps({"opencode": {"type": "api_key", "key": "shared-key"}})
    )

    omp_agent = home / ".omp" / "agent"
    omp_agent.mkdir(parents=True)
    db = omp_agent / "agent.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE auth_credentials (id INTEGER PRIMARY KEY, provider TEXT, credential_type TEXT, data TEXT, disabled_cause TEXT)"
    )
    conn.execute(
        "INSERT INTO auth_credentials(provider, credential_type, data, disabled_cause) VALUES (?, ?, ?, NULL)",
        ("opencode-zen", "api_key", json.dumps({"key": "shared-key"})),
    )
    conn.commit()
    conn.close()

    with patch.dict(opencode_zen.os.environ, {"XDG_DATA_HOME": str(xdg)}, clear=True), \
         patch.object(opencode_zen.Path, "home", return_value=home):
        result = opencode_zen.discover_credentials()

    assert len(result) == 1
    assert set(result[0]["harnesses"]) == {"opencode", "pi", "omp"}
    assert result[0]["fingerprint"]
    assert "shared-key" not in result[0]["fingerprint"]


def test_omp_dotenv_is_read_without_execution(tmp_path):
    home = tmp_path / "home"
    agent = home / ".omp" / "agent"
    agent.mkdir(parents=True)
    (agent / ".env").write_text('OPENCODE_API_KEY="dotenv-key"\n')

    with patch.dict(opencode_zen.os.environ, {}, clear=True), \
         patch.object(opencode_zen.Path, "home", return_value=home), \
         patch.object(opencode_zen.Path, "cwd", return_value=tmp_path / "cwd"):
        result = opencode_zen.discover_credentials()

    assert len(result) == 1
    assert result[0]["key"] == "dotenv-key"
    assert "omp-env" in result[0]["harnesses"]


def test_valid_zen_key_without_go_is_authenticated():
    identities = [{
        "key": "existing-key",
        "fingerprint": "abc123",
        "harnesses": ["opencode", "omp"],
        "sources": ["auth.json", "agent.db"],
    }]
    with patch("cclimits.discover_opencode_zen_credentials", return_value=identities), \
         patch("cclimits.http_get", return_value=(403, "Forbidden")) as http_get:
        result = cclimits.get_opencode_zen_usage()

    assert result["status"] == "authenticated"
    assert result["api_key_valid"] is True
    assert result["balance_status"] == "unavailable_by_api"
    assert result["auth"] == "opencode, omp"
    assert "balance" in result["balance_note"].lower()
    assert http_get.call_args.args[0] == "https://opencode.ai/zen/go/v1/usage"
    assert http_get.call_args.args[1]["Authorization"] == "Bearer existing-key"


def test_browser_billing_is_not_inspected_by_default():
    identities = [{
        "key": "existing-key",
        "fingerprint": "abc123",
        "harnesses": ["pi"],
        "sources": ["auth.json"],
    }]
    with patch("cclimits.discover_opencode_zen_credentials", return_value=identities), \
         patch("cclimits.http_get", return_value=(403, "Forbidden")), \
         patch("cclimits.discover_opencode_zen_billing") as discover_billing:
        result = cclimits.get_opencode_zen_usage()

    assert result["balance_status"] == "unavailable_by_api"
    discover_billing.assert_not_called()


def test_opencode_zen_cli_does_not_opt_into_browser_billing():
    with patch("cclimits.get_opencode_zen_usage", return_value={"status": "authenticated"}) as fetch, \
         patch("sys.argv", ["cclimits", "--opencode-zen", "--json"]):
        cclimits.main()

    fetch.assert_called_once_with(allow_browser_billing=False)


def test_opencode_zen_browser_flag_opts_in_explicitly():
    with patch("cclimits.get_opencode_zen_usage", return_value={"status": "authenticated"}) as fetch, \
         patch("sys.argv", ["cclimits", "--opencode-zen", "--opencode-zen-browser", "--json"]):
        cclimits.main()

    fetch.assert_called_once_with(allow_browser_billing=True)


def test_rejected_key_reports_invalid_auth():
    identities = [{
        "key": "bad-key",
        "fingerprint": "deadbeef",
        "harnesses": ["pi"],
        "sources": ["auth.json"],
    }]
    with patch("cclimits.discover_opencode_zen_credentials", return_value=identities), \
         patch("cclimits.http_get", return_value=(401, "Unauthorized")):
        result = cclimits.get_opencode_zen_usage()

    assert result["error"] == "Invalid API key"
    assert result["identities"][0]["validation"] == "invalid"


def test_no_credential_does_not_start_login():
    with patch("cclimits.discover_opencode_zen_credentials", return_value=[]):
        result = cclimits.get_opencode_zen_usage()

    assert result["error"] == cclimits.NO_CREDS_ERROR
    assert "OpenCode, Pi, OMP" in result["hint"]


def test_raw_key_is_not_exposed_in_success_payload():
    identities = [{
        "key": "super-secret-key",
        "fingerprint": "safe-fingerprint",
        "harnesses": ["omp"],
        "sources": ["agent.db"],
    }]
    with patch("cclimits.discover_opencode_zen_credentials", return_value=identities), \
         patch("cclimits.http_get", return_value=(403, "Forbidden")):
        result = cclimits.get_opencode_zen_usage()

    payload = json.dumps(result)
    assert "super-secret-key" not in payload
    assert "safe-fingerprint" not in payload
    assert "key_fingerprint" not in result
