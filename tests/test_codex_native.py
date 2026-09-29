"""Tests for native Codex app-server quota discovery."""

import json
import queue
from unittest.mock import patch

import cclimits
import codex_native


def _native_stdout(primary=42.5, secondary=12.0):
    rate_limit = {
        "limitId": "codex",
        "limitName": "Codex",
        "primary": {
            "usedPercent": primary,
            "windowDurationMins": 300,
            "resetsAt": 1788105600,
        },
        "secondary": {
            "usedPercent": secondary,
            "windowDurationMins": 10080,
            "resetsAt": 1788710400,
        },
        "planType": "pro",
        "rateLimitReachedType": None,
    }
    return "\n".join([
        json.dumps({"id": 1, "result": {"userAgent": "codex-test"}}),
        json.dumps({
            "id": 2,
            "result": {
                "rateLimits": rate_limit,
                "rateLimitsByLimitId": {"codex": rate_limit},
                "rateLimitResetCredits": {"availableCount": 2, "credits": []},
            },
        }),
        "",
    ])


def test_parse_native_rate_limits():
    result = codex_native.parse_app_server_output(_native_stdout())

    assert result is not None
    assert result["status"] == "ok"
    assert result["source"] == "codex_app_server"
    assert result["auth"] == "Codex app-server (native)"
    assert result["plan"] == "pro"
    assert result["primary_window"]["window"] == "5h"
    assert result["primary_window"]["used"] == "42.5%"
    assert result["primary_window"]["remaining"] == "57.5%"
    assert result["primary_window"]["window_duration_minutes"] == 300
    assert result["secondary_window"]["window"] == "7d"
    assert result["secondary_window"]["used"] == "12%"
    assert result["secondary_window"]["remaining"] == "88%"
    assert result["reset_credits_available"] == 2


def test_native_windows_are_classified_by_duration_not_slot():
    swapped = {
        "limitId": "codex",
        "primary": {
            "usedPercent": 70,
            "windowDurationMins": 10080,
            "resetsAt": 1788710400,
        },
        "secondary": {
            "usedPercent": 20,
            "windowDurationMins": 300,
            "resetsAt": 1788105600,
        },
        "planType": "plus",
    }
    stdout = "\n".join([
        json.dumps({"id": 1, "result": {}}),
        json.dumps({"id": 2, "result": {
            "rateLimits": swapped,
            "rateLimitsByLimitId": None,
            "rateLimitResetCredits": None,
        }}),
    ])

    result = codex_native.parse_app_server_output(stdout)

    assert result is not None
    assert result["primary_window"]["window"] == "5h"
    assert result["primary_window"]["used"] == "20%"
    assert result["secondary_window"]["window"] == "7d"
    assert result["secondary_window"]["used"] == "70%"


def test_weekly_only_native_window_is_not_mislabeled_5h():
    weekly_only = {
        "limitId": "codex",
        "primary": {
            "usedPercent": 6,
            "windowDurationMins": 10080,
            "resetsAt": 1788710400,
        },
        "secondary": None,
        "planType": "pro",
    }
    stdout = json.dumps({
        "id": 2,
        "result": {
            "rateLimits": weekly_only,
            "rateLimitsByLimitId": None,
            "rateLimitResetCredits": None,
        },
    })

    result = codex_native.parse_app_server_output(stdout)

    assert result is not None
    assert "primary_window" not in result
    assert result["secondary_window"]["window"] == "7d"
    assert result["secondary_window"]["used"] == "6%"


def test_multiple_native_buckets_are_preserved():
    aggregate = {
        "limitId": "codex",
        "limitName": "Codex",
        "primary": {"usedPercent": 10, "windowDurationMins": 300, "resetsAt": 1788105600},
        "secondary": {"usedPercent": 30, "windowDurationMins": 10080, "resetsAt": 1788710400},
        "planType": "pro",
    }
    review = {
        "limitId": "code-review",
        "limitName": "Code review",
        "primary": {"usedPercent": 25, "windowDurationMins": 10080, "resetsAt": 1788710400},
        "secondary": None,
        "planType": "pro",
    }
    stdout = json.dumps({
        "id": 2,
        "result": {
            "rateLimits": aggregate,
            "rateLimitsByLimitId": {
                "codex": aggregate,
                "code-review": review,
            },
            "rateLimitResetCredits": None,
        },
    })

    result = codex_native.parse_app_server_output(stdout)

    assert result is not None
    assert len(result["buckets"]) == 2
    assert {bucket["limit_id"] for bucket in result["buckets"]} == {"codex", "code-review"}


class _FakeStdout:
    def __init__(self):
        self.lines = queue.Queue()

    def push(self, value):
        self.lines.put(value)

    def readline(self):
        return self.lines.get()


class _FakeStdin:
    def __init__(self, proc):
        self.proc = proc
        self.closed = False

    def write(self, value):
        message = json.loads(value)
        self.proc.writes.append(message)
        if message.get("method") == "initialize":
            self.proc.stdout.push(json.dumps({
                "id": 1,
                "result": {
                    "userAgent": "codex-test",
                    "codexHome": "/tmp/.codex",
                    "platformFamily": "unix",
                    "platformOs": "linux",
                },
            }) + "\n")
        elif message.get("method") == "account/rateLimits/read":
            # The native request must happen only after the initialized
            # notification, matching Codex's documented lifecycle.
            assert any(item.get("method") == "initialized" for item in self.proc.writes)
            for line in _native_stdout().splitlines():
                parsed = json.loads(line)
                if parsed.get("id") == 2:
                    self.proc.stdout.push(line + "\n")

    def flush(self):
        pass

    def close(self):
        self.closed = True


