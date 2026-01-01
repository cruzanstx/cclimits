<objective>
Refactor the Gemini model display in cclimits to group models by quota tier instead of showing individual models.

Currently the --oneline output shows:
```
Gemini: ( 3-flash 7.3% ✅ | 2.5-pro 10% ✅ | 3-pro 10% ✅ | 2.5-flash 0.5% ✅ | 2.5-lite 0.5% ✅ | 2.0-flash 0.5% ✅ )
```

Change it to show tiers (models that share the same quota bucket):
```
Gemini: ( 3-Flash 7% ✅ | Flash 1% ✅ | Pro 10% ✅ )
```
</objective>

<context>
Gemini models share quotas in tiers (observed with Google One Premium):

| Tier | Models | Display Name |
|------|--------|--------------|
| **3-Flash** | gemini-3-flash-preview | "3-Flash" |
| **Flash** | gemini-2.5-flash, gemini-2.5-flash-lite, gemini-2.0-flash | "Flash" |
| **Pro** | gemini-2.5-pro, gemini-3-pro-preview | "Pro" |

Models within the same tier have identical usage percentages since they share a quota bucket.
</context>

<requirements>
1. Update `print_oneline()` function in `lib/cclimits.py` to group models by tier
2. For each tier, take the usage from any model in that tier (they're identical)
3. Display order should be: 3-Flash | Flash | Pro
4. Only show tiers that have data (some users may not have all models)
5. Keep the status icon logic unchanged (✅ ⚠️ 🔴 ❌)
</requirements>

<implementation>
Define a tier mapping constant:
```python
GEMINI_TIERS = {
    "3-Flash": ["gemini-3-flash-preview"],
    "Flash": ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"],
    "Pro": ["gemini-2.5-pro", "gemini-3-pro-preview"],
}
```

In `print_oneline()`, iterate through tiers and find the first matching model to get the usage percentage.
</implementation>

<output>
Modify: `./lib/cclimits.py`
- Add GEMINI_TIERS constant near the top (after imports)
- Update print_oneline() to use tier grouping for Gemini
</output>

<verification>
Test the changes:
```bash
python3 lib/cclimits.py --oneline
python3 lib/cclimits.py --oneline 7d
```

Expected output format:
```
Claude: X% (5h) ✅ | Codex: X% (5h) ✅ | Z.AI: X% ✅ | Gemini: ( 3-Flash X% ✅ | Flash X% ✅ | Pro X% ✅ )
```
</verification>

<success_criteria>
- Gemini output shows 3 tiers instead of 6 individual models
- Tiers with no data are omitted
- Status icons still work correctly based on percentage thresholds
- Both 5h and 7d windows work
</success_criteria>
