<objective>
Add a caching layer to cclimits so that `--oneline` can return instantly for statusline integration.

The primary use case is shell/tmux statusline integration where cclimits is called frequently (every prompt render). Without caching, each call makes 4 API requests which is too slow and wastes quota. With caching, we read from disk if data is fresh, only fetching when stale.
</objective>

<context>
@lib/cclimits.py - Main Python script to modify
@CLAUDE.md - Project conventions

Current behavior:
- Every invocation makes live API calls to Claude, Codex, Gemini, Z.AI
- `--oneline` is ideal for statusline but too slow due to network latency

Desired behavior:
- Cache results to `~/.cache/cclimits/usage.json`
- Use cached data if younger than TTL (default: 60 seconds)
- Fetch fresh data if cache is stale or missing
- New flags: `--cached` and `--cache-ttl N`
</context>

<requirements>
**1. Cache File Structure**
Location: `~/.cache/cclimits/usage.json`
```json
{
  "timestamp": 1704067200,
  "data": {
    "claude": { ... },
    "codex": { ... },
    "gemini": { ... },
    "zai": { ... }
  }
}
```

**2. New CLI Flags**
- `--cached` - Use cache if fresh (< TTL), fetch if stale. Without this flag, always fetch fresh.
- `--cache-ttl SECONDS` - Override default TTL (default: 60). Implies `--cached`.

**3. Cache Logic**
```
if --cached or --cache-ttl specified:
    if cache exists and age < TTL:
        return cached data
    else:
        fetch fresh data
        write to cache
        return fresh data
else:
    fetch fresh data (current behavior)
    optionally update cache for future --cached calls
```

**4. Directory Creation**
Create `~/.cache/cclimits/` if it doesn't exist (use `os.makedirs(..., exist_ok=True)`).

**5. Error Handling**
- If cache file is corrupted/unreadable, fetch fresh
- If cache write fails, continue silently (don't break the command)
- Handle permission errors gracefully

**6. Statusline Usage Examples**
```bash
# Fast statusline query (uses cache)
cclimits --oneline --cached

# Custom TTL for more frequent updates
cclimits --oneline --cache-ttl 30

# Force fresh fetch (default, current behavior)
cclimits --oneline

# JSON with cache
cclimits --json --cached
```
</requirements>

<implementation>
Add these functions to `lib/cclimits.py`:

```python
CACHE_DIR = Path.home() / ".cache" / "cclimits"
CACHE_FILE = CACHE_DIR / "usage.json"
DEFAULT_CACHE_TTL = 60  # seconds

def get_cache_path() -> Path:
    """Get cache file path, creating directory if needed"""
    ...

def read_cache(ttl: int) -> dict | None:
    """Read cache if fresh (younger than TTL seconds), return None if stale/missing"""
    ...

def write_cache(data: dict) -> bool:
    """Write data to cache file, return success status"""
    ...
```

Modify `main()`:
1. Add `--cached` and `--cache-ttl` arguments to argparse
2. Before fetching, check cache if `--cached` or `--cache-ttl` is set
3. After fetching, write to cache (always, so future `--cached` calls have data)

WHY always write cache even without --cached flag:
- Prepopulates cache for statusline use
- No downside (disk write is fast)
- User running `cclimits` manually seeds cache for their statusline
</implementation>

<output>
Modify: `./lib/cclimits.py`
- Add cache constants near top
- Add `get_cache_path()`, `read_cache()`, `write_cache()` functions
- Update argparse with new flags
- Update main() logic to use cache when appropriate
</output>

<verification>
```bash
cd /storage/projects/docker/cclimits

# Test 1: Fresh fetch (no cache flag)
python3 lib/cclimits.py --oneline
# Should make API calls, take 2-5 seconds

# Test 2: Check cache was written
ls -la ~/.cache/cclimits/usage.json
cat ~/.cache/cclimits/usage.json | python3 -m json.tool | head -20

# Test 3: Cached query (should be instant)
time python3 lib/cclimits.py --oneline --cached
# Should return in <0.1 seconds

# Test 4: Custom TTL
python3 lib/cclimits.py --oneline --cache-ttl 5
sleep 6
time python3 lib/cclimits.py --oneline --cache-ttl 5
# Should refetch after 6 seconds (TTL expired)

# Test 5: JSON output with cache
python3 lib/cclimits.py --json --cached

# Test 6: Help text shows new flags
python3 lib/cclimits.py --help | grep -A2 cached
```

Before declaring complete, verify:
- [ ] Cache file is created at `~/.cache/cclimits/usage.json`
- [ ] `--cached` returns instantly when cache is fresh
- [ ] `--cache-ttl N` respects custom TTL
- [ ] Cache expiration works correctly
- [ ] Corrupted cache doesn't crash the tool
- [ ] `--help` shows new flags with descriptions
</verification>

<success_criteria>
- `cclimits --oneline --cached` returns in <0.1 seconds when cache is fresh
- Cache TTL is configurable and defaults to 60 seconds
- Cache corruption is handled gracefully
- Existing behavior (without --cached) is unchanged
- New flags are documented in --help
</success_criteria>
