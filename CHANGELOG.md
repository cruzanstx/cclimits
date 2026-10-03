# Changelog

All notable changes to cclimits are documented here.

## 1.7.2 — 2026-10-03

### Fixed
- **Antigravity quotas now read from the backend the `agy` CLI actually uses.**
  String analysis of the `agy` 1.2.16 binary and its request logs showed the
  CLI routes all Cloud Code Assist traffic (model calls, quota, auth) to
  `daily-cloudcode-pa.googleapis.com`, while cclimits preferred the prod
  `cloudcode-pa.googleapis.com` endpoint. The two backends keep separate
  bucket state for the Claude/GPT weekly quota, which made cclimits report
  78% weekly used with a ~6h reset while the `agy /usage` panel showed
  ~0% used resetting in 6 days — same account, all 5h buckets agreeing.
  The daily backend is now queried first, with prod and sandbox hosts kept
  as fallbacks. Live output matches the `agy /usage` panel exactly.

## 1.7.1 — 2026-10-03

### Added
- **Antigravity quota output grouped by model family.** Antigravity exposes
  quota groups — Gemini models, and Claude + GPT models (GPT-OSS shares the
  Claude pool) — each with explicit 5-hour and weekly windows via
  `v1internal:retrieveUserQuotaSummary`. Previously these were flattened
  into a single "tightest model" percentage, which could pair one group's
  usage with the other group's reset time.
  - Oneline: `Antigravity Gemini: 12.2%/2.2% ✅ ↻1h42m/4h52m | Antigravity Claude/GPT: 0%/0.3% ✅ ↻4h59m/6d17h`
  - Detailed output: per-group 5-Hour/7-Day used/remaining/reset blocks,
    with per-model quotas retained as supplemental detail.
  - `--json`: new `quota_groups` array with per-group `5h`/`weekly` buckets;
    per-model detail preserved.
  - Legacy single-line rendering is kept as an explicit fallback if the
    grouped endpoint is unavailable.
