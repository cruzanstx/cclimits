# Progress: cclimits

## What Works

### Core Features ✅
- [x] Claude Code usage (5h, 7d, Opus windows)
- [x] OpenAI Codex usage (ChatGPT subscription quota)
- [x] Gemini CLI usage (per-model quotas)
- [x] Z.AI usage (token quota)
- [x] Auto-refresh Gemini OAuth tokens
- [x] JSON output mode
- [x] Compact one-liner mode (5h/7d)
- [x] Status icons (✅ ⚠️ 🔴 ❌)

### Credential Discovery ✅
- [x] macOS Keychain for Claude
- [x] Linux credential files for Claude
- [x] Codex auth.json parsing
- [x] Gemini oauth_creds.json parsing
- [x] Environment variable fallbacks
- [x] Nested credential structure handling

### Distribution ✅
- [x] npm package published (cclimits@1.0.0)
- [x] npx support working
- [x] GitHub repo (cruzanstx/cclimits)
- [x] MIT license

## What's Left

### Short-term
- [ ] Add automated tests
- [ ] Add CI/CD (GitHub Actions)
- [ ] Add Windows support
- [ ] Add `--version` flag

### Long-term
- [ ] TypeScript rewrite (eliminate Python dependency)
- [ ] Add more AI tools (Cursor, Aider, Continue)
- [ ] Add quota alerts/notifications
- [ ] Add historical tracking

## Known Issues

### Gemini OAuth Extraction
If Gemini CLI is installed via a non-standard path, OAuth credentials won't be auto-extracted. Workaround: Set `GEMINI_OAUTH_CLIENT_ID` and `GEMINI_OAUTH_CLIENT_SECRET` environment variables.

### Z.AI No Window Info
Z.AI API returns total quota percentage but no 5h/7d window breakdown. The percentage shown is overall monthly quota.

### Codex API Key Mode
If using `OPENAI_API_KEY` without ChatGPT OAuth, quota info isn't available (OpenAI doesn't expose subscription quota via API key).

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-01 | Initial release |
