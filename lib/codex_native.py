"""Read Codex subscription quota from the native app-server RPC.

This module is deliberately credential-blind: it asks the installed Codex
binary for the same account/rate-limit snapshot Codex itself uses. No OAuth
files or private HTTP endpoints are needed on the native path.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import queue
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


def _codex_command() -> list[str] | None:
    """Resolve the local Codex executable, including Windows npm shims."""
    configured = os.environ.get("CODEX_BIN")
    resolved = configured or shutil.which("codex")
    if not resolved:
        return None

    suffix = Path(resolved).suffix.lower()
    if os.name == "nt" and suffix in (".cmd", ".bat"):
        comspec = os.environ.get("COMSPEC") or "cmd.exe"
        return [comspec, "/d", "/s", "/c", resolved]
    return [resolved]


def _json_messages(stdout: str) -> list[dict]:
    messages: list[dict] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            messages.append(value)
    return messages


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if number == number and number not in (float("inf"), float("-inf")):
            return number
    return None


def _window_label(minutes: float | None) -> tuple[str, str]:
    """Return (slot, label) from the backend's actual duration."""
    if minutes is None:
        return "primary_window", "unknown"
    rounded = int(round(minutes))
    if rounded <= 24 * 60:
        if rounded % 60 == 0:
            return "primary_window", f"{rounded // 60}h"
        return "primary_window", f"{rounded}m"
    if rounded % (24 * 60) == 0:
        return "secondary_window", f"{rounded // (24 * 60)}d"
    return "secondary_window", f"{rounded}m"


