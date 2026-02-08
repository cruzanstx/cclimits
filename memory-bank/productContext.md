# Product Context: cclimits

## Problem Statement

Developers using multiple AI coding CLIs (Claude Code, Codex, Gemini, Z.AI, OpenRouter, Kimi) have no unified way to check their quota status. Each tool has different:
- Credential storage locations
- API endpoints for usage data
- Quota windows (5h, 7d, monthly) or prepaid balances
- Output formats

This leads to:
- Unexpected rate limiting mid-task
- Wasted time switching between tools to check status
- No visibility into which tool has capacity

## Solution

A single CLI command that:
1. Auto-discovers credentials for all tools
2. Fetches usage from each tool's API
3. Presents unified status in multiple formats

## User Experience Goals

### Quick Status Check
```bash
$ cclimits --oneline
Claude: 4.0% (5h) ✅ | Codex: 0% (5h) ✅ | Z.AI: 1% ✅ | Gemini: ( 3-Flash 7% ✅ ... ) | Kimi: $49.59 ✅
```

### Detailed Analysis
```bash
$ cclimits --claude
# Shows 5h window, 7d window, Opus usage, reset times
```

### Scripting Integration
```bash
$ cclimits --json | jq '.claude.five_hour.used'
"15.2%"
```

## Status Icons

| Icon | Meaning | Action |
|------|---------|--------|
| ✅ | <70% used | Plenty of capacity |
| ⚠️ | 70-90% used | Plan accordingly |
| 🔴 | 90-100% used | Near limit |
| ❌ | Unavailable | Auth issue or 100% |

## Integration Points

- **daplug /create-prompt**: Uses cclimits to suggest available models
- **CI/CD**: Check quota before running AI-assisted tasks
- **tmux statusline**: Quick quota display