class _FakeProc:
    def __init__(self):
        self.stdout = _FakeStdout()
        self.stderr = None
        self.writes = []
        self.stdin = _FakeStdin(self)
        self._done = False

    def poll(self):
        return 0 if self._done else None

    def terminate(self):
        self._done = True
        self.stdout.push("")

    def wait(self, timeout=None):
        self._done = True
        return 0

    def kill(self):
        self._done = True
        self.stdout.push("")


@patch("codex_native._codex_command", return_value=["codex"])
@patch("codex_native.subprocess.Popen")
def test_native_reader_uses_sequential_read_only_handshake(mock_popen, _mock_command):
    proc = _FakeProc()
    mock_popen.return_value = proc

    result = codex_native.get_native_codex_usage()

    assert result is not None
    assert result["status"] == "ok"
    args, kwargs = mock_popen.call_args
    assert args[0] == ["codex", "app-server", "--stdio"]
    assert kwargs["stderr"] is codex_native.subprocess.DEVNULL

    methods = [item.get("method") for item in proc.writes]
    assert methods == ["initialize", "initialized", "account/rateLimits/read"]
    payload = json.dumps(proc.writes)
    assert "consume" not in payload.lower()
    assert "redeem" not in payload.lower()


def test_cclimits_prefers_native_codex_without_reading_auth_or_wham():
    native = codex_native.parse_app_server_output(_native_stdout())
    assert native is not None

    with patch("cclimits.get_native_codex_usage", return_value=native), \
         patch("cclimits.get_openai_credentials") as creds, \
         patch("cclimits.http_get") as http_get:
        result = cclimits.get_codex_usage()

    assert result["source"] == "codex_app_server"
    assert result["primary_window"]["used"] == "42.5%"
    creds.assert_not_called()
    http_get.assert_not_called()


def test_cclimits_falls_back_to_wham_when_native_rpc_is_unavailable():
    with patch("cclimits.get_native_codex_usage", return_value={
            "error": "Codex native quota unavailable",
            "native_source": "codex_app_server",
         }), \
         patch("cclimits.get_openai_credentials", return_value={
            "access_token": "oauth-token",
            "account_id": "account-id",
         }), \
         patch("cclimits.http_get", return_value=(200, {
            "plan_type": "Plus",
            "rate_limit": {
                "primary_window": {
                    "used_percent": 35,
                    "limit_window_seconds": 18000,
                    "reset_after_seconds": 7200,
                    "reset_at": 1788105600,
                },
                "secondary_window": {
                    "used_percent": 68,
                    "limit_window_seconds": 604800,
                    "reset_after_seconds": 345600,
                    "reset_at": 1788710400,
                },
            },
         })) as http_get:
        result = cclimits.get_codex_usage()

    assert result["status"] == "ok"
    assert result["source"] == "chatgpt_wham_fallback"
    assert result["native_fallback_reason"] == "Codex native quota unavailable"
    assert "native_fallback_details" not in result
    assert result["primary_window"]["window_duration_minutes"] == 300
    assert result["primary_window"]["resets_at"] == "2026-08-30T16:00:00Z"
    assert result["secondary_window"]["window_duration_minutes"] == 10080
    assert result["secondary_window"]["resets_at"] == "2026-09-06T16:00:00Z"
    assert http_get.call_args.args[0] == "https://chatgpt.com/backend-api/wham/usage"


def test_native_failure_without_fallback_credentials_is_explicit():
    with patch("cclimits.get_native_codex_usage", return_value={
            "error": "Codex native quota unavailable",
            "details": "schema changed",
         }), \
         patch("cclimits.get_openai_credentials", return_value={}):
        result = cclimits.get_codex_usage()

    assert result["error"] == "Codex native quota unavailable"
    assert result["native_source"] == "codex_app_server"
    assert "fallback credentials" in result["hint"]


def test_native_failure_details_do_not_expose_local_paths():
    with patch("cclimits.get_native_codex_usage", return_value={
            "error": "Codex native quota unavailable",
            "details": "server failed at /home/alice/.codex/session",
         }), \
         patch("cclimits.get_openai_credentials", return_value={}):
        result = cclimits.get_codex_usage()

    payload = json.dumps(result)
    assert "/home/alice" not in payload
    assert result["details"] == "Codex app-server did not return a usable quota snapshot"


@patch("codex_native._codex_command", return_value=["/home/alice/private/codex"])
@patch("codex_native.subprocess.Popen", side_effect=FileNotFoundError(2, "No such file", "/home/alice/private/codex"))
def test_native_start_failure_does_not_expose_executable_path(_mock_popen, _mock_command):
    result = codex_native.get_native_codex_usage()

    assert result is not None
    assert result["error"] == "Codex native quota unavailable"
    payload = json.dumps(result)
    assert "/home/alice" not in payload
    assert "FileNotFoundError" in result["details"]
