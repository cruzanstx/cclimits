# AI Coding Providers Research

## Executive Summary

This research evaluates AI coding assistants and providers for potential integration into `cclimits`. The goal is to identify services with subscription-based usage limits or quotas that can be monitored programmatically.

**Top Candidates for Implementation:**
1.  **GitHub Copilot**: High value due to massive user base. While official APIs are limited, the IDE extension APIs or `gh` CLI might expose quota data.
2.  **Cursor**: Rapidly growing popularity. Uses a "request" and "fast/slow" mode model that users actively monitor.
3.  **Windsurf (Codeium)**: Similar to Cursor, with credit-based usage that users need to track.
4.  **Replit AI**: Has a clear "credits" system ($25/mo) that is central to their billing, making it a prime candidate for monitoring.

**Feasibility Note:** Most "AI Editors" (Cursor, Windsurf, JetBrains) do not offer public, documented APIs for user quota checking. Implementation will likely require reverse-engineering internal APIs used by their respective web dashboards or CLIs, similar to how `cclimits` currently handles OpenAI Codex (via ChatGPT backend) and Gemini.

## Detailed Analysis

### 1. Cursor
*   **Plan Structure**:
    *   **Hobby**: Free, 2 weeks Pro trial.
    *   **Pro ($20/mo)**: Unlimited completions, 500 "fast" premium requests/mo, unlimited "slow" requests.
    *   **Business ($40/user/mo)**: Centralized billing, privacy mode.
*   **Usage Limits**:
    *   Pro plan has a hard limit of 500 "fast" GPT-4/Claude-3.5 requests.
    *   After 500, usage drops to "slow" queue (no hard stop, but performance degrades).
*   **Rate Limiting**: "Slow" pool may have concurrency limits.
*   **CLI/API Access**: No official public API for quota.
*   **Credential Storage**: `~/.cursor/` or similar config paths (Electron app).
*   **Quota API**: Likely an internal endpoint used by the settings page in the IDE/Dashboard.
*   **Feasibility**: **Medium**. Requires finding the internal API endpoint used by the Electron app to display "Requests used" in settings.

### 2. Windsurf (Codeium)
*   **Plan Structure**:
    *   **Free**: Limited context, basic models.
    *   **Pro ($15/mo)**: Advanced models (GPT-4), larger context window.
    *   **Teams ($30/user/mo)**: Admin seats, centralized billing.
*   **Usage Limits**:
    *   Free: 25 prompts/mo.
    *   Pro: 500 prompts/mo (approx 2000 "credits").
*   **Rate Limiting**: Rate limits exist for free tier.
*   **CLI/API Access**: `codeium-parse` CLI exists, but primarily for syntax. No quota CLI.
*   **Credential Storage**: `~/.codeium/` json config files.
*   **Quota API**: Internal API used by the IDE status bar/settings.
*   **Feasibility**: **Medium**. Similar to Cursor, requires tracing the IDE's network calls to find the user stats endpoint.

### 3. GitHub Copilot
*   **Plan Structure**:
    *   **Individual ($10/mo)**: For individuals.
    *   **Business ($19/user/mo)**: For orgs.
    *   **Enterprise ($39/user/mo)**: Advanced customization.
*   **Usage Limits**:
    *   Generally "unlimited" for standard completions.
    *   "Rate limited" for abuse prevention.
    *   **Copilot Chat** and advanced models might have tighter, undisclosed throttles.
*   **Rate Limiting**: Dynamic.
*   **CLI/API Access**: `gh copilot` CLI extension exists.
*   **Credential Storage**: Managed by `gh` CLI auth or IDE (secure storage/keychain).
*   **Quota API**: `https://api.github.com/rate_limit` exists but is generic. Specific Copilot quota for individual users is **not exposed** via public APIs or the `gh` CLI.
*   **Feasibility**: **Low**. While `gh` is open source, there is no direct "remaining requests" endpoint for individual users. Enterprise APIs only show aggregate metrics.

### 4. Replit AI
*   **Plan Structure**:
    *   **Starter**: Free.
    *   **Core ($25/mo)**: Includes "Replit Agent" access.
    *   **Teams**: Shared credits.
*   **Usage Limits**:
    *   **Core**: $25/mo of "Cloud Usage" credits (covers AI, storage, bandwidth).
    *   AI Agent checkpoints cost ~$0.25 each.
