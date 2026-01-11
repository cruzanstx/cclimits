# Progress

## Working Features

- **Claude Code**: OAuth token from keychain (macOS) or `~/.claude/.credentials.json` (Linux)
- **OpenAI Codex**: JWT from `~/.codex/auth.json`
- **Gemini CLI**: OAuth from `~/.gemini/oauth_creds.json`, auto-refreshes expired tokens
- **Z.AI**: API token from environment variable (`$ZAI_KEY` or `$ZAI_API_KEY`), 5h shared quota
- **OpenRouter**: API token from environment variable (`$OPENROUTER_API_KEY`)
- **Display modes**: JSON, detailed, compact one-liner, noemoji color mode
- **Time windows**: 5h and 7d for Claude/Codex, 5h for Z.AI (shared across GLM models)
- **BYOK Support**: Explicit documentation for monitoring Aider/Continue via their underlying provider keys.

## Current Status

- ✅ All core AI tool integrations functional
- ✅ Cross-platform credential detection (macOS/Linux)
- ✅ npm package published as `cclimits`
- ✅ Gemini models grouped by quota tier (3-Flash, Flash, Pro)
- ✅ Research on additional providers completed (`research/ai-coding-providers.md`)

## Known Issues

None currently.

## What's Left to Build

### High Priority
- **Replit Integration**: Endpoint identified (`usage-credits-balance`), awaiting implementation.

### Medium Priority
- Add automated tests for all integrations
- CI/CD pipeline for npm publishing
- Better error messages for missing credentials

### Low Priority
- TypeScript rewrite to remove Python dependency
- **Cursor / Windsurf / Copilot**: Feasibility is currently low due to lack of public APIs.
- Configurable output formats
- Historical usage tracking