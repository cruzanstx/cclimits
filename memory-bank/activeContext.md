# Active Context

## Current Focus

- Cache robustness + status-visibility hardening complete (v1.2.15–1.2.18, 2026-07-02); back to maintenance
- Researching additional AI coding providers (Cursor, Copilot, Replit, etc.)

## Recent Changes (Last 7 Days)

- **2026-07-02**: v1.2.15–1.2.18 released — see `deltas.md`: cache merge (no-creds/partial runs no longer clobber good entries), atomic cache writes, provider filters honored on cache hits, cached-output age labels, Z.AI data cleanup (no fake token counts, plan level, tokens%/requests% in `both` mode), distinct oneline icons (🔑 no credentials, ⏰ expired token, ❌ real error)
- Root cause that kicked this off: a background statusline/cron shell without `ZAI_API_KEY` was poisoning the shared cache, so `--oneline --cached` showed `Z.AI: ❌` while direct probes were healthy

## Blocked/Waiting

- Replit integration requires a Replit account/token for implementation/testing.

## Next Steps

1. Implement Replit support (High feasibility endpoint identified)
2. Monitor GitHub Copilot/Cursor for future public API availability
3. ~~Add CI/CD for automated npm publishing~~ ✅ Done (2026-07-12) — `.github/workflows/ci.yml` runs tests on push/PR; `.github/workflows/publish.yml` publishes on `v*` tags via `NPM_TOKEN` secret
4. Possible future: Gemini legacy OAuth auto-refresh (CLI retired 2026-06-18; expired token now visible as ⏰ in oneline)

## Key Patterns

- **BYOK Tools**: Aider and Continue use standard API keys; `cclimits` supports them indirectly by monitoring the underlying provider (OpenAI/Anthropic/etc).
- **Integrated Tools**: Cursor, Windsurf, Copilot, JetBrains have "hidden" or internal-only usage APIs, making CLI integration difficult without reverse engineering.
- **Replit**: Uses a specific "usage credits" model with a likely accessible endpoint.