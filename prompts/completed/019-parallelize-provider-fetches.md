<objective>
Parallelize provider fetching in `lib/cclimits.py` so a full `cclimits` run takes roughly as long as the slowest single provider instead of the sum of all eight.

Today `main()` calls the eight `get_*_usage()` functions sequentially. Each provider makes 1–3 HTTP calls with a 10s timeout (Antigravity can also iterate three endpoints and do an OAuth refresh), so a run with a slow/unreachable provider can block everything behind it. Users run this in statuslines and shells where latency is directly felt.
</objective>

<context>
Project: cclimits — CLI that checks quota/usage for AI coding assistants. Read `CLAUDE.md` and `memory-bank/` for conventions.

Key facts:
- The provider fetch functions (`get_claude_usage`, `get_codex_usage`, `get_gemini_usage`, `get_zai_usage`, `get_openrouter_usage`, `get_kimi_usage`, `get_antigravity_usage`, `get_synthetic_usage`) are independent of each other — no shared mutable state except the module-level `requests`/urllib clients, which are thread-safe for this usage.
- The tool must stay zero-dependency: use `concurrent.futures.ThreadPoolExecutor` from the stdlib (available in Python 3.9+, the stated minimum — see `from __future__ import annotations` note in CLAUDE.md/PR #1).
- One subtlety: `get_gemini_credentials()` can refresh and atomically rewrite `~/.gemini/oauth_creds.json`, and `get_antigravity_credentials()` can refresh tokens — these touch different files, so they can run concurrently, but do not parallelize WITHIN a provider.
- Output ordering must stay deterministic (claude, codex, gemini, zai, openrouter, kimi, antigravity, synthetic) regardless of completion order — both the detailed sections and the `--oneline` string are order-sensitive and covered by tests.
- The check_all path currently gates openrouter/kimi/antigravity/synthetic on a credential-discovery call before fetching; keep that behavior (run the discovery inside the worker or before submission, but the provider must not appear in results when check_all is set and no credentials exist).
</context>

<requirements>
1. Build the list of (provider_name, fetch_callable) pairs exactly as the current dispatch logic decides them, then execute the fetches through a `ThreadPoolExecutor` (max_workers = number of providers is fine).
2. Assemble `results` in the canonical provider order, not completion order.
3. A provider whose worker raises an unexpected exception must not crash the whole run — capture it as `{"error": "..."}` for that provider so one bad provider can't blank out the statusline.
4. Behavior must be byte-identical for all output modes (`--json`, `--oneline`, detailed) given the same provider responses. No new flags, no new dependencies.
5. Keep the cache read/write flow unchanged (including any cache-hit skip logic present when you start this task).
</requirements>

<verification>
**Unit Tests** (required):

```bash
cd /storage/projects/docker/cclimits && python3 -m pytest tests/ -v
```

- [ ] All existing tests pass unchanged (they patch `get_*_usage` at module level — verify the new dispatch still calls those patched names so the patching pattern keeps working; this is a hard constraint).
- [ ] New test: all selected providers are fetched and results appear in canonical order.
- [ ] New test: a provider function that raises produces an `error` entry for that provider while others succeed.
- [ ] New test (timing-based, keep tolerant): with two fake providers each sleeping 0.3s, total wall time is well under 0.6s — proving concurrency.

Manual smoke check:
```bash
time python3 lib/cclimits.py --oneline
time python3 lib/cclimits.py --json | python3 -m json.tool > /dev/null
```
</verification>

<output>
Modify:
- `./lib/cclimits.py`
- `./tests/` — new tests in the most fitting module
- `./memory-bank/deltas.md` — delta entry per project convention
</output>

<success_criteria>
- Full-run wall time ≈ slowest provider, not the sum.
- All existing + new tests pass; module-level patching in tests still intercepts fetches.
</success_criteria>