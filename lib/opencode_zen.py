"""Zero-config OpenCode Zen credential discovery.

Reads credentials already configured by OpenCode, Pi, or Oh My Pi (OMP).
All sources are read-only. Raw keys are kept in memory only and are never
printed by the caller.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        normalized = os.path.normcase(os.path.abspath(str(path)))
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(path)
    return result


def opencode_auth_paths() -> list[Path]:
    paths: list[Path] = []
    if xdg := os.environ.get("XDG_DATA_HOME"):
        paths.append(Path(xdg).expanduser() / "opencode" / "auth.json")
    paths.append(Path.home() / ".local" / "share" / "opencode" / "auth.json")
    return _dedupe_paths(paths)


def pi_auth_paths() -> list[Path]:
    paths: list[Path] = []
    if agent_dir := os.environ.get("PI_CODING_AGENT_DIR"):
        paths.append(Path(agent_dir).expanduser() / "auth.json")
    paths.append(Path.home() / ".pi" / "agent" / "auth.json")
    return _dedupe_paths(paths)


def omp_agent_dirs() -> list[Path]:
    home = Path.home()
    config_name = os.environ.get("PI_CONFIG_DIR") or ".omp"
    root = home / config_name
    paths: list[Path] = []

    if agent_dir := os.environ.get("PI_CODING_AGENT_DIR"):
        paths.append(Path(agent_dir).expanduser())

    profile = os.environ.get("OMP_PROFILE")
    if profile is None:
        profile = os.environ.get("PI_PROFILE")
    if profile and profile.strip() and profile.strip() != "default":
        paths.append(root / "profiles" / profile.strip() / "agent")

    paths.append(root / "agent")

    profiles = root / "profiles"
    try:
        if profiles.is_dir():
            paths.extend(p / "agent" for p in profiles.iterdir() if p.is_dir())
    except OSError:
        pass

    if xdg := os.environ.get("XDG_DATA_HOME"):
        paths.append(Path(xdg).expanduser() / "omp")

    return _dedupe_paths(paths)


def omp_db_paths() -> list[Path]:
    return _dedupe_paths([directory / "agent.db" for directory in omp_agent_dirs()])


def _literal_api_key(entry: object) -> str | None:
    if isinstance(entry, str):
        value = entry.strip()
        return value or None
    if not isinstance(entry, dict):
        return None

    auth_type = entry.get("type")
    if auth_type not in (None, "api", "api_key"):
        return None
    for name in ("key", "apiKey", "api_key"):
        value = entry.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _read_json_key(path: Path, provider_ids: tuple[str, ...]) -> str | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    for provider_id in provider_ids:
        if key := _literal_api_key(raw.get(provider_id)):
            return key
    return None


def _read_omp_key(path: Path) -> str | None:
    """Read OMP agent.db using SQLite read-only mode."""
    if not path.is_file():
        return None
    conn = None
    try:
        uri = path.resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=1)
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(auth_credentials)").fetchall()
            if len(row) > 1
        }
        if not {"provider", "credential_type", "data"}.issubset(columns):
            return None

        sql = "SELECT credential_type, data FROM auth_credentials WHERE provider = ?"
        if "disabled_cause" in columns:
            sql += " AND disabled_cause IS NULL"
        if "id" in columns:
            sql += " ORDER BY id DESC"

        for credential_type, data in conn.execute(sql, ("opencode-zen",)).fetchall():
            if credential_type != "api_key" or not isinstance(data, str):
                continue
            try:
                parsed = json.loads(data)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                parsed = {"type": "api_key", **parsed}
            if key := _literal_api_key(parsed):
                return key
    except (OSError, sqlite3.Error):
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass
    return None


def _parse_env_key(path: Path, key_name: str = "OPENCODE_API_KEY") -> str | None:
    """Read one literal dotenv assignment without executing shell code."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, sep, value = line.partition("=")
        if not sep or name.strip() != key_name:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if not value or "$" in value or "`" in value:
            return None
        return value
    return None


def omp_env_paths() -> list[Path]:
    paths: list[Path] = []
    try:
        paths.append(Path.cwd() / ".env")
    except OSError:
        pass
    for agent_dir in omp_agent_dirs():
        paths.append(agent_dir / ".env")
        paths.append(agent_dir.parent / ".env")
    paths.append(Path.home() / ".env")
    return _dedupe_paths(paths)


def discover_credentials() -> list[dict]:
    """Collect and deduplicate Zen API keys from all supported harnesses."""
    found: list[tuple[str, str, str]] = []

    if value := os.environ.get("OPENCODE_API_KEY"):
        if value.strip():
            found.append((value.strip(), "environment", "$OPENCODE_API_KEY"))

    if raw := os.environ.get("OPENCODE_AUTH_CONTENT"):
        try:
            auth = json.loads(raw)
        except json.JSONDecodeError:
            auth = None
        if isinstance(auth, dict):
            if key := _literal_api_key(auth.get("opencode")):
                found.append((key, "opencode", "$OPENCODE_AUTH_CONTENT"))

    for path in opencode_auth_paths():
        if key := _read_json_key(path, ("opencode",)):
            found.append((key, "opencode", "OpenCode auth.json"))

    for path in pi_auth_paths():
        if key := _read_json_key(path, ("opencode", "opencode-zen")):
            found.append((key, "pi", "Pi auth.json"))

    for path in omp_db_paths():
        if key := _read_omp_key(path):
            found.append((key, "omp", "OMP agent.db"))

    for path in omp_env_paths():
        if key := _parse_env_key(path):
            found.append((key, "omp-env", "OMP .env"))

    by_fingerprint: dict[str, dict] = {}
    for key, harness, source in found:
        fingerprint = _fingerprint(key)
        item = by_fingerprint.setdefault(
            fingerprint,
            {
                "key": key,
                "fingerprint": fingerprint,
                "harnesses": [],
                "sources": [],
            },
        )
        if harness not in item["harnesses"]:
            item["harnesses"].append(harness)
        if source not in item["sources"]:
            item["sources"].append(source)

    return list(by_fingerprint.values())
