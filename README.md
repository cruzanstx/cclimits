# cclimits

Check quota/usage for AI coding CLI tools: Claude Code, OpenAI Codex, Google Gemini CLI, Z.AI, and OpenRouter.

## Features

- **Auto-discovers credentials** from standard locations
- **Auto-refreshes expired tokens** (Gemini OAuth) and persists them
- **Multiple output formats**: detailed, JSON, compact one-liner
- **Caching support** for fast statusline integration
- **Cross-platform**: macOS and Linux support

## Installation

### Via npm (recommended)

```bash
# Run directly without installing
npx cclimits

# Or install globally
npm install -g cclimits
cclimits
```

**Requires**: Python 3.10+ installed on your system.

### Via Git

```bash
# Clone and symlink
git clone https://github.com/cruzanstx/cclimits.git
ln -s $(pwd)/cclimits/lib/cclimits.py ~/.local/bin/cclimits

# Or just download
curl -o ~/.local/bin/cclimits https://raw.githubusercontent.com/cruzanstx/cclimits/main/lib/cclimits.py
chmod +x ~/.local/bin/cclimits
```

## Usage

```bash
cclimits              # Check all tools (detailed)
cclimits --claude     # Claude only
cclimits --codex      # Codex only
cclimits --gemini     # Gemini only
cclimits --zai        # Z.AI only
cclimits --openrouter # OpenRouter only
cclimits --json       # JSON output
cclimits --oneline           # Compact one-liner (5h window)
cclimits --oneline 7d        # Compact one-liner (7d window)
cclimits --oneline both      # Compact one-liner (5h/7d combined)
cclimits --oneline --noemoji # Color-coded text instead of emojis

# Caching (for statusline integration)
cclimits --oneline --cached        # Use cache if fresh (<60s)
cclimits --oneline --cache-ttl 30  # Custom TTL in seconds
```

## Example Output

### Compact One-liner (--oneline)

```bash
# Single window (5h or 7d)
Claude: 4.0% (5h) ✅ | Codex: 0% (5h) ✅ | Z.AI: 1% (5h) ✅ | Gemini: ( 3-Flash 7% ✅ | Flash 1% ✅ | Pro 10% ✅ ) | OpenRouter: $47.91 ✅

# Both windows (--oneline both) - shows 5h/7d combined
Claude: 4.0%/10.0% ✅ | Codex: 0%/2% ✅ | Z.AI: 1% (5h) ✅ | OpenRouter: $47.91 ✅

# No emoji mode (--noemoji) - colorizes percentages directly (green/yellow/red)
Claude: 4.0% (5h) | Codex: 0% (5h) | Z.AI: 1% (5h) | OpenRouter: $47.91
```

### Detailed Output (default)

```
🔍 AI CLI Usage Checker
   2025-12-31 21:30:00

==================================================
  Claude Code
==================================================
  🔑 Auth: Bearer token
  ✅ Connected

  5-Hour Window:
    Used:      15.2%
    Remaining: 84.8%
    Resets in: 3h 24m

  7-Day Window:
    Used:      42.0%
    Remaining: 58.0%
    Resets in: 4d 12h

==================================================
  OpenAI Codex
==================================================
  🔑 Auth: OAuth (ChatGPT)
  ✅ Connected
  📊 Plan: pro

  5h Window:
    Used:      8%
    Remaining: 92%
    Resets in: 2h 15m

==================================================
  Gemini CLI
==================================================
  🔑 Auth: OAuth (Google Account)
  ✅ Connected
  📊 Tier: standard

  Quota by Tier:
    3-Flash: 7.0% used, 93.0% remaining
    Flash: 1.0% used, 99.0% remaining
    Pro: 10.0% used, 90.0% remaining

==================================================
  Z.AI (5h shared - GLM-4.x)
==================================================
  ✅ Connected

  Token Quota (5h window):
    Used:      1%
    Remaining: 99%
    Resets in: 4h 30m
    (10,000 / 1,000,000 tokens)

==================================================
  OpenRouter
==================================================
  ✅ Connected

  Balance:     $47.91
  Total Used:  $2.09
```

## Status Icons

| Icon | Meaning |
|------|---------|
| ✅ | Under 70% - plenty of capacity |
| ⚠️ | 70-90% - moderate usage |
| 🔴 | 90-100% - near limit |
| ❌ | 100% or unavailable |

## Credential Locations

Credentials are auto-discovered from these locations:

| Tool | Location |
|------|----------|
| **Claude** | `~/.claude/.credentials.json` (Linux) or macOS Keychain |
| **Codex** | `~/.codex/auth.json` |
| **Gemini** | `~/.gemini/oauth_creds.json` (auto-refreshes) |
| **Z.AI** | `$ZAI_KEY` or `$ZAI_API_KEY` environment variable |
| **OpenRouter** | `$OPENROUTER_API_KEY` environment variable |

## Setup (One-Time)

If credentials are missing, run the corresponding CLI tool to authenticate:

```bash
claude           # Login to Claude Code
codex login      # Login to OpenAI Codex
gemini           # Login to Gemini CLI
export ZAI_KEY=your-key           # Add to ~/.zshrc or ~/.bashrc
export OPENROUTER_API_KEY=your-key  # Add to ~/.zshrc or ~/.bashrc
```

### Gemini Token Refresh

For Gemini token auto-refresh to work, cclimits needs OAuth client credentials. It will automatically extract these from your Gemini CLI installation. If that fails, set environment variables:

```bash
# Extract from Gemini CLI (run once to get values)
grep -E "CLIENT_(ID|SECRET)" ~/.npm/_npx/*/node_modules/@google/gemini-cli-core/dist/src/code_assist/oauth2.js

# Then add to ~/.zshrc or ~/.bashrc
export GEMINI_OAUTH_CLIENT_ID="..."
export GEMINI_OAUTH_CLIENT_SECRET="..."
```

## Requirements

- Python 3.10+
- `requests` library (optional, falls back to urllib)

## License

MIT
