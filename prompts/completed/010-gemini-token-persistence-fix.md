<objective>
Fix Gemini OAuth token persistence in cclimits so refreshed tokens are saved back to ~/.gemini/oauth_creds.json.

Currently, when a Gemini OAuth token expires, `refresh_gemini_token()` successfully refreshes it via the Google OAuth API, but the new access_token and expiry_date are only stored in memory. On the next run, cclimits must refresh again because the file still has the old expired token.
</objective>

<context>
Project: cclimits - CLI tool for checking AI coding assistant quotas
File: `lib/cclimits.py`

Key functions:
- `refresh_gemini_token()` (line ~546) - Refreshes expired OAuth token via Google API
- `get_gemini_credentials()` (line ~585) - Reads credentials, calls refresh if expired
- OAuth creds file: `~/.gemini/oauth_creds.json`

The refresh logic at lines 625-632 updates the in-memory `result` dict but never writes back to disk.
</context>

<requirements>
1. After successfully refreshing the token, write the updated credentials back to `~/.gemini/oauth_creds.json`
2. Update these fields in the JSON file:
   - `access_token` - new token from refresh response
   - `expiry_date` - new expiry timestamp (milliseconds)
3. Preserve all other fields in the oauth_creds.json file (refresh_token, token_type, etc.)
4. Handle file write errors gracefully (log warning, continue with in-memory token)
5. Maintain atomic write pattern (write to temp file, then rename) to avoid corruption
</requirements>

<implementation>
Location to add persistence logic: After line 632 in `get_gemini_credentials()`, where the refresh succeeds.

Pattern to follow:
```python
# After updating result dict with new tokens...
# Write updated credentials back to file
try:
    oauth_path = Path.home() / ".gemini" / "oauth_creds.json"
    if oauth_path.exists():
        # Read existing file to preserve other fields
        with open(oauth_path) as f:
            oauth_data = json.load(f)
        
        # Update with new values
        oauth_data["access_token"] = new_tokens["access_token"]
        oauth_data["expiry_date"] = new_expiry_ms
        
        # Atomic write
        temp_path = oauth_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(oauth_data, f, indent=2)
        temp_path.rename(oauth_path)
except Exception as e:
    # Log but continue - in-memory token still works
    pass
```

Avoid:
- Overwriting the entire file with only the new fields (would lose refresh_token)
- Non-atomic writes that could corrupt the file
- Failing silently without the in-memory fallback
</implementation>

<verification>
Test the fix:
1. Run `python3 lib/cclimits.py --gemini` - note the token expiry time
2. Manually edit ~/.gemini/oauth_creds.json to set `expiry_date` to a past timestamp (e.g., 1000)
3. Run `python3 lib/cclimits.py --gemini` again
4. Check ~/.gemini/oauth_creds.json - `expiry_date` should now be updated to future timestamp
5. Run `python3 lib/cclimits.py --gemini` a third time - should NOT show "Token auto-refreshed" message

Expected behavior after fix:
- First run after expiry: Shows "🔄 Token auto-refreshed", updates file
- Subsequent runs: Uses cached token, no refresh needed
</verification>

<success_criteria>
- Refreshed tokens are persisted to ~/.gemini/oauth_creds.json
- File preserves existing fields (refresh_token, token_type, etc.)
- Atomic write prevents file corruption
- Graceful fallback if write fails
- No unnecessary token refreshes on consecutive runs
</success_criteria>