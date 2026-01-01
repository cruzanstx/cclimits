# Active Context

## Current Focus

- Post v1.0.0 maintenance and user feedback improvements
- Just completed: Gemini display refactoring to show quota tiers

## Recent Changes (Last 7 Days)

- **2026-01-01**: Refactored Gemini display to show quota tiers (3-Flash | Flash | Pro)
- **2026-01-01**: Published to npm as `cclimits@1.0.0`
- **2026-01-01**: Added npm/npx distribution (Node wrapper)
- **2026-01-01**: Created standalone repo from daplug skill
- **2026-01-01**: Refactored Gemini OAuth to extract from CLI installation (avoid hardcoded secrets)

## Blocked/Waiting

None currently.

## Next Steps

1. Consider TypeScript rewrite for native npm (no Python dependency)
2. Add tests
3. Add CI/CD for automated npm publishing
4. Consider adding more AI tools (Cursor, Aider, etc.)

## Key Patterns

- Gemini models share quotas in tiers (observed with Google One Premium)
- 3-Flash tier: `gemini-3-flash-preview`
- Flash tier: `gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemini-2.0-flash`
- Pro tier: `gemini-2.5-pro`, `gemini-3-pro-preview`
- Within each tier, usage is identical since they share quota bucket
