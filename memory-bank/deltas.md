# Recent Deltas (Last 3-5 Changes)

## 2026-01-11: Z.AI 5h + Gemini Token Persistence (v1.2.5-1.2.7)

- Added `(5h)` indicator to Z.AI quota in oneline output
- Updated verbose section header to "Z.AI (5h shared - GLM-4.x)"
- Z.AI quota is shared across GLM-4.7, GLM-4.6, GLM-4.5V, GLM-4.5, GLM-4.5-Air, and Visual Analysis
- Fixed Gemini OAuth token persistence with atomic writes (temp file + rename)
- Added `.npmignore` and fixed `package.json` to exclude `__pycache__` (package size: 64KB → 15KB)
- Updated README examples to reflect Z.AI 5h window

**Files:** `lib/cclimits.py`, `CLAUDE.md`, `README.md`, `package.json`, `.npmignore`

## 2026-01-10: Oneline Both Mode + Noemoji Flag (v1.2.3-1.2.4)

- Added `--oneline both` to show 5h/7d windows simultaneously
- Added `--noemoji` flag for color-coded percentages instead of emoji icons
- Useful for terminals without emoji support

**Files:** `lib/cclimits.py`

## 2026-01-01: Gemini Tiers Refactoring

- Grouped Gemini models by quota tier (3-Flash, Flash, Pro)
- Reduced display from 6 models to 3 tiers
- Each tier shows usage from first available model in quota bucket
- Status icons continue to work correctly across all tiers

**Files:** `lib/cclimits.py`

## 2026-01-01: Initial npm Release (v1.0.0)

- Published to npm as `cclimits`
- Added Node.js wrapper for npx support
- Moved Python script to `lib/cclimits.py`
- Created memory-bank documentation

**Files:** `package.json`, `bin/cclimits.js`, `lib/cclimits.py`

## 2026-01-01: Repository Created

- Extracted from daplug plugin (`rogers_ai_rules/plugins/daplug/skills/ai-usage`)
- Refactored Gemini OAuth to extract credentials from CLI installation
- Added comprehensive README with usage examples
- MIT license

**Files:** `lib/cclimits.py`, `README.md`, `LICENSE`