def _reset_iso(epoch_seconds: object) -> str | None:
    number = _finite_number(epoch_seconds)
    if number is None or number < 0:
        return None
    try:
        return datetime.fromtimestamp(number, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except (OverflowError, OSError, ValueError):
        return None


def _reset_in(epoch_seconds: object) -> str | None:
    number = _finite_number(epoch_seconds)
    if number is None:
        return None
    delta = max(0, int(number - datetime.now(timezone.utc).timestamp()))
    days, remainder = divmod(delta, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _normalize_window(raw: object) -> dict | None:
    if not isinstance(raw, dict):
        return None

    used = _finite_number(raw.get("usedPercent"))
    duration = _finite_number(raw.get("windowDurationMins"))
    reset_at = raw.get("resetsAt")

    # A real window may omit one field, but an empty object is not quota data.
    if used is None and duration is None and reset_at is None:
        return None

    remaining = None if used is None else max(0.0, min(100.0, 100.0 - used))
    slot, label = _window_label(duration)

    item: dict = {
        "slot": slot,
        "window": label,
        "used": None if used is None else f"{used:g}%",
        "remaining": None if remaining is None else f"{remaining:g}%",
        "used_percent": used,
        "remaining_percent": remaining,
        "window_duration_minutes": None if duration is None else int(duration),
    }

    if reset_iso := _reset_iso(reset_at):
        item["resets_at"] = reset_iso
    if reset_in := _reset_in(reset_at):
        item["resets_in"] = reset_in

    return item


def _snapshot_to_public(snapshot: object, fallback_id: str | None = None) -> dict | None:
    if not isinstance(snapshot, dict):
        return None

    item: dict = {
        "limit_id": snapshot.get("limitId") if isinstance(snapshot.get("limitId"), str) else fallback_id,
        "limit_name": snapshot.get("limitName") if isinstance(snapshot.get("limitName"), str) else None,
        "plan": snapshot.get("planType") if isinstance(snapshot.get("planType"), str) else None,
        "rate_limit_reached_type": (
            snapshot.get("rateLimitReachedType")
            if isinstance(snapshot.get("rateLimitReachedType"), str)
            else None
        ),
        "windows": [],
    }

    for name in ("primary", "secondary"):
        if window := _normalize_window(snapshot.get(name)):
            item["windows"].append({"native_slot": name, **window})

    return item if item["windows"] else None


def parse_app_server_output(stdout: str) -> dict | None:
    """Parse account/rateLimits/read from newline-delimited app-server JSON."""
    messages = _json_messages(stdout)
    response = next(
        (
            message
            for message in messages
            if message.get("id") == 2 and isinstance(message.get("result"), dict)
        ),
        None,
    )
    if response is None:
        return None

    result = response["result"]
    snapshots: list[dict] = []

    by_id = result.get("rateLimitsByLimitId")
    if isinstance(by_id, dict):
        for limit_id, value in by_id.items():
            if parsed := _snapshot_to_public(value, str(limit_id)):
                snapshots.append(parsed)

    if not snapshots:
        if parsed := _snapshot_to_public(result.get("rateLimits")):
            snapshots.append(parsed)

    if not snapshots:
        return None

    # Prefer the canonical aggregate returned in rateLimits when present.
    preferred = _snapshot_to_public(result.get("rateLimits"))
    primary_snapshot = preferred or snapshots[0]

    public: dict = {
        "status": "ok",
        "source": "codex_app_server",
        "auth": "Codex app-server (native)",
        "buckets": snapshots,
    }

    if primary_snapshot.get("plan"):
        public["plan"] = primary_snapshot["plan"]
    if primary_snapshot.get("rate_limit_reached_type"):
        public["rate_limit_reached_type"] = primary_snapshot["rate_limit_reached_type"]
        public["limit_reached"] = True

    # Preserve current cclimits primary/secondary presentation, but classify
    # by actual duration rather than blindly trusting native slot position.
    for window in primary_snapshot["windows"]:
        slot = window["slot"]
        current = public.get(slot)
        # If multiple windows classify into the same slot, prefer the shorter
        # one for session quota and longer one for weekly/monthly quota.
        if isinstance(current, dict):
            old_duration = current.get("window_duration_minutes")
            new_duration = window.get("window_duration_minutes")
            if slot == "primary_window":
                if old_duration is not None and new_duration is not None and old_duration <= new_duration:
                    continue
            else:
                if old_duration is not None and new_duration is not None and old_duration >= new_duration:
                    continue

        rendered = {
            key: value
            for key, value in window.items()
            if key not in ("slot", "native_slot") and value is not None
        }
        public[slot] = rendered

    reset_credits = result.get("rateLimitResetCredits")
    if isinstance(reset_credits, dict):
        available = _finite_number(reset_credits.get("availableCount"))
        if available is not None:
            public["reset_credits_available"] = max(0, int(available))

    return public


def _write_message(proc: subprocess.Popen, message: dict) -> bool:
    if proc.stdin is None:
        return False
    try:
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()
        return True
    except (BrokenPipeError, OSError):
        return False


def _reader_thread(stream, output: queue.Queue) -> None:
    """Continuously move JSONL stdout into a queue so reads can time out."""
    try:
        for line in iter(stream.readline, ""):
            output.put(line)
    finally:
        output.put(None)


def _wait_for_response(
    output: queue.Queue,
    request_id: int,
    timeout: float,
    transcript: list[str],
) -> dict | None:
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        try:
            line = output.get(timeout=remaining)
        except queue.Empty:
            return None
        if line is None:
            return None
        transcript.append(line)
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(message, dict) or message.get("id") != request_id:
            continue
        return message


def _stop_process(proc: subprocess.Popen) -> None:
    """Best-effort cleanup; app-server is long-lived by design."""
    try:
        if proc.stdin is not None:
            proc.stdin.close()
    except OSError:
        pass
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=1)
    except (OSError, subprocess.SubprocessError):
        pass


def get_native_codex_usage(timeout: float = 10.0) -> dict | None:
    """Run Codex's read-only app-server quota RPC.

    app-server is a long-lived JSONL server, so this intentionally does not use
    subprocess.run()/communicate(): waiting for process exit would time out even
    after a perfectly valid response. The handshake follows Codex's documented
    lifecycle strictly: initialize -> wait response -> initialized notification
    -> account/rateLimits/read -> wait response -> terminate local helper.
    """
    command = _codex_command()
    if command is None:
        return None

    try:
        proc = subprocess.Popen(
            [*command, "app-server", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "error": "Codex native quota unavailable",
            # Do not expose the resolved executable path in normal JSON/cache
            # output; exception strings can contain a user's home directory.
            "details": f"{type(exc).__name__}: could not start Codex app-server",
            "native_source": "codex_app_server",
        }

    if proc.stdout is None:
        _stop_process(proc)
        return {
            "error": "Codex native quota unavailable",
            "details": "app-server stdout was unavailable",
            "native_source": "codex_app_server",
        }

    output: queue.Queue = queue.Queue()
    transcript: list[str] = []
    reader = threading.Thread(
        target=_reader_thread,
        args=(proc.stdout, output),
        daemon=True,
    )
    reader.start()

    # Divide the overall deadline across the two required request/response
    # phases while allowing either phase to consume the remaining time.
    deadline = time.monotonic() + timeout

    try:
        initialized = _write_message(
            proc,
            {
                "method": "initialize",
                "id": 1,
                "params": {
                    "clientInfo": {
                        "name": "cclimits",
                        "title": "cclimits",
                        "version": "0.1",
                    }
                },
            },
        )
        if not initialized:
            return {
                "error": "Codex native quota unavailable",
                "details": "could not write initialize request",
                "native_source": "codex_app_server",
            }

        init_response = _wait_for_response(
            output,
            1,
            max(0.1, deadline - time.monotonic()),
            transcript,
        )
        if init_response is None:
            return {
                "error": "Codex native quota unavailable",
                "details": "timed out waiting for initialize response",
                "native_source": "codex_app_server",
            }
        if "error" in init_response:
            return {
                "error": "Codex native quota unavailable",
                "details": "initialize request failed",
                "native_source": "codex_app_server",
            }

        # Official app-server sends this notification only after the initialize
        # response has arrived. Do not pipeline it with initialize.
        if not _write_message(proc, {"method": "initialized"}):
            return {
                "error": "Codex native quota unavailable",
                "details": "could not send initialized notification",
                "native_source": "codex_app_server",
            }

        if not _write_message(
            proc,
            # Current Codex schema defines this request's params as null and
            # permits them to be omitted. Do not send an empty object.
            {"method": "account/rateLimits/read", "id": 2},
        ):
            return {
                "error": "Codex native quota unavailable",
                "details": "could not write account/rateLimits/read request",
                "native_source": "codex_app_server",
            }

        rate_response = _wait_for_response(
            output,
            2,
            max(0.1, deadline - time.monotonic()),
            transcript,
        )
        if rate_response is None:
            return {
                "error": "Codex native quota unavailable",
                "details": "timed out waiting for account/rateLimits/read response",
                "native_source": "codex_app_server",
            }
        if "error" in rate_response:
            return {
                "error": "Codex native quota unavailable",
                "details": "account/rateLimits/read request failed",
                "native_source": "codex_app_server",
            }

        parsed = parse_app_server_output("\n".join(transcript))
        if parsed is not None:
            return parsed

        return {
            "error": "Codex native quota unavailable",
            "details": "app-server returned an unrecognized rate-limit schema",
            "native_source": "codex_app_server",
        }
    finally:
        _stop_process(proc)
