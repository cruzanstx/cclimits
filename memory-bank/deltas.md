# Recent Deltas (Last 3-5 Changes)

## 2026-07-12: Stale-Cache Fallback for Transient API Errors

- When a live fetch fails with a transient error (connection error, HTTP 5xx, generic "API error" / "Could not fetch usage") but the cache holds a previous good entry for that provider, the stale entry is served with a visible age marker instead of ❌
- **Rationale**: extends the v1.2.15 cache-merge principle ("a run that CAN'T check a provider shouldn't destroy known-good data") to display time — a 30-minute-old quota reading is more useful in a statusline than an error icon from a momentary API blip
- **Qualification rules** (which failures trigger fallback):
  - Transient (served stale): connection errors (`http_get` status 0 → "API error (0)"/"HTTP 0"), HTTP 5xx, "API error", "Could not fetch usage", generic exceptions
  - NOT transient (error shown as-is): `No credentials found` (🔑 config issue), `Token expired`/`token_status: "expired"` (⏰ actionable), `Invalid API key`/`Forbidden`/`Authentication failed` (user must act), any error string containing "401" or "403"
- **Good cached entry**: `status` of `ok` or `authenticated` (same notion as `merge_cache_data` implies)
- **Staleness cap**: `STALE_CACHE_MAX_AGE = 24 * 60 * 60` (24h) — entries older than this are not served; the error is shown instead
- **Labeling**: substituted entries annotated with `stale_age_seconds` (int) and `stale_fallback = True` (bool); oneline renders `(stale 32m)` suffix (yellow in `--noemoji` color mode); detailed output prints `💤 Stale fallback (last good: 32m ago)`; JSON output carries both annotation fields for scripted consumers
- **Merge-rule extension**: `merge_cache_data` now also preserves prior good entries when the new run hits a transient error (not just `NO_CREDS_ERROR`). Decision: transient errors are akin to "can't check" — the API was temporarily unreachable — so the same preservation principle applies. This keeps the cache the best known data across multiple consecutive blips; without it, the first blip would poison the cache and subsequent stale fallbacks would have nothing to serve
- **Where it hooks in**: after live fetches complete in `main()`, before output. Reads the stale cache BEFORE `write_cache` (to preserve original age for the marker), writes the cache (extended merge preserves good entries), then applies `apply_stale_fallback(results, cached_data, cached_age)` to replace transient errors with annotated stale entries
- **`read_cache` extension**: added optional `max_age` parameter — when provided, TTL is ignored and entries up to `max_age` seconds old are returned (for stale fallback reads); when `None` (default), behaves exactly as before
- **Both modes covered**: plain runs (no `--cached`) and `--cached` runs whose TTL missed — a TTL miss followed by a failed fetch is the exact statusline scenario that motivated v1.2.15
- **Opt-out**: `--no-stale-fallback` flag disables the feature; default is ON
- **New functions**: `_is_transient_error(data)`, `_is_good_cache_entry(data)`, `apply_stale_fallback(results, cached_data, cached_age, max_age)`
- **Tests**: 205 total (42 new) — `_is_transient_error` classification (13 cases), `apply_stale_fallback` substitution (9 cases), `read_cache` max_age (3 cases), merge transient preservation (2 cases), oneline stale marker (4 cases), detailed stale line (2 cases), CLI integration (9 cases: transient→stale, JSON annotation, no-creds/expired/401 not replaced, >24h cap, `--no-stale-fallback`, `--cached` TTL miss, detailed output)
- **Files**: `lib/cclimits.py`, `tests/test_utils.py`, `tests/test_output.py`, `tests/test_cli.py`, `memory-bank/deltas.md`

## 2026-07-12: Provider Registry Refactor

