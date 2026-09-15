<objective>
Add Amazon Q Developer (formerly CodeWhisperer) quota checking to cclimits.

Amazon Q has clear limits on the free tier (50 chat messages/mo) and uses standard AWS credentials.
</objective>

<context>
Project: cclimits — CLI tool for checking AI coding assistant quotas
File: `lib/cclimits.py`

**Architecture note (2026-09 refresh):** providers are now data-driven via the module-level
`PROVIDERS` registry in `lib/cclimits.py` (see registry around line 2563). Adding a provider =
(1) `get_<name>_credentials()` + `get_<name>_usage()` functions, (2) ONE registry entry with
`key`, `title`, `fetch`, `gated`, `creds`, `oneline_order`, `render_oneline`. Argparse flags,
fetch dispatch, and oneline/verbose/JSON output are all derived from the registry — do NOT
hand-wire flags or print blocks. GitHub Copilot (`get_copilot_usage` / `_render_copilot`) is the
freshest pattern reference. Also read `./CLAUDE.md` and `./memory-bank/systemPatterns.md` first.

Research findings (from `research/ai-coding-providers.md`):
- Plans: Free (50 chat messages/mo), Pro ($19/mo - unlimited chat)
- Pro includes 4000 lines of code transformation
- AWS credentials are standard (`~/.aws/credentials`)
- May be accessible via AWS CLI command
- Potential: `aws q-developer get-usage` or similar
</context>

<research_required>
Before implementing, investigate:
1. Check AWS CLI for any `q` or `codewhisperer` subcommands
2. Run `aws help | grep -i code` or `aws help | grep -i q`
3. Check Amazon Q IDE extension for network API calls
4. Look for usage endpoints in AWS console network traffic
5. Check if usage is exposed via standard AWS service APIs
</research_required>

<requirements>
1. Add `get_amazonq_credentials()` function (AWS creds)
2. Add `get_amazonq_usage()` function to fetch usage stats
3. Add ONE `PROVIDERS` registry entry for amazonq (`gated: True`, percent renderer) — the `--amazonq` flag, dispatch, and oneline/verbose/JSON output derive from it automatically
4. Display chat messages used (free tier)
5. Show code transformation lines (pro tier)
</requirements>

<implementation>
Pattern to follow:
```python
def get_amazonq_credentials() -> dict | None:
    """Get Amazon Q credentials via AWS config"""
    # Check ~/.aws/credentials
    # Check AWS_PROFILE, AWS_ACCESS_KEY_ID env vars
    # Verify Q Developer access
    # Return credentials if found

def get_amazonq_usage() -> dict:
    """Fetch Amazon Q usage stats"""
    # Use boto3 or AWS CLI
    # Call relevant Q Developer API
    # Return chat_used, chat_limit, transform_lines, etc.
```

Credential locations:
- `~/.aws/credentials`
- `~/.aws/config`
- Environment: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_PROFILE`
**Registry-era notes (2026-09):**
- Do NOT hand-edit argparse, main() dispatch, or print_oneline() — one `PROVIDERS` entry covers all of them.
- Use the `http_get()` helper for HTTP calls — no direct `requests` usage; keep the zero-dependency urllib fallback.
- Add tests under `tests/` following the existing provider test files; run `python3 -m pytest tests/` before declaring done.
</implementation>

<output>
Modify: `lib/cclimits.py`
Update: `README.md` with Amazon Q section
</output>

<verification>
```bash
python3 lib/cclimits.py --amazonq
```

Expected output (Free tier):
```
==================================================
  Amazon Q Developer
==================================================
  🔑 Auth: AWS Credentials
  ✅ Connected
  📊 Plan: Free

  Chat Messages (Monthly):
    Used:      23 / 50
    Remaining: 27 (54%)
```

Expected output (Pro tier):
```
==================================================
  Amazon Q Developer
==================================================
  🔑 Auth: AWS Credentials
  ✅ Connected
  📊 Plan: Pro

  Chat: Unlimited
  Code Transform:
    Lines:     1,200 / 4,000
    Remaining: 2,800 (70%)
```
</verification>

<success_criteria>
- Discovers AWS credentials from standard locations
- Shows chat message usage for free tier
- Shows code transformation lines for pro tier
- Integrates with existing oneline format
- Graceful error if no Amazon Q subscription
</success_criteria>
