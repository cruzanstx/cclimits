<objective>
Update the detailed output (`print_section()`) to show Gemini models grouped by tier instead of individual models.

Currently the detailed output shows:
```
  Model Quotas:
    gemini-2.0-flash: 0.5% used, 99.5% remaining (resets: 15h 59m)
    gemini-2.5-flash: 0.5% used, 99.5% remaining (resets: 15h 59m)
    gemini-2.5-flash-lite: 0.5% used, 99.5% remaining (resets: 15h 59m)
    gemini-2.5-pro: 10.4% used, 89.6% remaining (resets: 13h 18m)
    gemini-3-flash-preview: 7.3% used, 92.7% remaining (resets: 13h 18m)
    gemini-3-pro-preview: 10.4% used, 89.6% remaining (resets: 13h 18m)
```

Change it to show tiers (matching the --oneline format):
```
  Quota by Tier:
    3-Flash: 7.3% used, 92.7% remaining (resets: 13h 18m)
    Flash: 0.5% used, 99.5% remaining (resets: 15h 59m)
    Pro: 10.4% used, 89.6% remaining (resets: 13h 18m)
```
</objective>

<context>
The GEMINI_TIERS constant was already added by prompt 001:
```python
GEMINI_TIERS = {
    "3-Flash": ["gemini-3-flash-preview"],
    "Flash": ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"],
    "Pro": ["gemini-2.5-pro", "gemini-3-pro-preview"],
}
```

The `print_oneline()` function already uses tier grouping. Now `print_section()` needs the same treatment for the Gemini "models" section.
</context>

<requirements>
1. Update the Gemini section in `print_section()` to group by tier
2. Change label from "Model Quotas:" to "Quota by Tier:"
3. Use the same GEMINI_TIERS constant and tier order (3-Flash, Flash, Pro)
4. For each tier, take usage from the first available model in that tier
5. Include reset time from that model
6. Only show tiers that have data
</requirements>

<implementation>
In `print_section()`, find the block that handles `if "models" in data:` and replace the individual model iteration with tier grouping logic similar to `print_oneline()`.

```python
# Gemini tier quotas
if "models" in data:
    print(f"\n  Quota by Tier:")
    tier_order = ["3-Flash", "Flash", "Pro"]
    for tier_name in tier_order:
        tier_models = GEMINI_TIERS.get(tier_name, [])
        for model_id in tier_models:
            if model_id in data["models"]:
                model_data = data["models"][model_id]
                used = model_data.get("used", "?")
                remaining = model_data.get("remaining", "?")
                reset = model_data.get("resets_in", "")
                reset_str = f" (resets: {reset})" if reset else ""
                print(f"    {tier_name}: {used} used, {remaining} remaining{reset_str}")
                break  # Only need first model from each tier
```
</implementation>

<output>
Modify: `./lib/cclimits.py`
- Update the "models" section in `print_section()` to use tier grouping
</output>

<verification>
Test the changes:
```bash
python3 lib/cclimits.py --gemini
```

Expected output:
```
==================================================
  Gemini CLI
==================================================
  🔑 Auth: OAuth (Google Account)
  ✅ Connected
  📊 Tier: Gemini Code Assist

  Quota by Tier:
    3-Flash: 7.3% used, 92.7% remaining (resets: 13h 18m)
    Flash: 0.5% used, 99.5% remaining (resets: 15h 59m)
    Pro: 10.4% used, 89.6% remaining (resets: 13h 18m)
```
</verification>

<success_criteria>
- Detailed Gemini output shows 3 tiers instead of 6 individual models
- Label changed to "Quota by Tier:"
- Tier order is: 3-Flash, Flash, Pro
- Reset times are preserved
- Both --gemini and full output (no flags) work correctly
</success_criteria>
