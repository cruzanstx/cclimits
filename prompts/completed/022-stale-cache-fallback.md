<objective>
Add stale-cache fallback to `lib/cclimits.py`: when a live fetch fails with a transient/network error but the cache holds a previous good entry for that provider, serve the stale entry (clearly labeled with its age) instead of showing ❌.

Rationale: the cache-merge work (v1.2.15) already established the principle that a run that CAN'T check a provider shouldn't destroy known-good data. The same principle should apply at display time — a 30-minute-old quota reading is far more useful in a statusline than an error icon caused by a blip in one provider's API.
</objective>

<context>
Project: cclimits — read `CLAUDE.md`, `memory-bank/deltas.md`, and `memory-bank/systemPatterns.md` first; this builds directly on the existing cache machinery (`read_cache`, `write_cache`, `merge_cache_data`, `NO_CREDS_ERROR`, `format_cache_age`).

Design decisions to respect (think carefully about each):
1. **Which failures qualify for fallback**: transient failures only — connection errors (`http_get` returns status 0), HTTP 5xx, and generic `"API error"` / `"Could not fetch usage"` results. NOT `No credentials found` (config issue, 🔑 is correct), NOT expired tokens (⏰ is actionable), NOT 401/invalid-key (user must act).
2. **What counts as a good cached entry**: `status` of `ok`/`authenticated` — reuse the same notion of "good" that `merge_cache_data` implies.
3. **Staleness bound**: don't serve arbitrarily old data. Add a cap (suggest 24h, as a module constant) beyond which the error is shown as today.
4. **Labeling**: a substituted entry must be visibly stale. Suggested: annotate the entry (e.g. `stale_age_seconds`) and render a suffix in oneline (e.g. `Z.AI: 1% (5h) ✅ (stale 32m)` or a distinct 💤/(stale Xm) marker) and a line in detailed output. JSON output should carry the annotation so scripted consumers can detect it. Keep the exact rendering choice simple and consistent with existing style (`format_cache_age`).
5. **Where it hooks in**: after live fetches complete in `main()`, before output — read the cache file WITHOUT the TTL constraint (this needs a way to read stale data; extend `read_cache` with an `ignore_ttl`/max-age parameter or a sibling helper rather than duplicating parsing).
6. This must work in BOTH modes: plain runs and `--cached` runs whose TTL missed (a TTL miss followed by a failed fetch is exactly the statusline scenario that motivated the v1.2.15 work).
7. The cache WRITE path must store the fresh error result or preserve the old good one per existing `merge_cache_data` semantics — decide deliberately whether transient errors should also not clobber good entries in the cache (extending the merge rule), and document the choice in the delta entry.
</context>

<requirements>
1. Implement the fallback with the qualification rules above; keep it self-contained (a `apply_stale_fallback(results, ...)` style function is testable).
2. Annotate substituted entries in the results dict; render the stale marker in oneline, detailed, and pass it through in JSON.
3. Add the staleness cap as a named constant.
4. No new flags required; if you judge an opt-out worthwhile, `--no-stale-fallback` is acceptable but keep the default ON.
</requirements>

<verification>
```bash
cd /storage/projects/docker/cclimits && python3 -m pytest tests/ -v
```

- [ ] New tests: transient error + fresh-enough good cache entry → stale entry served with annotation; oneline shows the stale marker.
- [ ] New tests: `No credentials found` / expired-token / 401 results are NOT replaced.
- [ ] New test: cached entry older than the cap → error shown, no substitution.
- [ ] New test: JSON output contains the stale annotation.
- [ ] Full existing suite passes.

Manual smoke check: run once to populate cache, then simulate failure (e.g. unset a provider's network by pointing at an unreachable env or temporarily patch) and confirm the stale rendering.
</verification>

<output>
Modify:
- `./lib/cclimits.py`
- `./tests/` — new tests in the fitting modules (test_utils/test_output/test_cli)
- `./memory-bank/deltas.md` — delta entry documenting the qualification rules and the merge-rule decision
</output>

<success_criteria>
- A provider API blip with a <24h-old good cache entry renders stale data with a visible age marker instead of ❌, in all three output modes.
- Config-type failures (no key, expired, invalid key) render exactly as today.
</success_criteria>