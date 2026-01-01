<objective>
Create comprehensive unit tests for the cclimits Python CLI tool.

The cclimits tool checks quota/usage for AI coding assistants (Claude Code, OpenAI Codex, Google Gemini CLI, Z.AI). It's a ~1000 line Python script that needs regression protection for its core functionality.
</objective>

<context>
@lib/cclimits.py - Main Python script (the only code file)
@CLAUDE.md - Project conventions and patterns

Key architecture:
- Dual HTTP client (requests library when available, urllib fallback)
- Platform-specific credential discovery (macOS Keychain, config files, env vars)
- API calls to 4 different services
- Output formatting for terminal display
</context>

<requirements>
Create a test suite using pytest with the following coverage:

**1. Pure Functions (no mocking needed)**
- `format_reset_time()` - ISO timestamp to human-readable
- `get_status_icon()` - percentage to emoji icon

**2. HTTP Client Functions (mock network calls)**
- `http_get()` - test with both requests and urllib paths
- `http_post()` - test with both requests and urllib paths
- Test success, error, and timeout scenarios

**3. Credential Discovery Functions (mock filesystem/subprocess)**
- `get_claude_credentials()` - test macOS Keychain, config files, env vars
- `get_openai_credentials()` - test auth.json and env vars
- `get_gemini_credentials()` - test oauth_creds.json, token refresh, env vars
- `get_zai_credentials()` - test various env var names

**4. Usage Functions (mock both credentials and HTTP)**
- `get_claude_usage()` - test success, expired token, no credentials
- `get_codex_usage()` - test OAuth flow, API key fallback
- `get_gemini_usage()` - test OAuth flow, token refresh, API key fallback
- `get_zai_usage()` - test quota endpoint parsing

**5. Output Functions (capture stdout)**
- `print_section()` - test various data combinations
- `print_oneline()` - test compact output format
- Test error cases and edge cases

**6. CLI Integration (mock all dependencies)**
- Test `--json` flag produces valid JSON
- Test `--oneline` flag with 5h and 7d windows
- Test single-tool flags (`--claude`, `--codex`, etc.)
</requirements>

<implementation>
Use pytest with these patterns:

```python
# Recommended test structure
tests/
├── conftest.py          # Shared fixtures
├── test_utils.py        # Pure function tests
├── test_http.py         # HTTP client tests
├── test_credentials.py  # Credential discovery tests
├── test_usage.py        # API usage tests
├── test_output.py       # Output formatting tests
└── test_cli.py          # CLI integration tests
```

Key patterns:
- Use `@pytest.fixture` for common test data
- Use `unittest.mock.patch` for mocking
- Use `pytest.mark.parametrize` for testing multiple inputs
- Use `capsys` for capturing stdout
- Test both `HAS_REQUESTS = True` and `HAS_REQUESTS = False` paths

WHY mock external dependencies:
- Tests should be fast and reliable (no network)
- Tests should work offline
- Tests should not depend on actual credentials
- Tests should be reproducible
</implementation>

<output>
Create the following files:
- `./tests/conftest.py` - Shared fixtures and mock data
- `./tests/test_utils.py` - Tests for pure utility functions
- `./tests/test_http.py` - Tests for HTTP client functions
- `./tests/test_credentials.py` - Tests for credential discovery
- `./tests/test_usage.py` - Tests for API usage functions
- `./tests/test_output.py` - Tests for output formatting
- `./tests/test_cli.py` - Tests for CLI entry point
</output>

<verification>
**Run the test suite:**
```bash
cd /storage/projects/docker/cclimits
pip install pytest pytest-mock --quiet
python -m pytest tests/ -v --tb=short
```

Before declaring complete, verify:
- [ ] All test files are created and syntactically valid
- [ ] Tests can be imported without errors
- [ ] `pytest tests/ -v` shows tests discovered
- [ ] At least 80% of tests pass (some may need adjustment)
- [ ] Coverage of all major functions is addressed

**Test count targets:**
- `test_utils.py`: 8+ tests
- `test_http.py`: 10+ tests
- `test_credentials.py`: 15+ tests
- `test_usage.py`: 12+ tests
- `test_output.py`: 8+ tests
- `test_cli.py`: 6+ tests
</verification>

<success_criteria>
- All test files created with valid pytest syntax
- Tests run without import errors
- Test coverage addresses all major functions
- Mocking strategy properly isolates external dependencies
- Tests are readable and maintainable
</success_criteria>
