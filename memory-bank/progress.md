# Progress

## Working Features

- **Claude Code**: OAuth token from keychain (macOS) or `~/.claude/.credentials.json` (Linux)
- **OpenAI Codex**: JWT from `~/.codex/auth.json`
- **Gemini CLI** (legacy — CLI retired 2026-06-18): OAuth from `~/.gemini/oauth_creds.json`; token refresh needs an installed Gemini CLI package or env overrides, otherwise reports ⏰ expired
- **Google Antigravity**: OAuth tokens read from `~/.gemini/antigravity-cli/antigravity-oauth-token` (written by `agy` CLI) or `ANTIGRAVITY_REFRESH_TOKEN`; per-model quota tracking, live-verified against real install
- **Z.AI**: API token from environment variable (`$ZAI_KEY` or `$ZAI_API_KEY`), 5h shared quota
- **OpenRouter**: API token from environment variable (`$OPENROUTER_API_KEY`)
- **Kimi K2 (Moonshot)**: API token from env var (`$MOONSHOT_API_KEY`), prepaid balance tracking
- **Synthetic.new**: API token from env var (`$SYNTHETIC_API_KEY`), reports subscription/rolling-5h/weekly-credits buckets via `GET /v2/quotas` (free probe)
- **Display modes**: JSON, detailed, compact one-liner, noemoji color mode; oneline distinguishes 🔑 no credentials / ⏰ expired token / ❌ real error
- **Time windows**: 5h and 7d for Claude/Codex, 5h for Z.AI (shared across GLM models; `both` mode shows tokens%/requests%), 5h rolling + weekly credits for Synthetic.new
- **Caching** (`--cached`, `~/.cache/cclimits/usage.json`): atomic writes (temp + rename), merge on write (no-creds/partial runs preserve prior good entries), provider filters honored on cache hits (refetch if a requested provider is missing), output labeled with cache age
- **BYOK Support**: Explicit documentation for monitoring Aider/Continue via their underlying provider keys.

## Current Status

- ✅ All core AI tool integrations functional (Claude, Codex, Gemini, Antigravity, Z.AI, OpenRouter, Kimi, Synthetic.new)
- ✅ Full local pytest suite passes with isolated cache and module-level patch targets
- ✅ Cross-platform credential detection (macOS/Linux)
- ✅ npm package published as `cclimits`
- ✅ Gemini models grouped by quota tier (3-Flash, Flash, Pro)
- ✅ Antigravity models sorted by tightest remaining quota with min/avg summary; compact oneline displays tightest model usage percentage
- ✅ Research on additional providers completed (`research/ai-coding-providers.md`)
- ✅ Providers fetched concurrently; cache hits skip all network/credential calls; transient failures fall back to <24h-old cached data with stale marker (v1.3.0)
- ✅ Data-driven `PROVIDERS` registry — adding a provider is one registry entry + one fetch function
- ✅ CI (GitHub Actions matrix) + automated npm publish on `v*` tags via Trusted Publishing (OIDC); 205 tests

## Known Issues

None currently.

## What's Left to Build

### High Priority
- **Replit Integration**: Endpoint identified (`usage-credits-balance`), awaiting implementation.

### Medium Priority
- ~~CI/CD pipeline for npm publishing~~ ✅ Done (2026-07-12) — GitHub Actions workflows added for CI (pytest on push/PR) and automated publish (tag push → npm with provenance)
- Gemini legacy OAuth auto-refresh or graceful retirement (CLI retired 2026-06-18; expired token renders ⏰)

### Low Priority
- TypeScript rewrite to remove Python dependency
- **Cursor / Windsurf / Copilot**: Feasibility is currently low due to lack of public APIs.
- Configurable output formats
- Historical usage tracking
