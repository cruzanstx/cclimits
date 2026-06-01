<objective>
Add Google Antigravity CLI as a tracked provider in cclimits. Antigravity is Google's
Go-based replacement for Gemini CLI (Gemini CLI was retired 2026-06-18). It uses the
same Google OAuth flow but stores credentials in the system keyring (NOT a file like
`~/.gemini/oauth_creds.json`), and exposes a per-model quota endpoint via the Cloud
Code Assist API. Tracks GitHub issue cruzanstx/cclimits#2.
</objective>

<context>
This is the cclimits project — a CLI tool that checks quota/usage for AI coding assistants.
It is distributed via npm and runs Python under the hood.

Read these files first to understand the codebase patterns:
- `./CLAUDE.md` — Project conventions and structure
- `./lib/cclimits.py` — Main script (all code lives here)
- `./memory-bank/deltas.md` — Recent changes
- `./memory-bank/systemPatterns.md` — Architecture patterns

**Existing provider closest to Antigravity** — Gemini (`lib/cclimits.py:454-795`).
Antigravity uses the *same Google OAuth client* and the same `cloudcode-pa.googleapis.com`
host, but a different endpoint (`fetchAvailableModels`) that returns per-model quotas
rather than the per-day "1k generate-content / 100 code-completion" rollup that
`countTokens` returns for Gemini CLI.

**Antigravity OAuth + API reference** (verified against
github.com/firdyfirdy/antigravity-auth and github.com/duongductrong/antigravity-kit,
both of which extracted the client from the official Antigravity binary):

```
Client ID:     1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com
Client Secret: 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
Token URL:     https://oauth2.googleapis.com/token
Scopes:        cloud-platform, userinfo.email, userinfo.profile, cclog, experimentsandconfigs
```

**Quota check is a 2-step call:**

1. Resolve project ID:
   ```
   POST https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist
   Authorization: Bearer <access_token>
   Content-Type: application/json
   User-Agent: antigravity/windows/amd64
   Body: {"metadata": {"ideType": "ANTIGRAVITY"}}
   → {"cloudaicompanionProject": "<projectId>",
      "currentTier": {"id": "..."}, "paidTier": {"id": "..."}}
   ```

2. Fetch per-model quota:
   ```
   POST https://cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels
   Authorization: Bearer <access_token>
   Content-Type: application/json
   User-Agent: antigravity/1.11.5 windows/amd64
   Body: {"project": "<projectId>"}
   → {"models": {
        "gemini-3-pro":               {"quotaInfo": {"remainingFraction": 0.92, "resetTime": "..."}},
        "gemini-3-flash":             {"quotaInfo": {"remainingFraction": 0.88, "resetTime": "..."}},
        "claude-opus-4-5-thinking":   {"quotaInfo": {"remainingFraction": 0.65, "resetTime": "..."}},
        "claude-sonnet-4-6":          {"quotaInfo": {"remainingFraction": 0.71, "resetTime": "..."}},
        ...
      }}
   ```

Endpoint fallback order (try in sequence if one fails):
`https://cloudcode-pa.googleapis.com` (prod, prefer this), then
`https://daily-cloudcode-pa.sandbox.googleapis.com`, then
`https://autopush-cloudcode-pa.sandbox.googleapis.com`.

`remainingFraction` is a float 0.0–1.0; convert to percentage.

**Credential storage — this is the hard part:**

Unlike Gemini CLI which writes `~/.gemini/oauth_creds.json`, the official Antigravity
CLI stores its refresh token in the **OS keyring**:
- macOS: Keychain (`security find-generic-password`)
- Linux: libsecret / GNOME Keyring / KWallet (`secret-tool lookup`)
- Windows: Credential Manager

The exact keyring service name used by the official Antigravity CLI is **not yet
confirmed** — verify by inspecting a real install (try `security dump-keychain |
grep -i antigravity` on macOS, or `secret-tool search --all type service` on Linux).
Likely candidates: `Antigravity`, `antigravity`, `Google Antigravity`,
`google-antigravity`, or `antigravity-cli`.

