<objective>
Fix a cache-bypass bug in `lib/cclimits.py` `main()`: when `--cached` produces a cache hit, the OpenRouter, Kimi, Antigravity, and Synthetic providers are STILL fetched live, defeating the cache entirely for those providers.

This matters because the primary consumer of `--cached` is a statusline/cron context where speed is the whole point — Antigravity alone can make 2+ HTTP round-trips (plus a token refresh), so a "cache hit" today can still take several seconds.
</objective>

<context>
Project: cclimits — CLI that checks quota/usage for AI coding assistants. Read `CLAUDE.md` and `memory-bank/deltas.md` for conventions.

The bug is in `main()` (around lines 1922–1941 of `lib/cclimits.py`). The first four providers are correctly guarded:

```python
if not skip_fetch and (check_all or args.claude):
    results["claude"] = get_claude_usage()
```

…but the last four are NOT guarded with `not skip_fetch`:

```python
if args.openrouter or (check_all and get_openrouter_credentials()):
    results["openrouter"] = get_openrouter_usage()
if args.kimi or (check_all and get_kimi_credentials()):
    results["kimi"] = get_kimi_usage()
if args.antigravity or (check_all and get_antigravity_credentials()):
    results["antigravity"] = get_antigravity_usage()
if args.synthetic or (check_all and get_synthetic_credentials()):
    results["synthetic"] = get_synthetic_usage()
```

So on a cache hit (`skip_fetch == True`), these four still run credential discovery AND live HTTP fetches, then overwrite the cached entries in the in-memory `results`. Additionally, because `write_cache()` is only called `if not skip_fetch`, those fresh results are thrown away rather than written back.
</context>

<requirements>
1. Add the `not skip_fetch` guard to the openrouter/kimi/antigravity/synthetic dispatch lines so a cache hit performs zero network calls and zero credential probing.
2. Preserve existing semantics otherwise: on a cache MISS, `check_all` still only includes these providers when credentials are discoverable, and explicit flags (`--openrouter` etc.) still force a fetch.
3. Verify the provider-filter cache path still works: `--openrouter --cached` with openrouter present in cache must serve from cache; with openrouter absent from cache it must refetch (this logic lives in the `read_cache` handling above the dispatch — do not break it).
</requirements>

<verification>
**Unit Tests** (required — this is regression-protection for a cache-correctness bug):

```bash
cd /storage/projects/docker/cclimits && python3 -m pytest tests/ -v
```

Add tests (likely in `tests/test_cli.py`, following its existing patching patterns / conftest isolation):
- [ ] Cache hit with all providers cached → `get_openrouter_usage` / `get_kimi_usage` / `get_antigravity_usage` / `get_synthetic_usage` are NOT called (patch them and assert call count 0). Same for the credential-discovery functions.
- [ ] Cache miss → dispatch behaves exactly as before (explicit flag forces fetch; check_all fetches only when credentials exist).
- [ ] `--openrouter --cached` with openrouter missing from cache → refetches.
- [ ] Full existing suite passes (155 tests at time of writing).

Manual smoke check:
```bash
python3 lib/cclimits.py --cached --oneline   # run twice; second run should be near-instant
```
</verification>

<output>
Modify:
- `./lib/cclimits.py` — add guards in `main()`
- `./tests/test_cli.py` (or the most fitting existing test module) — new regression tests
- `./memory-bank/deltas.md` — add a delta entry per project convention
</output>

<success_criteria>
- On a cache hit, zero provider fetch functions and zero credential-discovery functions execute.
- All existing tests plus new regression tests pass.
</success_criteria>