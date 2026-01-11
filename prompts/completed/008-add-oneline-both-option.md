<objective>
Add `--oneline both` option to show both 5h and 7d time windows in compact format.

Currently `--oneline` shows either 5h OR 7d. Users want to see both windows together for statusline use.
</objective>

<context>
- File: `lib/cclimits.py`
- Function: `print_oneline()` (around line 996)
- Argument parser: around line 1118
- This is for Claude Code statusline integration

Current output:
```
Claude: 4.0% (5h) ✅ | Codex: 1% (5h) ✅ | Z.AI: 1% ✅ | OpenRouter: $47.91 ✅
```

Desired output with `--oneline both`:
```
Claude: 4%/10% ✅ | Codex: 1%/5% ✅ | Z.AI: 1% ✅ | OpenRouter: $47.91 ✅
```

Format rationale: Drop the `(5h)` label - order is consistent (5h/7d), so labels are redundant noise.
</context>

<requirements>
1. Add "both" as valid window option alongside "5h" and "7d"
2. Update `print_oneline()` to handle `window="both"`:
   - Claude: Show `{5h_pct}/{7d_pct}` (e.g., "4%/10%")
   - Codex: Show `{primary}/{secondary}` (e.g., "1%/5%")
   - Gemini: Keep current tier format (no dual windows)
   - Z.AI: Keep current format (no dual windows, just total quota)
   - OpenRouter: Keep current format (balance only)
3. Status icon should be based on the HIGHER of the two percentages (more conservative)
4. Update help text to mention "both" option
</requirements>

<implementation>
In `print_oneline()`, add handling for `window == "both"`:

```python
# Claude
if window == "both" and "five_hour" in data and "seven_day" in data:
    pct_5h = data["five_hour"]["used"].rstrip("%")
    pct_7d = data["seven_day"]["used"].rstrip("%")
    max_pct = max(float(pct_5h), float(pct_7d))
    parts.append(f"Claude: {pct_5h}%/{pct_7d}% {get_status_icon(max_pct)}")
```

Similar pattern for Codex with primary_window/secondary_window.

Update argument parser help text:
```python
parser.add_argument("--oneline", nargs="?", const="5h", metavar="WINDOW",
                    help="Compact one-liner output (5h, 7d, or both; default: 5h)")
```

Update window validation (around line 1166):
```python
window = args.oneline if args.oneline in ("5h", "7d", "both") else "5h"
```
</implementation>

<output>
Modify: `./lib/cclimits.py`
- Update `print_oneline()` function
- Update argument parser help text
- Update window validation
</output>

<verification>
Test all oneline modes:
```bash
python3 lib/cclimits.py --oneline        # 5h (default)
python3 lib/cclimits.py --oneline 5h     # 5h explicit
python3 lib/cclimits.py --oneline 7d     # 7d
python3 lib/cclimits.py --oneline both   # NEW: both windows
python3 lib/cclimits.py --oneline invalid  # Should fall back to 5h
```

Verify output format for `--oneline both`:
- Claude shows `X%/Y%` format (no labels)
- Codex shows `X%/Y%` format (no labels)
- Z.AI shows single percentage (unchanged)
- OpenRouter shows dollar amount (unchanged)
- Gemini shows tier format (unchanged)
</verification>

<success_criteria>
- `--oneline both` produces compact dual-window output
- Status icons use the higher percentage (conservative)
- Backward compatible: existing `--oneline`, `--oneline 5h`, `--oneline 7d` unchanged
- Invalid window values fall back to "5h"
</success_criteria>