If a refresh token cannot be located in the keyring, fall back to environment
variables (`ANTIGRAVITY_REFRESH_TOKEN`, `ANTIGRAVITY_ACCESS_TOKEN`) so power users
can wire it manually. If neither is available, the provider should return
`{"error": "...", "hint": "..."}` like other unconfigured providers — it must NOT
crash and must NOT appear in `--oneline` / `check_all` output when unconfigured
(matches the behavior of commit 16a4148 "hide env-var providers from check_all when
unconfigured").
</context>

<requirements>
1. **Constants** — define at module scope near the other provider constants:
   - `ANTIGRAVITY_CLIENT_ID`, `ANTIGRAVITY_CLIENT_SECRET`
   - `ANTIGRAVITY_ENDPOINTS` (list, prod first)
   - `ANTIGRAVITY_KEYRING_SERVICE_CANDIDATES` (list of strings to probe)

2. **Credential discovery** — `get_antigravity_credentials() -> dict | None`
   - Try each keyring service name in `ANTIGRAVITY_KEYRING_SERVICE_CANDIDATES`:
     - macOS: `security find-generic-password -s <service> -w` (subprocess, capture stdout)
     - Linux: `secret-tool lookup service <service>` (subprocess)
     - Windows: best-effort via `keyring` module if available, otherwise skip
   - Fall back to env vars `ANTIGRAVITY_REFRESH_TOKEN` and `ANTIGRAVITY_ACCESS_TOKEN`
   - Return shape: `{"refresh_token": "...", "access_token": "...", "source": "keyring|env"}`
     or `None` if nothing found
   - Auto-refresh: if only refresh_token is present, call the OAuth token endpoint
     and populate access_token (same pattern as `refresh_gemini_token` at line 546)
   - Must NOT raise — wrap subprocess calls and return None on failure

3. **Usage fetcher** — `get_antigravity_usage() -> dict`
   - If no creds: return `{"error": "...", "hint": "Run 'antigravity auth login' or set ANTIGRAVITY_REFRESH_TOKEN"}`
   - Step 1: POST `:loadCodeAssist` to resolve project ID. If the call returns 401,
     try refreshing the token once and retry. On repeated 401, return error.
   - Step 2: POST `:fetchAvailableModels` with the project ID. Try each endpoint in
     `ANTIGRAVITY_ENDPOINTS` until one returns 2xx.
   - Parse the response and return:
     ```python
     {
         "status": "ok",
         "project_id": "<id>",
         "subscription_tier": "<tier-id or 'free'>",
         "models": [
             {"name": "gemini-3-pro", "remaining_pct": 92, "reset_time": "..."},
             ...
         ],
         "summary": {
             "model_count": N,
             "min_remaining_pct": <int>,    # tightest quota across all models
             "avg_remaining_pct": <int>,
         },
         "dashboard_url": "https://antigravity.google"
     }
     ```
   - Use the existing `http_post()` helper at line 167 — do NOT use requests directly
   - Set the `User-Agent` and other headers per the spec above

4. **CLI integration** — wire into `main()`:
   - Add `--antigravity` flag to argparse (after `--kimi`)
   - Update `check_all` calculation at line 1402 to include `args.antigravity`
   - Gate the check on credentials being present (same env-var-aware pattern as
     OpenRouter line 1416 and Kimi line 1418):
     ```python
     if args.antigravity or (check_all and get_antigravity_credentials()):
         results["antigravity"] = get_antigravity_usage()
     ```
   - Add to verbose output via `print_section()` near line 1444
   - Add to oneline output via a new branch in `print_oneline()`

5. **`print_section` handling** — Antigravity returns a *list* of models, not a flat
   `tokens_used/limit`. The existing `print_section` dispatches on known keys; you'll
   need to either:
   - Add a dedicated branch that detects `data.get("models") and data.get("summary")`
     and prints a compact table (model name, remaining %, reset time), OR
   - Extend the generic renderer to handle a `models` list
   Choose whichever requires fewer changes and keeps the output readable. Cap the
   table at ~10 rows and add a "N more models hidden" line if truncated, sorted by
   `remaining_pct` ascending (tightest first — that's what the user cares about).

6. **`print_oneline` handling** — one line, one summary number:
   - Format: `Antigravity: <min_pct>% (N models) <icon>`
   - Use the existing `get_status_icon(pct)` and `colorize_pct()` helpers
   - `min_pct` (tightest model) drives the icon, not avg

7. **JSON output** — should work automatically since `results["antigravity"]` is
   already a dict. Just verify the structure round-trips through `json.dumps`.

8. **CLAUDE.md updates**:
   - Add Antigravity rows to the API Endpoints table (both `:loadCodeAssist` and
     `:fetchAvailableModels`)
   - Note keyring storage in Known Limitations (not a file path)
   - Update the "Gemini OAuth" limitation note — Gemini CLI was retired 2026-06-18,
     so the OAuth-must-have-gemini-CLI bit needs a "(legacy)" qualifier

9. **README.md updates**:
   - Add Antigravity to supported tools list
   - Add `--antigravity` to CLI flags
   - Add setup note: "requires Antigravity CLI installed and authenticated; refresh
     token discovered automatically from system keyring"
   - Update example outputs to include Antigravity row

10. **memory-bank/deltas.md and progress.md** — add a top entry summarizing the new
    provider, the keyring discovery, and the per-model quota shape.
</requirements>

<implementation>
- Place `get_antigravity_credentials()`, `refresh_antigravity_token()`, and
  `get_antigravity_usage()` directly after the Kimi functions (~line 950) so
  related providers stay grouped.
- The token refresh is identical to `refresh_gemini_token` — feel free to extract a
  shared `_refresh_google_oauth(client_id, client_secret, refresh_token)` helper if
  it reads cleaner, but don't refactor existing Gemini code beyond that.
- Keychain access on macOS: use `subprocess.run(["security", "find-generic-password",
  "-s", svc, "-w"], ...)`. The `-w` flag prints the password to stdout. Capture and
  strip newlines.
- libsecret on Linux: `subprocess.run(["secret-tool", "lookup", "service", svc],
  ...)`. May not be installed on minimal systems — handle FileNotFoundError.
- Keep the zero-dependency pattern (urllib fallback) — `http_post()` already does this.
- Do NOT hardcode any refresh tokens or access tokens. The OAuth client_id/secret
  ARE the official Google-issued public credentials for the Antigravity desktop app;
  hardcoding them is intentional and required, same as the Gemini CLI client_id
  already in the codebase.

**Verify the keyring service name on a real install if possible:**
The Antigravity CLI may not be installed in the test environment. If it isn't:
- Implement the candidate-list probing pattern as specified
- Document in a code comment which service names were probed
- The end user can override via `ANTIGRAVITY_REFRESH_TOKEN` env var as escape hatch

**Testing approach:**
- `python3 lib/cclimits.py --antigravity` — single provider check
- `python3 lib/cclimits.py --oneline` — Antigravity row appears (when configured) or
  is hidden (when unconfigured, matching the 16a4148 pattern)
- `python3 lib/cclimits.py --json` — valid JSON, antigravity key present
- `python3 lib/cclimits.py` — verbose output shows model table
- Test the unconfigured path: temporarily move/clear ANTIGRAVITY_* env vars and
  confirm cclimits doesn't crash and doesn't spam errors
</implementation>

<verification>
Before declaring complete, verify:
- [ ] `ANTIGRAVITY_CLIENT_ID`, `ANTIGRAVITY_CLIENT_SECRET`, `ANTIGRAVITY_ENDPOINTS`,
      `ANTIGRAVITY_KEYRING_SERVICE_CANDIDATES` constants defined
- [ ] `get_antigravity_credentials()` probes keyring (macOS/Linux/Windows best-effort)
      then falls back to env vars
- [ ] `refresh_antigravity_token()` (or shared helper) refreshes via Google OAuth
- [ ] `get_antigravity_usage()` does `:loadCodeAssist` then `:fetchAvailableModels`,
      retries with refreshed token on 401, falls back across `ANTIGRAVITY_ENDPOINTS`
- [ ] Response normalized to `{status, project_id, subscription_tier, models[],
      summary{min,avg,count}, dashboard_url}`
- [ ] `--antigravity` flag added to argparse
- [ ] Wired into `check_all` with credential gate (hidden when unconfigured)
- [ ] `print_section` handles the model-list shape (sorted ascending by remaining_pct,
      capped at ~10 rows)
- [ ] `print_oneline` shows `Antigravity: <min_pct>% (N models) <icon>`
- [ ] JSON output round-trips cleanly
- [ ] CLAUDE.md updated (endpoints table + Gemini-retired note)
- [ ] README.md updated (supported tools, --antigravity flag, setup note)
- [ ] memory-bank/deltas.md and progress.md updated
- [ ] No hardcoded user-specific tokens
- [ ] Uses http_get/http_post helpers, not raw requests
- [ ] Unconfigured run does not crash or spam errors
- [ ] `python3 lib/cclimits.py --json` succeeds
- [ ] `python3 lib/cclimits.py --oneline` succeeds
- [ ] `python3 lib/cclimits.py --antigravity` shows either a quota table or a
      clean error+hint

Output: <verification>VERIFICATION_COMPLETE</verification>
</verification>
