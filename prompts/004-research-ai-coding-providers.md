<research_objective>
Research AI coding assistants and providers that have subscription-based plans with usage limits, quotas, or rate limiting - similar to Claude Code and OpenAI Codex.

The goal is to identify potential candidates for cclimits to support in the future. We need providers that:
1. Have CLI tools or APIs that developers use for coding
2. Have usage limits, quotas, or rate limiting on paid plans
3. Potentially have APIs to check usage/quota status
</research_objective>

<scope>
Focus on:
- AI coding assistants with subscription plans (Pro, Teams, Enterprise tiers)
- Tools that have documented usage limits or rate limiting
- Priority on tools with CLI interfaces or VS Code extensions that might expose quota APIs

Known providers already supported by cclimits:
- Claude Code (Anthropic) - ✅ Already supported
- OpenAI Codex CLI - ✅ Already supported
- Google Gemini CLI - ✅ Already supported
- Z.AI - ✅ Already supported

Providers to research:
- Cursor (cursor.sh)
- Windsurf (Codeium)
- GitHub Copilot
- Sourcegraph Cody
- Amazon CodeWhisperer / Amazon Q Developer
- Tabnine
- Replit AI
- JetBrains AI Assistant
- Continue.dev
- Aider
- Any others discovered during research
</scope>

<research_questions>
For each provider, answer:

1. **Plan Structure**: What subscription tiers exist? (Free, Pro, Teams, Enterprise)
2. **Usage Limits**: Are there documented limits? (requests/day, tokens/month, etc.)
3. **Rate Limiting**: Is there rate limiting? How is it structured?
4. **CLI/API Access**: Is there a CLI tool? Can limits be checked programmatically?
5. **Credential Storage**: Where are credentials typically stored? (config files, env vars, keychain)
6. **Quota API**: Is there an API endpoint to check remaining quota?
7. **Feasibility**: How feasible is it to add to cclimits? (High/Medium/Low)
</research_questions>

<deliverables>
Save findings to: `./research/ai-coding-providers.md`

Format as a markdown document with:
1. Executive summary (top candidates)
2. Detailed analysis per provider
3. Comparison table
4. Recommendations for which to implement first
</deliverables>

<evaluation_criteria>
Prioritize providers that:
- Have clear usage limits on their plans
- Have CLI tools or accessible APIs
- Have large user bases (worth supporting)
- Have discoverable credential locations
- Potentially expose quota/usage APIs

Mark as "not feasible" if:
- No usage limits exist
- No programmatic access to usage data
- Purely IDE-embedded with no external API
</evaluation_criteria>

<verification>
Before completing, verify:
- [ ] At least 8 providers researched
- [ ] Each has answers to all 7 research questions
- [ ] Comparison table is complete
- [ ] Clear recommendations provided
- [ ] Sources cited where possible
</verification>

<execution>
Recommended model: gemini3pro (Gemini 3 Pro - best for research tasks)
Run with: /daplug:run-prompt 004 --model gemini3pro
</execution>
