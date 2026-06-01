<objective>
Add Kimi K2 (Moonshot AI) as a tracked provider in cclimits. Kimi K2 is a prepaid credit-based
AI inference API (like OpenRouter) with an OpenAI-compatible balance endpoint. This should follow
the same patterns as existing providers (credential discovery, HTTP request, structured output).
</objective>

<context>
This is the cclimits project — a CLI tool that checks quota/usage for AI coding assistants.
It is distributed via npm and runs Python under the hood.

Read these files to understand the codebase patterns:
- `./CLAUDE.md` — Project conventions and structure
- `./lib/cclimits.py` — Main script (all code lives here)
- `./memory-bank/deltas.md` — Recent changes
- `./memory-bank/systemPatterns.md` — Architecture patterns

**Kimi K2 API Reference** (already documented in our llms_txt repo):
- Balance endpoint: `GET https://api.moonshot.ai/v1/users/me/balance`
- Auth header: `Authorization: Bearer {api_key}`
- This is a prepaid credit system (balance in CNY/USD), NOT a subscription quota
- Rate limits are tiered by cumulative recharge amount (Tier0-Tier5)
- API keys are generated at https://platform.moonshot.ai/console

**Existing provider patterns to follow:**
- OpenRouter (closest match — also a prepaid balance system): lines 98-138
- Z.AI (env var credential discovery): lines 797-897
- The `http_get()` helper at line 141 handles both requests and urllib fallback
</context>

<requirements>
1. **Credential Discovery** — `get_kimi_credentials() -> str | None`
   - Check env vars in order: `MOONSHOT_API_KEY`, `KIMI_API_KEY`, `KIMI_KEY`
   - Return the first found key, or None

2. **Usage Fetcher** — `get_kimi_usage() -> dict`
   - Call `GET https://api.moonshot.ai/v1/users/me/balance` with Bearer token auth
   - Parse the response to extract balance information
   - Return structured dict matching existing provider patterns:
     ```python
     {
         "status": "ok",
         "balance": <float>,          # Available balance
         "currency": "CNY" or "USD",  # If detectable
         "dashboard_url": "https://platform.moonshot.ai/console"
     }
     ```
   - Handle errors: 401 (invalid key), other HTTP errors
   - If no credentials found, return error dict with hint about env var setup

3. **CLI Integration** — Wire into main():
   - Add `--kimi` flag to argparse (same pattern as --zai, --openrouter)
   - Add to `check_all` logic
   - Add to results processing (JSON, oneline, verbose)
   - Update epilog help text with Kimi credential location

4. **Oneline Output** — Add Kimi section to `print_oneline()`:
   - Follow OpenRouter pattern (balance-based, not percentage-based)
   - Format: `Kimi: $X.XX ✅` (or CNY equivalent)
   - Use same status thresholds as OpenRouter: >$5 ✅, $1-5 ⚠️, <$1 🔴, $0 ❌

5. **Verbose Output** — Add Kimi section to verbose print:
   - Section name: "Kimi K2 (Moonshot AI)"
   - Show balance, auth status, dashboard link

6. **CLAUDE.md Updates**:
   - Add Kimi to the API Endpoints table
   - Add Kimi credential location to the epilog section
   - Update description to include Kimi

7. **README.md Updates**:
   - Add Kimi K2 to supported tools list
   - Add `--kimi` to CLI flags documentation
   - Add Kimi setup instructions (env var)
   - Update example outputs to include Kimi
</requirements>

<implementation>
- Place `get_kimi_credentials()` and `get_kimi_usage()` near the OpenRouter functions
  (they follow the same prepaid balance pattern)
- The balance API response format needs to be discovered — fetch the endpoint and
  inspect the actual JSON structure, then parse accordingly
- Use `http_get()` helper (line 141) for the API call — do NOT use requests directly
- Keep zero-dependency pattern (urllib fallback)
- Do NOT hardcode any API keys

**Important: Research the actual balance API response format.** The llms_txt docs show
the endpoint exists but not the response schema. You may need to:
1. Check https://platform.moonshot.ai/docs/api/balance for response format
2. Or test with a real API call if credentials are available (check env vars)
3. Or search for documentation about the response structure

**Testing approach:**
- If MOONSHOT_API_KEY is set in env, test with real API call
- If not, verify the code structure matches existing patterns
- Run: `python3 lib/cclimits.py --kimi` to test single provider
- Run: `python3 lib/cclimits.py --oneline` to test oneline integration
- Run: `python3 lib/cclimits.py --json` to test JSON output
</implementation>

<verification>
Before declaring complete, verify:
- [ ] `get_kimi_credentials()` function exists and checks env vars
- [ ] `get_kimi_usage()` function exists and calls the balance API
- [ ] `--kimi` flag added to argparse
- [ ] Kimi added to `check_all` logic in main()
- [ ] Kimi section in `print_oneline()` (balance-based like OpenRouter)
- [ ] Kimi section in verbose output via `print_section()`
- [ ] Kimi added to JSON output
- [ ] CLAUDE.md updated with Kimi endpoint info
- [ ] README.md updated with Kimi support
- [ ] Epilog help text updated
- [ ] Run `python3 lib/cclimits.py --json` — no crashes, Kimi section present
- [ ] Run `python3 lib/cclimits.py --oneline` — Kimi appears in output
- [ ] Run `python3 lib/cclimits.py` — verbose output includes Kimi section
- [ ] No hardcoded API keys or credentials
- [ ] Uses http_get() helper, not raw requests

Output: <verification>VERIFICATION_COMPLETE</verification>
</verification>