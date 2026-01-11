<objective>
Add Windsurf (Codeium) quota checking to cclimits.

Windsurf/Codeium has a credit-based system with 500 prompts/month on Pro that users need to track.
</objective>

<context>
Project: cclimits - CLI tool for checking AI coding assistant quotas
File: `lib/cclimits.py`

Research findings (from `research/ai-coding-providers.md`):
- Plans: Free (25 prompts/mo), Pro ($15/mo - 500 prompts/mo)
- Pro ~= 2000 "credits"
- Rate limits exist for free tier
- `codeium-parse` CLI exists but is for syntax only
- Config stored in `~/.codeium/` JSON files
- Internal API used by IDE status bar for usage display
</context>

<research_required>
Before implementing, investigate:
1. Check `~/.codeium/` directory for config structure
2. Look for auth tokens in `~/.codeium/config.json` or similar
3. Inspect Windsurf/Codeium IDE network traffic for usage endpoints
4. Check Codeium website dashboard for API calls
5. Look for any `codeium` CLI commands that might expose usage
</research_required>

<requirements>
1. Add `get_windsurf_credentials()` function
2. Add `get_windsurf_usage()` function to fetch prompt/credit usage
3. Add `--windsurf` CLI flag to filter output
4. Display prompts used vs limit
5. Show credit balance if available
</requirements>

<implementation>
Pattern to follow:
```python
def get_windsurf_credentials() -> dict | None:
    """Get Windsurf/Codeium credentials from config"""
    # Check ~/.codeium/ for auth files
    # Parse JSON config for API key/token
    # Return credentials if found

def get_windsurf_usage() -> dict:
    """Fetch Windsurf/Codeium usage stats"""
    # Call internal API endpoint
    # Parse for prompt count, credits, etc.
    # Return usage stats
```

Likely credential locations:
- `~/.codeium/config.json`
- `~/.codeium/codeium.json`
- `~/Library/Application Support/Codeium/` (macOS)
</implementation>

<output>
Modify: `lib/cclimits.py`
Update: `README.md` with Windsurf section
</output>

<verification>
```bash
python3 lib/cclimits.py --windsurf
```

Expected output:
```
==================================================
  Windsurf (Codeium)
==================================================
  🔑 Auth: Local config
  ✅ Connected
  📊 Plan: Pro

  Prompts (Monthly):
    Used:      89 / 500
    Remaining: 411 (82%)
    Resets in: 18d
```
</verification>

<success_criteria>
- Discovers Codeium credentials from config
- Shows prompt usage (X / 500)
- Shows plan type (Free/Pro)
- Indicates when quota resets
- Oneline format: `Windsurf: 18% (89/500) ✅`
</success_criteria>
