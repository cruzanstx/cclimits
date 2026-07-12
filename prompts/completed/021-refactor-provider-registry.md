<objective>
Refactor the per-provider duplication in `lib/cclimits.py` into a small data-driven provider registry, so adding a provider (Replit is next in the pipeline — see `prompts/providers/013-replit-integration.md`) touches ONE table instead of four scattered code sites.

This is a pure refactor: behavior and output must be byte-identical.
</objective>

<context>
Project: cclimits — single-file Python CLI (~2000 lines). Read `CLAUDE.md` and `memory-bank/systemPatterns.md` first.

Current duplication (the pain this removes):
1. `print_oneline()` has eight near-identical ~25-line provider blocks. Six of them follow two repeated shapes:
   - "percent-based, dual-window" (Claude, Codex, Z.AI, Synthetic): extract 5h/7d percents, `both` renders `X%/Y%` colored by max, single window renders `X% (5h)`.
   - "balance-based" (OpenRouter, Kimi): identical threshold ladder (`<=0` ❌ / `<1` 🔴 / `<5` ⚠️ / else ✅) copy-pasted twice, differing only in currency symbol.
   Gemini (tiered) and Antigravity (model summary) are genuinely bespoke and may stay as custom renderers.
2. `main()` dispatch: eight hand-written `if` lines mapping flag → fetch function, plus the tuple of provider names for `requested`, plus eight `print_section(...)` lines with display titles.
3. `argparse`: eight copy-pasted `--<provider>` flags.

Thoroughly analyze the existing structure before writing code — the goal is LESS total code and one obvious extension point, not an abstraction layer for its own sake. Consider multiple registry shapes (list of dataclass-like dicts vs. per-provider renderer functions registered in a table) and pick the simplest that eliminates the duplication.
</context>

<requirements>
1. Introduce a module-level `PROVIDERS` registry (ordered) carrying at minimum: key (`claude`), display title (`Claude Code`), fetch function, whether check_all gates on a credential probe (openrouter/kimi/antigravity/synthetic do; the first four don't), and a oneline renderer (shared percent/balance renderers parameterized per provider, or a custom function for Gemini/Antigravity).
2. Drive ALL of these from the registry: argparse flag creation, the `requested` list, the fetch dispatch in `main()` (preserving cache-hit skip semantics exactly as they are when you start), the detailed `print_section` loop, and `print_oneline`.
3. Extract the two shared oneline renderers (dual-window percent, balance-with-thresholds) so Z.AI's quirks (integer percents, `request_quota` second value, `(5h)` suffix fallback) and Synthetic's (`weekly_credits.percent_used`) are handled via small per-provider extractor lambdas/params — NOT by re-forking the renderer.
4. The failure branch (`fail_icon` handling for no-creds 🔑 / expired ⏰ / error ❌) must be applied uniformly in one place, not per-provider.
5. Output must be byte-identical for every mode: this is the hard success criterion. The 155-test suite pins much of this; do not modify existing test assertions — if a test fails, the refactor is wrong.
6. Tests patch symbols like `cclimits.get_claude_usage` at module level — the registry must reference these late (e.g. store the name or look up via the module) OR the task must verify patching still intercepts. Do not silently break test patching.
</requirements>

<verification>
```bash
cd /storage/projects/docker/cclimits && python3 -m pytest tests/ -v
```

- [ ] Entire existing suite passes with ZERO assertion changes.
- [ ] Byte-identical output check: before refactoring, capture `python3 lib/cclimits.py --json`, `--oneline`, `--oneline both`, `--oneline 7d --noemoji`, and detailed output to files (live creds in this environment make this meaningful); after refactoring, diff against them (allow only timestamp lines to differ).
- [ ] Line count of `lib/cclimits.py` decreases meaningfully (expect roughly 150–300 lines saved).
- [ ] Demonstrate the extension point in the PR/commit message: what a new provider now requires (one registry entry + fetch function).
</verification>

<output>
Modify:
- `./lib/cclimits.py`
- `./memory-bank/deltas.md` and `./memory-bank/systemPatterns.md` — document the registry pattern
</output>

<success_criteria>
- All existing tests pass unmodified; captured outputs diff clean.
- Adding a hypothetical provider requires one registry entry, one fetch function, and (if bespoke) one renderer — no edits to main()/print_oneline internals.
</success_criteria>