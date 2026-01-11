<objective>
Add Replit AI credit/budget checking to cclimits.

Replit has a clear credit-based system ($25/mo on Core plan) that's perfect for quota monitoring. The research identified this as HIGH feasibility.
</objective>

<context>
Project: cclimits - CLI tool for checking AI coding assistant quotas
File: `lib/cclimits.py`

Research findings (from `research/ai-coding-providers.md`):
- Plans: Starter (free), Core ($25/mo)
- Core includes $25/mo of "Cloud Usage" credits
- AI Agent checkpoints cost ~$0.25 each
- `replit` CLI exists for repl management
- Credentials via env var: `REPLIT_TOKEN`
- Internal GraphQL API exposes remaining credits/budget
- Endpoint identified: `usage-credits-balance`
</context>

<research_required>
Before implementing, investigate:
1. Check Replit dashboard network traffic for GraphQL queries
2. Look for `usage-credits-balance` or similar endpoints
3. Test `replit` CLI for any usage commands
4. Check what auth headers Replit dashboard sends
5. Document the GraphQL schema for credit queries
</research_required>

<requirements>
1. Add `get_replit_credentials()` function (env var + config)
2. Add `get_replit_usage()` function to fetch credit balance
3. Add `--replit` CLI flag to filter output
4. Display remaining credits in dollars
5. Show percentage of monthly budget used
</requirements>

<implementation>
Pattern to follow:
```python
def get_replit_credentials() -> str | None:
    """Get Replit token from environment or config"""
    # Check REPLIT_TOKEN env var
    # Check ~/.replit/ config files
    # Return token if found

def get_replit_usage() -> dict:
    """Fetch Replit credit balance via GraphQL"""
    # Query GraphQL API for credit/budget info
    # Parse response for remaining balance
    # Return balance, used, limit
```

API endpoint pattern:
```python
# GraphQL query for credits
query = """
query {
  currentUser {
    credits {
      balance
      used
      limit
    }
  }
}
"""
```
</implementation>

<output>
Modify: `lib/cclimits.py`
Update: `README.md` with Replit section
</output>

<verification>
```bash
python3 lib/cclimits.py --replit
```

Expected output:
```
==================================================
  Replit AI
==================================================
  🔑 Auth: API Token
  ✅ Connected
  📊 Plan: Core

  Credits (Monthly):
    Balance:   $18.50
    Used:      $6.50 / $25.00
    Remaining: 74%
```
</verification>

<success_criteria>
- Discovers Replit token from env or config
- Shows credit balance in dollars
- Shows percentage used
- Integrates with existing oneline format: `Replit: $18.50 ✅`
- Graceful error if no Replit account
</success_criteria>
