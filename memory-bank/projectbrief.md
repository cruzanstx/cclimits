# Project Brief: cclimits

## Overview

**cclimits** is a CLI tool that checks quota and usage for AI coding assistants: Claude Code, OpenAI Codex, Google Gemini CLI, and Z.AI.

## Goals

1. **Unified quota checking** - Single command to check all AI CLI tools
2. **Zero configuration** - Auto-discover credentials from standard locations
3. **Multiple output formats** - Detailed, JSON, and compact one-liner
4. **Cross-platform** - Works on macOS and Linux

## Core Requirements

### Functional
- Check Claude Code usage (5h and 7d windows)
- Check OpenAI Codex usage (ChatGPT subscription quota)
- Check Gemini CLI usage (per-model quotas)
- Check Z.AI usage (token quota)
- Auto-refresh expired Gemini OAuth tokens
- Support JSON output for scripting
- Support compact one-liner for quick status

### Non-Functional
- No external dependencies required (urllib fallback)
- Python 3.10+ compatible
- Fast execution (<5s for all tools)
- Graceful degradation if tools unavailable

## Distribution

- **npm/npx**: Primary distribution (`npx cclimits`)
- **GitHub**: Source and direct download
- **daplug plugin**: Bundled as skill in rogers_ai_rules

## Target Users

- Developers using multiple AI coding assistants
- Teams managing shared AI tool quotas
- Automation scripts that need to check capacity before running
