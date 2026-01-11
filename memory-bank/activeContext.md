# Active Context

## Current Focus

- Researching additional AI coding providers (Cursor, Copilot, Replit, etc.)
- Post v1.0.0 maintenance and documentation updates

## Recent Changes (Last 7 Days)

- **2026-01-11**: Completed research on 8 AI coding providers (`research/ai-coding-providers.md`)
- **2026-01-11**: Updated README to clarify support for BYOK tools (Aider, Continue)
- **2026-01-01**: Refactored Gemini display to show quota tiers (3-Flash | Flash | Pro)
- **2026-01-01**: Published to npm as `cclimits@1.0.0`
- **2026-01-01**: Added npm/npx distribution (Node wrapper)
- **2026-01-01**: Created standalone repo from daplug skill
- **2026-01-01**: Refactored Gemini OAuth to extract from CLI installation (avoid hardcoded secrets)

## Blocked/Waiting

- Replit integration requires a Replit account/token for implementation/testing.

## Next Steps

1. Implement Replit support (High feasibility endpoint identified)
2. Monitor GitHub Copilot/Cursor for future public API availability
3. Add tests
4. Add CI/CD for automated npm publishing

## Key Patterns

- **BYOK Tools**: Aider and Continue use standard API keys; `cclimits` supports them indirectly by monitoring the underlying provider (OpenAI/Anthropic/etc).
- **Integrated Tools**: Cursor, Windsurf, Copilot, JetBrains have "hidden" or internal-only usage APIs, making CLI integration difficult without reverse engineering.
- **Replit**: Uses a specific "usage credits" model with a likely accessible endpoint.