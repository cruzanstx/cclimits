# Recent Deltas (Last 3-5 Changes)

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
