# Test Organization

This test suite follows best practices by testing at the appropriate levels.

## Test Levels

### 1. Contract/Interface Tests (PRIMARY)

**What:** Test behavior through public interfaces (CLI)
**Why:** Tests what users experience, not how it's implemented
**Location:**
- `test_cli.py` - CLI interface contract
- `test_template_detection_contract.py` - Detection through CLI
- `test_safety.py` - Safety layer behaviors
- `test_ux_and_skip_logic.py` - UX features

**Example:**
```python
def test_cis_baseline_detected(self, mocker):
    result = runner.invoke(app, ["--repo", "aws-cis-baseline", "--dry-run"])
    assert "cis" in result.output.lower()  # Test behavior, not implementation
```

### 2. Component Tests (SECONDARY)

**What:** Test specific components in isolation
**Why:** Fast tests for specific functionality
**Location:**
- `test_functional.py` - LicenseStandardizer class behaviors (mocked GitHub API)
- `test_templates.py` - Template structure validation
- `test_jinja2.py` - Jinja2 rendering

**Example:**
```python
def test_fork_detection_skips_repo(self, mocker):
    # Test component behavior with mocked dependencies
```

### 3. Implementation Tests

**REMOVED** - All implementation tests removed. Test through public interfaces only.

## Test Best Practices

### ✅ DO:
- Test through public CLI interface (CliRunner)
- Mock external dependencies (GitHub API, file I/O)
- Test contracts (does it produce correct LICENSE?)
- Test behavior (does it skip unchanged files?)

### ❌ DON'T:
- Test private methods directly (use CLI instead)
- Test implementation details
- Over-mock (makes tests brittle)
- Test what libraries already test

## Test Categories

**CLI Tests** (test_cli.py)
- Help text
- Flag validation
- Error handling

**Contract Tests** (test_template_detection_contract.py)
- CIS repos → CIS template
- DISA repos → DISA template
- Tools → plain template

**Safety Tests** (test_safety.py)
- Command validation
- Bulk confirmation
- Backup system
- Template distribution
- Sanity warnings

**UX Tests** (test_ux_and_skip_logic.py)
- Ctrl-C handling
- Skip unchanged files
- Better output formatting

**Template Tests** (test_templates.py, test_jinja2.py)
- Template structure (has required sections)
- Jinja2 equivalence (matches static templates)
- 80-char width

**Interactive Tests** (test_interactive.py)
- Questionary mocking examples
- Rich console capture

**Functional Tests** (test_functional.py)
- Component behaviors with mocked I/O

## Running Tests

```bash
# All tests
uv run pytest tests/ -v

# Only contract tests (recommended)
uv run pytest tests/test_*_contract.py tests/test_cli.py tests/test_safety.py -v

# Only implementation tests (fast, for debugging)
uv run pytest tests/test_detection_implementation.py -v

# With coverage
uv run pytest tests/ --cov=. --cov-report=term
```

## Test Count

- **Contract/Interface tests:** 39 (CLI, safety, UX, detection)
- **Component tests:** 30 (functional, templates, Jinja2)
- **Total:** 69 tests (all at proper levels)
