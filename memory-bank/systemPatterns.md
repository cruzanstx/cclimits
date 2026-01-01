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
