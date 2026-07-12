# Active Context

## Current Focus

- v1.3.0 released 2026-07-12 via the new automated pipeline; back to maintenance
- Researching additional AI coding providers (Cursor, Copilot, Replit, etc.)

## Recent Changes (Last 7 Days)

- **2026-07-12**: **v1.3.0 released** — first release through the new tag-push pipeline (npm Trusted Publishing/OIDC, provenance attested). Five changes in one release, see `deltas.md`: cache-hit bypass bug fix (openrouter/kimi/antigravity/synthetic no longer fetch live on cache hits), concurrent provider fetching (ThreadPoolExecutor; wall time ≈ slowest provider), GitHub Actions CI (3.9/3.11/3.13 × requests/urllib matrix) + automated publish, data-driven `PROVIDERS` registry refactor (byte-identical output, −93 lines), stale-cache fallback (transient failures serve <24h-old good entries with stale marker). Suite: 155 → 205 tests
- Publishing gotchas hit and fixed: `setup-node` `registry-url` breaks the OIDC exchange (E404); newer npm strips `./`-prefixed bin paths at publish (would have broken `npx cclimits`) — `npm pkg fix` applied
- **2026-07-02**: v1.2.15–1.2.18 released — see `deltas.md`: cache merge, atomic cache writes, provider filters on cache hits, cached-output age labels, Z.AI data cleanup, distinct oneline icons (🔑/⏰/❌)

## Blocked/Waiting

- Replit integration requires a Replit account/token for implementation/testing.

## Next Steps

1. Implement Replit support (High feasibility endpoint identified)
2. Monitor GitHub Copilot/Cursor for future public API availability
3. ~~Add CI/CD for automated npm publishing~~ ✅ Done (2026-07-12) — `.github/workflows/ci.yml` runs tests on push/PR; `.github/workflows/publish.yml` publishes on `v*` tags via npm Trusted Publishing (OIDC, no token)
4. Possible future: Gemini legacy OAuth auto-refresh (CLI retired 2026-06-18; expired token now visible as ⏰ in oneline)

## Key Patterns

- **BYOK Tools**: Aider and Continue use standard API keys; `cclimits` supports them indirectly by monitoring the underlying provider (OpenAI/Anthropic/etc).
- **Integrated Tools**: Cursor, Windsurf, Copilot, JetBrains have "hidden" or internal-only usage APIs, making CLI integration difficult without reverse engineering.
- **Replit**: Uses a specific "usage credits" model with a likely accessible endpoint.