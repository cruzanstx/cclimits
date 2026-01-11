<objective>
Add Cursor AI quota checking to cclimits.

Cursor is rapidly growing in popularity and has a clear "500 fast requests/month" limit on Pro plans that users actively need to track.
</objective>

<context>
Project: cclimits - CLI tool for checking AI coding assistant quotas
File: `lib/cclimits.py`

Research findings (from `research/ai-coding-providers.md`):
- Plans: Hobby (free), Pro ($20/mo), Business ($40/mo)
- Pro limit: 500 "fast" GPT-4/Claude requests per month
- After 500, drops to "slow" queue (degraded performance)
- No official public API
- Electron app stores config in `~/.cursor/` or similar
- Internal API used by settings page to show "Requests used"
</context>

<research_required>
Before implementing, investigate:
1. Check `~/.cursor/` directory structure for config/auth files
2. Run Cursor and inspect network traffic (DevTools) when viewing usage in settings
3. Look for JWT tokens or API keys in config files
4. Identify the internal API endpoint that returns usage stats
5. Check for any `.cursor-tutor` or similar hidden directories
</research_required>

<requirements>
1. Add `get_cursor_credentials()` function to discover Cursor auth
2. Add `get_cursor_usage()` function to fetch usage stats
3. Add `--cursor` CLI flag to filter output
4. Display fast/slow request counts and remaining quota
5. Show when quota resets (monthly)
</requirements>

<implementation>
Pattern to follow:
```python
def get_cursor_credentials() -> dict | None:
    """Get Cursor credentials from config files"""
    # Check ~/.cursor/ for auth tokens
    # Parse relevant JSON/config files
    # Return auth token if found

def get_cursor_usage() -> dict:
    """Fetch Cursor usage from internal API"""
    # Call internal Cursor API endpoint
    # Parse response for usage stats
    # Return fast_used, fast_limit, slow_used, etc.
```

Likely credential locations:
- `~/.cursor/`
- `~/Library/Application Support/Cursor/` (macOS)
- `~/.config/Cursor/` (Linux)
</implementation>

<output>
Modify: `lib/cclimits.py`
Update: `README.md` with Cursor section
</output>

<verification>
```bash
python3 lib/cclimits.py --cursor
```

Expected output:
```
==================================================
  Cursor
==================================================
  🔑 Auth: Local config
  ✅ Connected
  📊 Plan: Pro

  Fast Requests (Monthly):
    Used:      127 / 500
    Remaining: 373
    Resets in: 12d

  Slow Requests: Unlimited
```
</verification>

<success_criteria>
- Discovers Cursor credentials from config files
- Shows fast request usage (X / 500)
- Shows plan type
- Indicates when quota resets
- Oneline format: `Cursor: 25% (127/500) ✅`
</success_criteria>