- Refactored per-provider duplication in `lib/cclimits.py` into a data-driven `PROVIDERS` registry (~93 lines saved, 2004 → 1911)
- **What was duplicated**: `print_oneline()` had 8 near-identical ~25-line provider blocks; `main()` had 8 hand-written argparse flags, 8 dispatch `if`-lines, 8 `print_section()` calls, and a hardcoded canonical-order tuple; argparse had 8 copy-pasted `--<provider>` flags
- **What the registry drives**: argparse flag creation, `requested` list, fetch dispatch (with gated/ungated credential semantics), canonical-order result collection, detailed `print_section` loop, and `print_oneline` iteration
- **Shared renderers**: `_fmt_both` (dual-window percent), `_fmt_single` (single-window percent with suffix), `_fmt_balance` (balance with threshold ladder) — Z.AI's integer percents / `request_quota` second value / `(5h)` suffix fallback and Synthetic's `weekly_credits.percent_used` handled via per-provider extractor lambdas, not by re-forking the renderer
- **Two renderer factories**: `_make_str_pct_renderer` (Claude/Codex string-based percents) and `_make_balance_renderer` (OpenRouter/Kimi balance with currency symbol)
- **Fail branch unified**: `fail_icon` (🔑 no-creds / ⏰ expired / ❌ error) applied in one place in the `print_oneline` loop, not per-provider
- **Test patching preserved**: fetch/credential functions stored as name strings, resolved via `globals()` at call time so `@patch('cclimits.get_X_usage')` still intercepts
- **Byte-identical output**: all 163 tests pass with zero assertion changes; live output diffs show only timestamp and real-time data differences
- **Extension point**: adding a provider now requires one `PROVIDERS` entry + one fetch function (+ a custom renderer if the shared factories don't fit) — no edits to `main()` or `print_oneline()` internals

**Files:** `lib/cclimits.py`, `memory-bank/systemPatterns.md`, `memory-bank/deltas.md`

## 2026-07-12: GitHub Actions CI + Automated npm Publishing

- Added `.github/workflows/ci.yml`: runs the 163-test pytest suite on push to main and pull requests across a Python 3.9/3.11/3.13 matrix with two HTTP-backend flavors — one with `requests` installed (full suite), one without (urllib fallback; `-k "not WithRequests"` skips the 9 tests that mock the requests library). Also runs a `node bin/cclimits.js --help` wrapper smoke test.
- Added `.github/workflows/publish.yml`: triggered by `v*` tags — runs the test suite, verifies the tag version matches `package.json`, then publishes to npm with `--provenance --access public` using the `NPM_TOKEN` secret. Requires `id-token: write` permission for provenance.
- Added `requirements-dev.txt` (pytest, requests) for dev dependency tracking.
- Added CI status badge to `README.md`.
- Updated `CLAUDE.md` Publishing Workflow section to document both automated (tag-push) and manual paths.

**Files:** `.github/workflows/ci.yml`, `.github/workflows/publish.yml`, `requirements-dev.txt`, `README.md`, `CLAUDE.md`, `memory-bank/deltas.md`, `memory-bank/activeContext.md`

## 2026-07-12: Parallel Provider Fetching via ThreadPoolExecutor

- `main()` now builds a list of (provider_name, fetch_callable) pairs using the same dispatch logic, then submits them to a `concurrent.futures.ThreadPoolExecutor` (max_workers = number of selected providers) so a full run takes ~max(provider_latencies) instead of sum(provider_latencies)
- Credential discovery for the four gated providers (openrouter, kimi, antigravity, synthetic) still runs before submission in the main thread, preserving the check_all-conditional-fetch semantics and the module-level patch pattern used by tests
- Results are collected in canonical provider order (claude, codex, gemini, zai, openrouter, kimi, antigravity, synthetic) by iterating `future.result()` in that order — deterministic `--json` key order and `--oneline` output preserved
- A provider whose worker raises an unexpected exception is captured as `{"error": "..."}` for that provider only; one bad provider can no longer blank out the statusline
- Zero new dependencies: `ThreadPoolExecutor` is stdlib (Python 3.2+, well within the 3.9+ floor)
- New tests in `TestParallelFetch`: canonical ordering with all 8 providers, exception isolation (one provider raises, others succeed), concurrency timing (two providers each sleeping 0.3s finish < 0.55s)
- Tests: 163 passing (3 new; all 160 existing pass unchanged)

**Files:** `lib/cclimits.py`, `tests/test_cli.py`, `memory-bank/deltas.md`

## 2026-07-12: Cache-Bypass Fix for Last Four Providers

- `main()` dispatch lines for openrouter, kimi, antigravity, and synthetic were missing the `not skip_fetch` guard that the first four providers already had; on a `--cached` cache hit these four still ran credential discovery + live HTTP fetches and overwrote cached entries, defeating the cache (Antigravity alone can make 2+ round-trips + a token refresh)
- Added `not skip_fetch and` to all four dispatch lines, matching the existing pattern for claude/codex/gemini/zai
- Regression tests added in `TestCachedBypassFix`: cache hit asserts zero calls to all 8 usage functions and 4 credential-discovery functions; cache miss verifies explicit-flag-forces-fetch and check_all-conditional-fetch semantics; `--openrouter --cached` missing-from-cache refetch path verified
- Tests: 155 passing (5 new)

**Files:** `lib/cclimits.py`, `tests/test_cli.py`, `memory-bank/deltas.md`

## 2026-07-02: Expired Tokens Visible in Oneline

- Expired OAuth tokens no longer silently vanish from `--oneline`: entries with `token_status: "expired"` (Gemini/Codex 401 paths return these with no `error` key) or `error: "Token expired"` (Claude) now render as ⏰ (`expired` in yellow with `--noemoji`)
- All 8 provider blocks broadened to catch `token_status == "expired"`; `fail_icon()` picks 🔑 / ⏰ / ❌
- Found via cache inspection: gemini entry was `{token_status: expired, hint_refresh: ...}` — neither ok nor error, so oneline dropped it entirely
- README: added status-icon legend and updated `both` examples (Z.AI `tokens%/requests%`)
- Tests: 155 passing (4 new; 2 stale assertions updated: `error: "Token expired"` now ⏰ not ❌)

**Files:** `lib/cclimits.py`, `tests/test_output.py`, `README.md`, `memory-bank/deltas.md`

## 2026-07-02: Atomic Cache Writes + Z.AI Dual Value in Both Mode

- `write_cache()` writes to a `.json.tmp` sibling then `os.replace()` — concurrent runs (cron/statusline vs interactive) can no longer observe a half-written cache
- `--oneline both` now shows Z.AI as `tokens%/requests%` (e.g. `Z.AI: 1%/0%`), matching the dual-value style of Claude/Codex/Synthetic; falls back to `N% (5h)` when request quota is absent; `5h`/`7d` windows unchanged
- Tests: 151 passing (4 new)

**Files:** `lib/cclimits.py`, `tests/test_output.py`, `tests/test_utils.py`, `memory-bank/deltas.md`

## 2026-07-02: Cache Filter/Staleness + Z.AI Data Fixes

- Provider filters now honored on cache hits: `--zai --cached` used to print every cached provider; now subsets to the requested ones, and refetches if any requested provider is missing from cache
- Cached output is labeled with its age: oneline gets a `(cached 42s)` suffix, detailed header gets `(cached 42s ago)` — via `read_cache()` now returning `(data, age_seconds)` and new `format_cache_age()`
- Z.AI `token_quota` no longer emits fake `limit/used/remaining: 0` — the `/quota/limit` TOKENS_LIMIT entry only carries `percentage` + `nextResetTime` (verified against raw API); counts included only when the API provides them. Also captures plan `level` (e.g. "max") into `plan`, rendered by the generic 📊 Plan line
- Z.AI total fetch failure (both endpoints + auth fallback down) now returns `error: "Could not fetch usage"` instead of a dict with neither status nor error (which oneline silently dropped)
- Tests: 147 passing (11 new across test_cli/test_usage/test_utils/test_output)

**Files:** `lib/cclimits.py`, `tests/test_cli.py`, `tests/test_usage.py`, `tests/test_utils.py`, `tests/test_output.py`, `memory-bank/deltas.md`

## 2026-07-02: Cache Merge + Missing-Credentials Icon

- `write_cache()` now merges into the existing cache via new `merge_cache_data()`: a provider entry with `error: "No credentials found"` no longer overwrites a previous good entry, and partial runs (e.g. `--zai`) no longer clobber other providers' cached data
- Rationale: cache is shared across environments (cron/statusline vs interactive shell); a run missing `ZAI_API_KEY` was poisoning the cache, making `--oneline --cached` show `Z.AI: ❌` while a direct probe was healthy
- `--oneline` now renders missing credentials as 🔑 (`no key` in yellow with `--noemoji`) instead of ❌, distinguishing config issues from API outages; matched on the exact `NO_CREDS_ERROR = "No credentials found"` string all providers use
- Added tests: `TestMergeCacheData` (test_utils.py), `TestOnelineMissingCredentials` (test_output.py); suite now 136 passing

**Files:** `lib/cclimits.py`, `tests/test_utils.py`, `tests/test_output.py`, `memory-bank/deltas.md`

## 2026-06-27: Synthetic.new Provider

- Added Synthetic.new support via `--synthetic` (env: `SYNTHETIC_API_KEY` / `SYNTHETIC_KEY`)
- Hits `GET https://api.synthetic.new/v2/quotas` (Bearer auth) — `/quotas` requests don't count against the subscription
- Exposes all three primary buckets: `daily_subscription` (period requests), `rolling_5h` (5h token tick), `weekly_credits` (USD credits with regen tick)
- One-line mapping: `5h` → rolling 5h used %, `7d` → weekly credit used %, `both` → `5h%/7d%`
- Added timezone-aware `_format_resets_in()` helper (Python 3.9 fromisoformat-compatible) for ISO-8601 `Z` timestamps
- Updated detailed/oneline/JSON paths plus README, CLAUDE.md endpoints table, and credential discovery section

**Files:** `lib/cclimits.py`, `README.md`, `CLAUDE.md`, `memory-bank/deltas.md`

## 2026-06-26: Python 3.9+ Compatibility (PR #1)

- Merged PR #1 from @Elyter: added `from __future__ import annotations` to defer evaluation of PEP 604 `X | None` unions
- Bumped stated minimum from Python 3.10+ → 3.9+ across README, `bin/cclimits.js` error message, CLAUDE.md, and memory-bank files
- Verified no `match` statements remain in `lib/cclimits.py`, so the `__future__` import is sufficient for 3.9 support
- Released as 1.2.13

**Files:** `lib/cclimits.py`, `README.md`, `bin/cclimits.js`, `CLAUDE.md`, `memory-bank/projectbrief.md`, `memory-bank/techContext.md`

## 2026-06-15: Antigravity Oneline Usage Normalization

- Changed Antigravity compact output to display used percentage (`100 - min_remaining_pct`) instead of remaining percentage, matching Claude/Codex usage-oriented semantics
- Added oneline regression coverage and updated README examples
- Fixed full test-suite isolation for module patching, cache writes, urllib fallback tests, and minimal detailed-output fixtures

**Files:** `lib/cclimits.py`, `tests/conftest.py`, `tests/test_cli.py`, `tests/test_credentials.py`, `tests/test_http.py`, `tests/test_output.py`, `README.md`, `memory-bank/deltas.md`, `memory-bank/progress.md`

## 2026-05-31: Antigravity Live Test + File-Based Credential Discovery

- Verified end-to-end against a real `agy` install — returned 20 models, project ID, free-tier
- Discovered the real credential file: `~/.gemini/antigravity-cli/antigravity-oauth-token` (nested `{"token": {...}}` shape, RFC3339 expiry)
- Replaced keyring-probing with file-based discovery (kept env-var fallback unchanged)
- Fixed `--oneline` status icon: now passes `100 - min_remaining_pct` so 100% remaining renders ✅, not ❌
- Closes #2

**Files:** `lib/cclimits.py`, `README.md`, `CLAUDE.md`, `memory-bank/deltas.md`

## 2026-05-30: Google Antigravity Provider (initial)

- Added Google Antigravity support via `--antigravity` with Cloud Code Assist `:loadCodeAssist` + `:fetchAvailableModels`
- Implemented keyring-first credential discovery with env fallback (`ANTIGRAVITY_REFRESH_TOKEN`, `ANTIGRAVITY_ACCESS_TOKEN`) — superseded by 2026-05-31 entry
- Normalizes per-model quota data into a tightest-first model list plus summary (`model_count`, min/avg remaining percentage)
- Updated detailed, one-line, and JSON output paths plus README and CLAUDE.md provider docs

**Files:** `lib/cclimits.py`, `README.md`, `CLAUDE.md`, `memory-bank/deltas.md`, `memory-bank/progress.md`

## 2026-02-07: Kimi K2 (Moonshot AI) Integration

- Added support for Kimi K2 (Moonshot AI) via `--kimi` flag
- Implemented `get_kimi_credentials` and `get_kimi_usage`
- Balance-based tracking (like OpenRouter) with USD/CNY currency support
- Updated documentation (README, CLAUDE.md)
- Integrated into all output modes (detailed, oneline, JSON)

**Files:** `lib/cclimits.py`, `README.md`, `CLAUDE.md`

## 2026-01-11: Provider Research + Implementation Prompts

- Completed research on 8+ AI coding providers (`research/ai-coding-providers.md`)
- Created 5 implementation prompts in `prompts/providers/`:
  - 011: GitHub Copilot (high feasibility - `gh` CLI)
  - 012: Cursor (medium - internal API discovery needed)
  - 013: Replit (high - GraphQL credits API)
  - 014: Windsurf/Codeium (medium - config discovery)
  - 015: Amazon Q (medium - AWS CLI research needed)
- Top candidates: Replit (clearest API), GitHub Copilot (largest user base)
- BYOK tools (Aider, Continue) already covered via existing provider keys

**Files:** `research/ai-coding-providers.md`, `prompts/providers/011-015*.md`

## 2026-01-11: Z.AI 5h + Gemini Token Persistence (v1.2.5-1.2.8)

- Added `(5h)` indicator to Z.AI quota in oneline output
- Updated verbose section header to "Z.AI (5h shared - GLM-4.x)"
- Z.AI quota is shared across GLM-4.7, GLM-4.6, GLM-4.5V, GLM-4.5, GLM-4.5-Air, and Visual Analysis
- Fixed Gemini OAuth token persistence with atomic writes (temp file + rename)
- Added `.npmignore` and fixed `package.json` to exclude `__pycache__` (package size: 64KB → 15KB)
- Updated README examples to reflect Z.AI 5h window

**Files:** `lib/cclimits.py`, `CLAUDE.md`, `README.md`, `package.json`, `.npmignore`

## 2026-01-10: Oneline Both Mode + Noemoji Flag (v1.2.3-1.2.4)

- Added `--oneline both` to show 5h/7d windows simultaneously
- Added `--noemoji` flag for color-coded percentages instead of emoji icons
- Useful for terminals without emoji support

**Files:** `lib/cclimits.py`

## 2026-01-01: Gemini Tiers Refactoring

- Grouped Gemini models by quota tier (3-Flash, Flash, Pro)
- Reduced display from 6 models to 3 tiers
- Each tier shows usage from first available model in quota bucket
- Status icons continue to work correctly across all tiers

**Files:** `lib/cclimits.py`

## 2026-01-01: Initial npm Release (v1.0.0)

- Published to npm as `cclimits`
- Added Node.js wrapper for npx support
- Moved Python script to `lib/cclimits.py`
- Created memory-bank documentation

**Files:** `package.json`, `bin/cclimits.js`, `lib/cclimits.py`

## 2026-01-01: Repository Created

- Extracted from daplug plugin (`rogers_ai_rules/plugins/daplug/skills/ai-usage`)
- Refactored Gemini OAuth to extract credentials from CLI installation
- Added comprehensive README with usage examples
- MIT license

**Files:** `lib/cclimits.py`, `README.md`, `LICENSE`
