<objective>
Research the OpenRouter API and add support for displaying account balance/credits remaining.

OpenRouter is a unified API gateway that provides access to many LLM models (Claude, GPT, etc.) with pay-per-use pricing. Users want to see their remaining balance alongside other AI tool quotas.
</objective>

<context>
@lib/cclimits.py - Main Python script (follow existing patterns)
@CLAUDE.md - Project conventions

Existing pattern for each tool:
1. `get_X_credentials()` - Find API key from env vars or config files
2. `get_X_usage()` - Call API and return structured dict
3. Update `print_section()` for detailed output
4. Update `print_oneline()` for compact output
5. Add `--openrouter` CLI flag
</context>

<research>
**Step 1: Research OpenRouter API**

Use web search to find:
1. OpenRouter API documentation URL
2. Authentication method (likely `Authorization: Bearer $OPENROUTER_API_KEY`)
3. Endpoint for checking account balance/credits
4. Response format for balance endpoint

Common OpenRouter API patterns to investigate:
- `https://openrouter.ai/api/v1/auth/key` - Key info endpoint
- `https://openrouter.ai/api/v1/credits` - Credits/balance endpoint
- Look for fields like: `balance`, `credits`, `usage`, `limit`

**Step 2: Test API locally if possible**
```bash
# Check if user has OpenRouter key set
echo $OPENROUTER_API_KEY

# If set, test the API (adjust endpoint based on research)
curl -s https://openrouter.ai/api/v1/auth/key \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" | python3 -m json.tool
```
</research>

<requirements>
**1. Credential Discovery**
```python
def get_openrouter_credentials() -> str | None:
    """Get OpenRouter API key from environment"""
    # Check common env var names
    for var in ["OPENROUTER_API_KEY", "OPENROUTER_KEY"]:
        if key := os.environ.get(var):
            return key
    return None
```

**2. Usage Function**
```python
def get_openrouter_usage() -> dict:
    """Fetch OpenRouter account balance"""
    # Return structure should include:
    # - balance/credits remaining (in USD or credits)
    # - usage if available
    # - rate limit info if available
    # - hint with dashboard URL
```

**3. Output Integration**
- Add OpenRouter section to `print_section()`
- Add OpenRouter to `print_oneline()` - show balance like `OpenRouter: $12.34 ✅`
- Use appropriate status icons based on balance thresholds

**4. CLI Flag**
- Add `--openrouter` flag to argparse
- Include in "check all" when no specific tool selected

**5. Update Documentation**
- Add OpenRouter to epilog help text with credential location
- Add to CLAUDE.md API endpoints table
</requirements>

<implementation>
Follow the existing Z.AI pattern since it's also a balance-based API (not quota percentage):

```python
# For oneline output, show dollar amount:
# OpenRouter: $12.34 ✅

# Status thresholds for balance:
# > $5.00  → ✅
# $1-5    → ⚠️
# < $1.00 → 🔴
# $0 or error → ❌
```

WHY these thresholds: OpenRouter charges ~$0.001-0.01 per 1K tokens depending on model, so $1 is roughly 100-1000 requests minimum.
</implementation>

<output>
Modify: `./lib/cclimits.py`
- Add `get_openrouter_credentials()` function
- Add `get_openrouter_usage()` function
- Update `print_section()` for OpenRouter data
- Update `print_oneline()` for OpenRouter balance
- Add `--openrouter` argparse flag
- Update epilog help text
- Update main() to include OpenRouter in results

Update: `./CLAUDE.md`
- Add OpenRouter to API endpoints table
</output>

<verification>
```bash
cd /storage/projects/docker/cclimits

# Test 1: Check if OPENROUTER_API_KEY is set
echo "OpenRouter key set: $([ -n \"$OPENROUTER_API_KEY\" ] && echo 'yes' || echo 'no')"

# Test 2: Run with --openrouter flag
python3 lib/cclimits.py --openrouter

# Test 3: Run all tools (should include OpenRouter)
python3 lib/cclimits.py

# Test 4: Oneline output
python3 lib/cclimits.py --oneline

# Test 5: JSON output
python3 lib/cclimits.py --json | python3 -c "import sys,json; d=json.load(sys.stdin); print('openrouter' in d)"

# Test 6: Help shows new flag
python3 lib/cclimits.py --help | grep -i openrouter
```

Before declaring complete, verify:
- [ ] Research found correct API endpoint for balance
- [ ] `get_openrouter_credentials()` checks appropriate env vars
- [ ] `get_openrouter_usage()` returns balance in consistent format
- [ ] `--openrouter` flag works standalone
- [ ] OpenRouter included when running without flags
- [ ] Oneline shows balance with status icon
- [ ] Graceful handling when API key not set
</verification>

<success_criteria>
- OpenRouter balance displays alongside other tools
- Works with `OPENROUTER_API_KEY` environment variable
- Balance shown as dollar amount (e.g., "$12.34")
- Appropriate status icons based on balance level
- Graceful error handling when key missing or API fails
- Follows existing code patterns and style
</success_criteria>
