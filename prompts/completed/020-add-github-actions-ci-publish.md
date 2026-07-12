<objective>
Add GitHub Actions CI to cclimits: run the pytest suite on every push/PR, and automate npm publishing on version tags.

This is a long-standing memory-bank "Next Step" ("Add CI/CD for automated npm publishing"). Today nothing runs the 155-test suite on GitHub — outside contributions (like PR #1) get no automated verification, and publishing is a manual multi-step ritual (`npm version patch && npm publish && git push --tags`).
</objective>

<context>
Project: cclimits — npm-distributed CLI (`bin/cclimits.js` Node wrapper) that runs Python (`lib/cclimits.py`). Repo: https://github.com/cruzanstx/cclimits. No `.github/` directory exists yet.

Key facts:
- Tests: `python3 -m pytest tests/` (pure stdlib code under test; pytest is the only test dependency — there is no requirements.txt yet, so install pytest in the workflow, and add a small `requirements-dev.txt` if that keeps things clean).
- Supported Python floor is 3.9 (PR #1 added `from __future__ import annotations` specifically for this) — CI is the only way to keep that promise honest.
- The code has a documented dual HTTP path: `requests` if importable, urllib fallback otherwise. The testing checklist in CLAUDE.md explicitly asks for a no-requests environment test.
- npm publish currently requires 2FA or an automation token with bypass (noted in CLAUDE.md) — the publish workflow should use an `NPM_TOKEN` repo secret (granular automation token).
</context>

<requirements>
1. `./.github/workflows/ci.yml`:
   - Trigger: push to main + pull_request.
   - Matrix: Python 3.9, 3.11, and 3.13 on ubuntu-latest.
   - Two flavors: one job (or matrix dimension) WITH `requests` installed, one WITHOUT, so the urllib fallback path is exercised (verify how the test suite toggles this — see `tests/test_http.py` / `conftest.py` — and make the no-requests job meaningful, not redundant).
   - Also run a trivial wrapper smoke test: `node bin/cclimits.js --help` on the ubuntu default node, to catch wrapper/python-spawn breakage.
2. `./.github/workflows/publish.yml`:
   - Trigger: push of tags matching `v*`.
   - Runs the test suite first; publishes to npm only if green.
   - Uses `NPM_TOKEN` secret with `npm publish --provenance --access public` if provenance is straightforward (requires `id-token: write` permission); otherwise plain `npm publish`.
   - Sanity-guard: fail early if the tag version doesn't match `package.json` version.
3. Add a CI status badge to `README.md`.
4. Document the new release flow briefly in `CLAUDE.md`'s Publishing Workflow section (tag push → CI publishes; NPM_TOKEN secret must exist).
</requirements>

<constraints>
- Do not change any Python source behavior in this task.
- Keep workflows minimal and readable — no third-party actions beyond `actions/checkout`, `actions/setup-python`, `actions/setup-node`.
</constraints>

<verification>
- [ ] `python3 -m pytest tests/ -v` passes locally before and after (no source changes expected).
- [ ] Validate workflow YAML syntax (e.g. `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))"` for both files, or `actionlint` if available).
- [ ] The no-requests CI job genuinely exercises the urllib path (explain in the workflow file how).
- [ ] README badge URL matches the workflow name.

Note: full end-to-end verification requires pushing to GitHub — state clearly in your summary what remains to be verified on the first real push (and that the user must create the `NPM_TOKEN` secret).
</verification>

<output>
Create/modify:
- `./.github/workflows/ci.yml`
- `./.github/workflows/publish.yml`
- `./README.md` — badge
- `./CLAUDE.md` — publishing workflow note
- `./memory-bank/deltas.md`, `./memory-bank/activeContext.md` — mark the CI/CD next-step as done
</output>

<success_criteria>
- CI workflow runs tests across the Python matrix including a urllib-fallback job.
- Tag push publishes to npm after green tests, with version-mismatch guard.
</success_criteria>