<objective>
Update all documentation to reflect the Gemini tier grouping changes.

The cclimits tool now groups Gemini models by quota tier instead of showing individual models:
- Before: `Gemini: ( 3-flash 7% ✅ | 2.5-pro 10% ✅ | 3-pro 10% ✅ | 2.5-flash 1% ✅ | ... )`
- After: `Gemini: ( 3-Flash 7% ✅ | Flash 1% ✅ | Pro 10% ✅ )`
</objective>

<context>
Gemini models share quotas in tiers:

| Tier | Models |
|------|--------|
| **3-Flash** | gemini-3-flash-preview |
| **Flash** | gemini-2.5-flash, gemini-2.5-flash-lite, gemini-2.0-flash |
| **Pro** | gemini-2.5-pro, gemini-3-pro-preview |

This was implemented in prompt 001. Now the documentation needs to match.
</context>

<requirements>
1. **README.md** - Update all example outputs:
   - Update the "Compact One-liner" example to show tier format
   - Update the "Detailed Output" example to include Gemini and Z.AI sections (currently missing)
   - Ensure example shows tier-based grouping, not individual models

2. **lib/cclimits.py --help epilog** - Update if needed:
   - Check if the help text examples need updating for tier format

3. **memory-bank/productContext.md** - Update example output if present

4. **memory-bank/systemPatterns.md** - Update if Gemini output patterns are documented
</requirements>

<implementation>
Read each file and update example outputs to match this format:

**One-liner example:**
```
Claude: 4.0% (5h) ✅ | Codex: 0% (5h) ✅ | Z.AI: 1% ✅ | Gemini: ( 3-Flash 7% ✅ | Flash 1% ✅ | Pro 10% ✅ )
```

**Detailed Gemini section:**
```
==================================================
  Gemini CLI
==================================================
  🔑 Auth: OAuth (Google Account)
  ✅ Connected
  📊 Tier: standard

  Quota by Tier:
    3-Flash: 7.0% used, 93.0% remaining
    Flash: 1.0% used, 99.0% remaining
    Pro: 10.0% used, 90.0% remaining
```

**Detailed Z.AI section:**
```
==================================================
  Z.AI (GLM-4)
==================================================
  ✅ Connected

  Token Quota:
    Used:      1%
    Remaining: 99%
    (10,000 / 1,000,000 tokens)
```
</implementation>

<output>
Modify these files:
- `./README.md` - Update example outputs
- `./lib/cclimits.py` - Update --help epilog examples if needed
- `./memory-bank/productContext.md` - Update examples if present
- `./memory-bank/systemPatterns.md` - Update if needed
</output>

<verification>
After updates, verify:
```bash
# Check README has updated examples
grep -A5 "Compact One-liner" README.md
grep -A20 "Gemini CLI" README.md

# Check help output
python3 lib/cclimits.py --help | tail -20
```

Ensure all example outputs show:
- Tier names (3-Flash, Flash, Pro) not model names
- Gemini and Z.AI sections in detailed output examples
</verification>

<success_criteria>
- README example outputs match actual tool output format
- Detailed output examples include all 4 tools (Claude, Codex, Gemini, Z.AI)
- One-liner examples show tier grouping
- --help epilog is consistent with README
</success_criteria>
