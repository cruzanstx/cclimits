# CLAUDE.md

Project instructions for Claude Code when working in this repository.

## Quick Orientation

**cclimits** is a CLI tool that checks quota/usage for AI coding assistants (Claude Code, OpenAI Codex, Google Gemini CLI, Z.AI). Distributed via npm, runs Python under the hood.

**Repository**: https://github.com/cruzanstx/cclimits
**npm**: https://www.npmjs.com/package/cclimits

## Project Structure

```
cclimits/
├── bin/
│   └── cclimits.js      # Node wrapper (spawns Python)
├── lib/
│   └── cclimits.py      # Main script (~1000 lines)
├── memory-bank/         # AI context files (read these first)
├── package.json         # npm config
├── README.md
├── LICENSE              # MIT
└── CLAUDE.md            # This file
```

## Memory Bank

Read `memory-bank/` files at the start of each task:
1. `deltas.md` - Most recent changes
2. `activeContext.md` - Current focus
3. `progress.md` - What works, known issues
4. `systemPatterns.md` - Architecture patterns
5. `techContext.md` - Tech stack, commands

## Key Patterns

### Dual Distribution
- **npm package**: Users run `npx cclimits`
- **Node wrapper** (`bin/cclimits.js`): Spawns Python
- **Python script** (`lib/cclimits.py`): Does actual work

### Credential Discovery
Each tool has a `get_X_credentials()` function that checks:
1. Platform-specific storage (macOS Keychain)
2. Config files (~/.claude, ~/.codex, ~/.gemini)
3. Environment variables (fallback)

### HTTP Client
Zero-dependency fallback pattern:
```python
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
```

### No Hardcoded Secrets
Gemini OAuth credentials are extracted from the user's Gemini CLI installation, not hardcoded (GitHub push protection).

## Commands

```bash
# Development
python3 lib/cclimits.py --oneline
python3 lib/cclimits.py --json

# Test via npx (uses published version)
npx cclimits

# Test local changes via npx
npm link
npx cclimits
npm unlink

# Publish new version
npm version patch  # bumps to x.x.X
npm version minor  # bumps to x.X.0
npm publish
git push --tags
```

## Publishing Workflow

1. Make changes to `lib/cclimits.py`
2. Update `memory-bank/deltas.md` and `progress.md`
3. Bump version: `npm version patch`
4. Publish: `npm publish`
5. Push tags: `git push --tags`

**Note**: npm publish requires 2FA or automation token with bypass.

## API Endpoints

| Tool | Endpoint | Auth Header |
|------|----------|-------------|
| Claude | `api.anthropic.com/api/oauth/usage` | `Bearer {token}` |
| Codex | `chatgpt.com/backend-api/wham/usage` | `Bearer {oauth}` + `chatgpt-account-id` |
| Gemini | `cloudcode-pa.googleapis.com/v1internal:retrieveUserQuota` | `Bearer {oauth}` |
| Z.AI | `api.z.ai/api/monitor/usage/quota/limit` | `Authorization: {api_key}` |

## Testing Checklist

Before publishing:
- [ ] `python3 lib/cclimits.py` - All tools checked
- [ ] `python3 lib/cclimits.py --oneline` - Compact output works
- [ ] `python3 lib/cclimits.py --json` - Valid JSON output
- [ ] `python3 lib/cclimits.py --claude` - Single tool filter works
- [ ] Test on machine without `requests` installed (urllib fallback)

## Known Limitations

1. **Python required**: npm package needs Python 3.10+ on user's system
2. **Gemini OAuth**: Must have Gemini CLI installed for token refresh
3. **Z.AI**: No 5h/7d window, only total quota percentage
4. **Codex API key mode**: No quota info (only OAuth has it)
5. **Windows**: Untested, may have path issues
