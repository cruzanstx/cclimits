# Active Context

## Current Focus

- **2026-09-03**: Zero-config Claude quota discovery (PR #3) merged + documented; v1.7.0 publish in progress
- Researching additional AI coding providers (Cursor, MiniMax, OpenCode Zen, Replit)

## Recent Changes (Last 7 Days)

- **2026-08-05**: **GitHub Copilot integration** — monthly premium-request quota via undocumented `copilot_internal/user`; credential chain apps.json → hosts.json → gh hosts.yml → GITHUB_TOKEN; no-subscription tokens hidden from check-all (Gemini pattern); 232 → 261 tests. Key research reversal: endpoint accepts plain PATs, so the Jan "Low feasibility" rating no longer holds. Prompt `prompts/providers/011-github-copilot-integration.md` is now obsolete (written under the old assumption).

- **2026-07-12**: **v1.3.0 released** — first release through the new tag-push pipeline (npm Trusted Publishing/OIDC, provenance attested). Five changes in one release, see `deltas.md`: cache-hit bypass bug fix (openrouter/kimi/antigravity/synthetic no longer fetch live on cache hits), concurrent provider fetching (ThreadPoolExecutor; wall time ≈ slowest provider), GitHub Actions CI (3.9/3.11/3.13 × requests/urllib matrix) + automated publish, data-driven `PROVIDERS` registry refactor (byte-identical output, −93 lines), stale-cache fallback (transient failures serve <24h-old good entries with stale marker). Suite: 155 → 205 tests
- Publishing gotchas hit and fixed: `setup-node` `registry-url` breaks the OIDC exchange (E404); newer npm strips `./`-prefixed bin paths at publish (would have broken `npx cclimits`) — `npm pkg fix` applied
- **2026-07-02**: v1.2.15–1.2.18 released — see `deltas.md`: cache merge, atomic cache writes, provider filters on cache hits, cached-output age labels, Z.AI data cleanup, distinct oneline icons (🔑/⏰/❌)

## Blocked/Waiting

- Replit integration requires a Replit account/token for implementation/testing.

## Next Steps

1. Implement Replit support (High feasibility endpoint identified; blocked on a Replit token — prompts/providers/013)
3. Monitor Cursor (cookie-only usage API), MiniMax coding plan (`coding_plan/remains` rejects API keys — MiniMax-AI/MiniMax-M2#88), and OpenCode Zen balance (feature request anomalyco/opencode#10448)
4. Possible future: Gemini legacy OAuth auto-refresh (CLI retired 2026-06-18; expired token now visible as ⏰ in oneline)

## Key Patterns

- **BYOK Tools**: Aider and Continue use standard API keys; `cclimits` supports them indirectly by monitoring the underlying provider (OpenAI/Anthropic/etc).
- **Integrated Tools**: Cursor, Windsurf, Copilot, JetBrains have "hidden" or internal-only usage APIs, making CLI integration difficult without reverse engineering.
- **Replit**: Uses a specific "usage credits" model with a likely accessible endpoint.