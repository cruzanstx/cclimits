# Progress

## Working Features

- **Claude Code**: OAuth token from keychain (macOS) or `~/.claude/.credentials.json` (Linux)
- **OpenAI Codex**: JWT from `~/.codex/auth.json`
- **Gemini CLI**: OAuth from `~/.gemini/oauth_creds.json`, auto-refreshes expired tokens
- **Z.AI**: API token from environment variable (`$ZAI_KEY` or `$ZAI_API_KEY`)
- **Display modes**: JSON, detailed, compact one-liner
- **Time windows**: 5h and 7d for Claude and Codex

## Current Status

- ✅ All AI tool integrations functional
- ✅ Cross-platform credential detection (macOS/Linux)
- ✅ npm package published as `cclimits`
- ✅ Gemini models grouped by quota tier (3-Flash, Flash, Pro)

## Known Issues

None currently.

## What's Left to Build

### High Priority
- None identified

### Medium Priority
- Add automated tests for all integrations
- CI/CD pipeline for npm publishing
- Better error messages for missing credentials

### Low Priority
- TypeScript rewrite to remove Python dependency
- Add more AI coding providers with subscription limits:
  - Cursor Pro (has usage limits)
  - Windsurf Pro (has usage limits)
  - GitHub Copilot (if quota API available)
  - Sourcegraph Cody (if quota API available)
- Configurable output formats
- Historical usage tracking