*   **Rate Limiting**: Rate limits on internal GraphQL API.
*   **CLI/API Access**: `replit` CLI exists (mostly for repl management).
*   **Credential Storage**: Env vars (`REPLIT_TOKEN`).
*   **Quota API**: `https://replit.com/~/cli/account/usage-credits-balance` exists and appears to be designed for CLI usage.
*   **Feasibility**: **High**. The existence of a specific "usage-credits-balance" endpoint makes this a prime candidate.

### 5. Sourcegraph Cody
*   **Plan Structure**:
    *   **Free**: Deprecated/Limited.
    *   **Enterprise**: Custom.
    *   **Amp**: New tool for individuals.
*   **Usage Limits**: Previously 500 completions/mo for free. Enterprise is custom.
*   **Feasibility**: **Low/Medium**. Transition period makes it unstable to target "Free/Pro" tiers right now.

### 6. JetBrains AI Assistant
*   **Plan Structure**:
    *   **Pro**: Add-on subscription.
*   **Usage Limits**:
    *   **AI Credits**: Users get a monthly allowance of credits.
    *   Credits reset monthly.
*   **Credential Storage**: JetBrains account token (IDE stored).
*   **Feasibility**: **Low**. Highly integrated into the proprietary IDE ecosystem. Decrypting/accessing the token outside the IDE might be difficult.

### 7. Amazon Q Developer (CodeWhisperer)
*   **Plan Structure**: Free, Pro ($19/mo).
*   **Usage Limits**:
    *   Free: 50 chat messages/mo.
    *   Pro: Unlimited chat, 4000 lines of code transformation.
*   **Feasibility**: **Medium**. AWS credentials are standard (`~/.aws/credentials`). If usage is exposed via an AWS CLI command (e.g., `aws q-developer get-usage`), it's trivial. If not, it's hard.

### 8. BYOK Tools (Continue, Aider)
*   **Model**: These tools primarily use **Bring Your Own Key** (OpenAI, Anthropic, etc.).
*   **Impact**: `cclimits` **already supports** checking the underlying keys for these (OpenAI, Claude, etc.).
*   **Action**: No specific "Continue" or "Aider" implementation needed. Instead, `cclimits` usage instructions should mention: *"Using Aider/Continue? Run `cclimits` to check your OpenAI/Anthropic quotas directly."*

## Comparison Table

| Provider | Plans | Quota Type | CLI Avail. | Feasibility | Priority |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Replit AI** | Starter, Core | Credits ($) | Yes | High | 1 |
| **GitHub Copilot** | Individual, Biz | Rate Limit / Hidden | `gh` ext | Low | 2 |
| **Cursor** | Hobby, Pro | Requests (Fast/Slow) | No | Medium | 3 |
| **Windsurf** | Free, Pro | Prompt Credits | Parse only | Medium | 4 |
| **Amazon Q** | Free, Pro | Chats/Lines | AWS CLI? | Medium | 5 |
| **JetBrains** | Pro | AI Credits | No | Low | 6 |
| **Sourcegraph** | Ent only | Custom | Yes | Low | 7 |
| **Tabnine** | Pro, Ent | Hidden/Custom | Docker | Low | 8 |

## Recommendations

1.  **Prioritize Replit AI**:
    *   The discovered endpoint `https://replit.com/~/cli/account/usage-credits-balance` is promising.
    *   **Next Step**: Implement a prototype using a Replit token (or `replit` CLI login state) to fetch this balance.

2.  **Defer GitHub Copilot**:
    *   Without a public API for individual quota, there's no reliable way to support this.
    *   Monitor `gh` CLI updates for future API exposure.

3.  **Hold on Cursor/Windsurf**:
    *   Requires complex reverse engineering. Revisit if public APIs appear.

4.  **Documentation Update (Completed)**:
    *   `README.md` has been updated to explicitly support BYOK tools (Aider, Continue).

## Implementation Roadmap (Updated)

*   [x] **Phase 1 (Discovery)**: Replit endpoint identified (`usage-credits-balance`). Cursor/Copilot deemed low feasibility without hacking.
*   [x] **Phase 2 (GitHub)**: Confirmed no public individual quota API exists.
*   [x] **Phase 3 (Docs)**: Updated `README.md` to target BYOK tool users.
*   [ ] **Phase 4 (Dev)**: Implement Replit support in `cclimits.py` (requires Replit account for testing).
