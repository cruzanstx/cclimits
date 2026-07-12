# System Patterns: cclimits

## Architecture

```
cclimits (npm package)
├── bin/cclimits.js     # Node wrapper (spawns Python)
└── lib/cclimits.py     # Main Python script

User runs: npx cclimits --oneline
  → Node wrapper spawns: python3 lib/cclimits.py --oneline
  → Python script fetches from APIs
  → Output to stdout
```

## Credential Discovery Pattern

Each tool has a `get_X_credentials()` function that checks multiple locations:

```python
def get_claude_credentials() -> str | None:
    # 1. macOS Keychain (if darwin)
    # 2. Linux credential files (~/.claude/.credentials.json)
    # 3. Environment variable fallback
```

**Priority**: Platform-specific → Config files → Environment variables

## HTTP Client Pattern

Dual implementation for zero-dependency operation:

```python
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

def http_get(url, headers):
    if HAS_REQUESTS:
        # Use requests library
    else:
        # Use urllib (stdlib)
```

## API Endpoints

| Tool | Endpoint | Auth |
|------|----------|------|
| Claude | `api.anthropic.com/api/oauth/usage` | Bearer token |
| Codex | `chatgpt.com/backend-api/wham/usage` | OAuth + account ID |
| Gemini | `cloudcode-pa.googleapis.com/v1internal:retrieveUserQuota` | OAuth |
| Z.AI | `api.z.ai/api/monitor/usage/quota/limit` | API key |

## Gemini OAuth Refresh

Gemini tokens expire every hour. Auto-refresh pattern:

```python
def get_gemini_credentials():
    # 1. Load from ~/.gemini/oauth_creds.json
    # 2. Check expiry_date
    # 3. If expired, call refresh_gemini_token()
    # 4. Save new tokens back to file
    # 5. Return fresh access_token
```

OAuth client credentials extracted from Gemini CLI installation (not hardcoded).

## Output Modes

| Mode | Flag | Use Case |
|------|------|----------|
| Detailed | (default) | Full analysis |
| JSON | `--json` | Scripting |
| One-liner | `--oneline [5h\|7d]` | Quick status |

## Error Handling

- Missing credentials → Show setup hint
- Expired tokens → Show refresh instructions
- API errors → Show error + fallback URL
- Network issues → Graceful failure per tool

## Provider Registry Pattern

All provider metadata lives in a single `PROVIDERS` list of dicts at module level. Each entry carries:

| Field | Purpose |
|-------|---------|
| `key` | Provider identifier (`"claude"`); used for argparse flag, results dict key, cache key |
| `title` | Display title for detailed output (`"Claude Code"`) |
| `oneline_label` | Prefix for oneline output (`"Claude"`) |
| `arg_help` | Help text for `--<key>` argparse flag |
| `fetch` | Fetch function name (string, looked up via `globals()` at call time for test patching) |
| `gated` | If `True`, `check_all` gates on credential probe before fetching |
| `creds` | Credential function name (string) for gated providers; `None` for ungated |
| `oneline_order` | Sort key for oneline display order (differs from registry/canonical order) |
| `render_oneline` | Function `(data, window, use_color) -> str | None`; returns `None` if data not renderable |

**Three oneline renderer patterns:**

1. **String percent-dual** (Claude, Codex): `_make_str_pct_renderer(label, ok_check, w5_key, w7d_key)` — factory for providers whose usage values are pre-formatted strings like `"45.5%"`.
2. **Balance** (OpenRouter, Kimi): `_make_balance_renderer(label, ok_key, get_balance)` — factory with shared threshold ladder (`<=0` ❌ / `<1` 🔴 / `<5` ⚠️ / else ✅).
3. **Custom** (Gemini, Antigravity, Z.AI, Synthetic): bespoke functions for tiered/summary/float-based data.

**Shared formatting helpers:**
- `_fmt_both(label, s5, s7, use_color)` — dual-window `X%/Y%` line
- `_fmt_single(label, inner, pct, suffix, use_color)` — single-window line; suffix goes outside color span
- `_fmt_balance(label, balance_str, balance, use_color)` — balance with threshold ladder

**Why `globals()` lookup:** Tests patch symbols like `cclimits.get_claude_usage` at module level. Storing function names as strings and resolving via `globals()` at call time ensures patched mocks are intercepted. Storing direct references would bypass the patch.

**Adding a new provider:**
1. Write a `get_X_usage()` function (and `get_X_credentials()` if gated)
2. Add one entry to `PROVIDERS` (use a factory for percent/balance renderers, or write a custom renderer)
3. No edits needed to `main()`, `print_oneline()`, or argparse setup

**Two ordering dimensions:**
- Registry order = canonical order for `main()` (argparse, dispatch, result collection, detailed output, JSON key order)
- `oneline_order` field = display order for `print_oneline()` (Z.AI and Synthetic appear before Gemini)
