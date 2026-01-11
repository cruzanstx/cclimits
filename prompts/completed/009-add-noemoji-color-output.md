<objective>
Add `--noemoji` flag to replace emoji status icons with ANSI color-coded text in oneline output.

Some terminals/fonts don't render emojis well. This provides an alternative using colors.
</objective>

<context>
- File: `lib/cclimits.py`
- Function: `get_status_icon()` (returns emoji based on percentage)
- Function: `print_oneline()` (uses status icons)
- Argument parser: around line 1118

Current oneline output:
```
Claude: 4.0% (5h) ✅ | Codex: 1% (5h) ✅ | Z.AI: 1% ✅ | OpenRouter: $47.91 ✅
```

Desired output with `--noemoji`:
```
Claude: 4.0% (5h) [OK] | Codex: 1% (5h) [OK] | Z.AI: 1% [OK] | OpenRouter: $47.91 [OK]
```
Where `[OK]` is green, `[WARN]` is yellow, `[HIGH]` is red, `[FAIL]` is bold red.
</context>

<requirements>
1. Add `--noemoji` flag to argument parser
2. Create ANSI color codes helper:
   ```python
   COLORS = {
       'green': '\033[32m',
       'yellow': '\033[33m',
       'red': '\033[31m',
       'bold_red': '\033[1;31m',
       'reset': '\033[0m'
   }
   ```
3. Modify `get_status_icon()` to accept optional `use_color=False` parameter:
   - `< 70%`: `✅` or green `[OK]`
   - `70-90%`: `⚠️` or yellow `[WARN]`
   - `90-100%`: `🔴` or red `[HIGH]`
   - `100%+` or error: `❌` or bold red `[FAIL]`
4. Pass `use_color` flag through `print_oneline()` to all `get_status_icon()` calls
5. Also handle OpenRouter balance thresholds in color mode
</requirements>

<implementation>
```python
COLORS = {
    'green': '\033[32m',
    'yellow': '\033[33m',
    'red': '\033[31m',
    'bold_red': '\033[1;31m',
    'reset': '\033[0m'
}

def get_status_icon(percentage: float, use_color: bool = False) -> str:
    """Return status icon (emoji or colored text)"""
    if use_color:
        if percentage >= 100:
            return f"{COLORS['bold_red']}[FAIL]{COLORS['reset']}"
        elif percentage >= 90:
            return f"{COLORS['red']}[HIGH]{COLORS['reset']}"
        elif percentage >= 70:
            return f"{COLORS['yellow']}[WARN]{COLORS['reset']}"
        else:
            return f"{COLORS['green']}[OK]{COLORS['reset']}"
    else:
        # existing emoji logic
        ...
```

Update `print_oneline(results, window, use_color=False)` signature.

Add argument:
```python
parser.add_argument("--noemoji", action="store_true",
                    help="Use colored text instead of emojis (for terminals without emoji support)")
```
</implementation>

<output>
Modify: `./lib/cclimits.py`
- Add COLORS constant
- Update `get_status_icon()` function
- Update `print_oneline()` function signature and calls
- Add `--noemoji` argument
- Pass flag from main() to print_oneline()
</output>

<verification>
Test all modes:
```bash
python3 lib/cclimits.py --oneline                # Emojis (default)
python3 lib/cclimits.py --oneline --noemoji      # Colored text
python3 lib/cclimits.py --oneline both --noemoji # Both windows + colors
python3 lib/cclimits.py --oneline 7d --noemoji   # 7d + colors
```

Verify:
- Colors render correctly in terminal
- `[OK]` is green, `[WARN]` is yellow, `[HIGH]` is red, `[FAIL]` is bold red
- OpenRouter balance also uses colored status
- Flag has no effect on non-oneline output (detailed/JSON)
</verification>

<success_criteria>
- `--noemoji` flag works with all `--oneline` variants (5h, 7d, both)
- Colors match the emoji thresholds exactly
- Backward compatible: default behavior unchanged (emojis)
- Works in standard terminals (bash, zsh, etc.)
</success_criteria>
