# cclimits

[![CI](https://github.com/cruzanstx/cclimits/actions/workflows/ci.yml/badge.svg)](https://github.com/cruzanstx/cclimits/actions/workflows/ci.yml)

Check quota/usage for AI coding CLI tools: Claude Code, OpenAI Codex, Google Gemini CLI, Google Antigravity, Z.AI, OpenRouter, Kimi K2 (Moonshot AI), and Synthetic.new. It also supports checking keys used by **Aider** and **Continue**.

## Features

- **Auto-discovers credentials** from standard locations
- **Auto-refreshes expired tokens** (Gemini OAuth, Antigravity OAuth)
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

**Requires**: Python 3.9+ installed on your system.

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
cclimits --kimi       # Kimi only
cclimits --antigravity # Google Antigravity only
cclimits --synthetic  # Synthetic.new only
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
Claude: 4.0% (5h) ✅ | Codex: 0% (5h) ✅ | Z.AI: 1% (5h) ✅ | Gemini: ( 3-Flash 7% ✅ | Flash 1% ✅ | Pro 10% ✅ ) | OpenRouter: $47.91 ✅ | Kimi: $49.59 ✅ | Antigravity: 35% (8 models) ✅

# Both windows (--oneline both) - shows 5h/7d combined (Z.AI: tokens%/requests%)
Claude: 4.0%/10.0% ✅ | Codex: 0%/2% ✅ | Z.AI: 1%/0% ✅ | OpenRouter: $47.91 ✅

# No emoji mode (--noemoji) - colorizes percentages directly (green/yellow/red)
Claude: 4.0% (5h) | Codex: 0% (5h) | Z.AI: 1% (5h) | OpenRouter: $47.91 | Antigravity: 35% (8 models)
```

Status icons: ✅ ok · ⚠️ high usage · ❌ error · 🔑 no credentials found · ⏰ token expired. Cached results (`--cached`) are suffixed with their age, e.g. `(cached 42s)`.

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

==================================================
  Kimi K2 (Moonshot AI)
==================================================
  ✅ Connected

  Balance (USD):
    Total:     $49.5889
    Cash:      $3.0000
    Voucher:   $46.5889

==================================================
  Google Antigravity
==================================================
  ✅ Connected
  📦 Project: my-cloud-code-project
  📊 Tier: free

  Model Quotas:
    Models:    8
    Tightest:  65% remaining
    Average:   83% remaining

    Model                             Remaining  Reset
    -------------------------------- ----------  ----------------
    claude-opus-4-5-thinking               65%  2026-05-30T18:00:00Z
    claude-sonnet-4-6                      71%  2026-05-30T18:00:00Z
    gemini-3-flash                         88%  2026-05-30T18:00:00Z

==================================================
  Synthetic.new
==================================================
  ✅ Connected

  Subscription:
    Used:      0 / 1,500 (0%)
    Remaining: 1,500
    Renews in: 4h 59m

  5-Hour Rolling:
    Used:      0 / 1,500 (0%)
    Remaining: 1,500
    Next tick: 0h 1m

  Weekly Credits:
    Remaining: $72.00 / $72.00 (100%)
    Next regen: 2h 53m (+$1.44)
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
| **Kimi** | `$MOONSHOT_API_KEY` environment variable |
| **Antigravity** | `~/.gemini/antigravity-cli/antigravity-oauth-token` (auto-refreshes); fallback `$ANTIGRAVITY_REFRESH_TOKEN` / `$ANTIGRAVITY_ACCESS_TOKEN` |
| **Synthetic.new** | `$SYNTHETIC_API_KEY` environment variable |

## Setup (One-Time)

If credentials are missing, run the corresponding CLI tool to authenticate:

```bash
claude           # Login to Claude Code
codex login      # Login to OpenAI Codex
gemini           # Login to Gemini CLI
agy -p hello                 # Login to Google Antigravity (prompts for OAuth)
export ZAI_KEY=your-key           # Add to ~/.zshrc or ~/.bashrc
export OPENROUTER_API_KEY=your-key  # Add to ~/.zshrc or ~/.bashrc
export MOONSHOT_API_KEY=your-key    # Add to ~/.zshrc or ~/.bashrc
export SYNTHETIC_API_KEY=your-key   # Add to ~/.zshrc or ~/.bashrc
```

### Antigravity Authentication

The `agy` CLI writes its OAuth tokens to `~/.gemini/antigravity-cli/antigravity-oauth-token`; cclimits reads that file and auto-refreshes the access token via Google's OAuth endpoint. As a fallback (e.g. shared CI machines without the agy install), set `ANTIGRAVITY_REFRESH_TOKEN` (or `ANTIGRAVITY_ACCESS_TOKEN`) in your environment.

### Gemini Token Refresh

For Gemini token auto-refresh to work, cclimits needs OAuth client credentials. It will automatically extract these from your Gemini CLI installation. If that fails, set environment variables:

```bash
# Extract from Gemini CLI (run once to get values)
grep -E "CLIENT_(ID|SECRET)" ~/.npm/_npx/*/node_modules/@google/gemini-cli-core/dist/src/code_assist/oauth2.js

# Then add to ~/.zshrc or ~/.bashrc
export GEMINI_OAUTH_CLIENT_ID="..."
export GEMINI_OAUTH_CLIENT_SECRET="..."
```

## BYOK & Other Tools

`cclimits` can monitor usage for "Bring Your Own Key" (BYOK) tools by checking the underlying provider directly:

- **Aider / Continue**: If you use these with an API key (OpenAI, Anthropic, OpenRouter, Gemini), simply set the corresponding environment variable (e.g., `OPENROUTER_API_KEY`) and run `cclimits --openrouter` (or the relevant flag) to check your balance/quota.

**Note on Integrated Providers:**
- **GitHub Copilot**: Currently not supported as GitHub does not expose a public API for individual user quota/rate limits.
- **Cursor / Windsurf**: Not supported yet as they do not provide public quota APIs.

## Requirements

- Python 3.9+
- `requests` library (optional, falls back to urllib)

## License

MIT
