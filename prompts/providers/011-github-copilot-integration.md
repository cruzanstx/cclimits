<objective>
Add GitHub Copilot quota/usage checking to cclimits.

GitHub Copilot is the most widely-used AI coding assistant. While it advertises "unlimited" completions, there are rate limits and the `gh` CLI may expose usage data.
</objective>

<context>
Project: cclimits - CLI tool for checking AI coding assistant quotas
File: `lib/cclimits.py`

Research findings (from `research/ai-coding-providers.md`):
- Plans: Individual ($10/mo), Business ($19/mo), Enterprise ($39/mo)
- Rate limiting is dynamic and undisclosed
- `gh copilot` CLI extension exists
- Credentials managed by `gh` CLI auth (standard GitHub tokens)
- Potential endpoint: `https://api.github.com/copilot/...` or internal `gh` calls
</context>

<research_required>
Before implementing, investigate:
1. Run `gh copilot --help` to see available commands
2. Check if `gh api /user/copilot` or similar endpoints exist
3. Inspect `gh` CLI source or network traffic for Copilot status calls
4. Look for usage/quota data in GitHub settings page network requests
5. Check `~/.config/gh/` for relevant config files
</research_required>

<requirements>
1. Add `get_copilot_credentials()` function to discover GitHub auth
2. Add `get_copilot_usage()` function to fetch usage/status
3. Add `--copilot` CLI flag to filter output
4. Display connection status and any available quota info
5. Graceful fallback if Copilot subscription not found
</requirements>

<implementation>
Pattern to follow (see existing integrations):
```python
def get_copilot_credentials() -> dict | None:
    """Get GitHub Copilot credentials via gh CLI"""
    # Check if gh CLI is installed
    # Check if user has copilot access
    # Return token/auth info

def get_copilot_usage() -> dict:
    """Fetch GitHub Copilot usage/status"""
    # Use gh CLI or GitHub API
    # Return status, plan info, any usage metrics
```

Credential locations to check:
- `gh auth status` output
- `~/.config/gh/hosts.yml`
- Environment: `GITHUB_TOKEN`, `GH_TOKEN`
</implementation>

<output>
Modify: `lib/cclimits.py`
Update: `README.md` with Copilot section
</output>

<verification>
```bash
python3 lib/cclimits.py --copilot
```

Expected output (if Copilot active):
```
==================================================
  GitHub Copilot
==================================================
  🔑 Auth: GitHub CLI (gh)
  ✅ Connected
  📊 Plan: Individual

  Status: Active
  [Any usage metrics if available]
```
</verification>

<success_criteria>
- Detects GitHub Copilot subscription status
- Shows plan type (Individual/Business/Enterprise)
- Displays any available usage metrics
- Works with existing `gh` CLI authentication
- Graceful error if no Copilot subscription
</success_criteria>
