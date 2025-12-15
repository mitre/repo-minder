# Roadmap

**Project:** MITRE License Standardizer
**Current Version:** 1.0.0 (Complete)
**Last Updated:** 2025-12-15

This document outlines planned features and enhancements for the license standardization tool.

---

## v1.0.0 - Current Release ✅

**Status:** Complete and production-ready

### Core Features
- ✅ LICENSE.md standardization across 240+ MITRE SAF repos
- ✅ Three template types (CIS, DISA, Plain) with Jinja2 inheritance
- ✅ Automatic template detection based on repo naming
- ✅ Interactive CLI with Typer + Rich + Questionary
- ✅ Parallel verification (20 workers, 10x faster)
- ✅ 5 safety layers (validation, confirmation, backup, analysis, sanity checks)
- ✅ Friendly error messages and grouped results display
- ✅ 69 passing tests (contract/component levels)
- ✅ Modern Python stack (uv, black, ruff, bandit)

---

## v1.1.0 - Standard Files Support 🎯 **Next Release**

**Priority:** High
**Estimated Effort:** 2-3 weeks
**Target:** Q1 2025

### Standard Repository Files

Add support for checking and standardizing common OSS repository files:

**Core Standard Files:**
- `NOTICE.md` - Third-party attribution and acknowledgments
- `CODE_OF_CONDUCT.md` - Community guidelines (Contributor Covenant)
- `SECURITY.md` - Security policy and vulnerability reporting
- `CONTRIBUTING.md` - Contribution guidelines and developer workflow
- `INSTALLATION.md` - Installation instructions and dependencies
- `CHANGELOG.md` - Version history following [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format

**GitHub-Specific Files:**
- `.github/PULL_REQUEST_TEMPLATE.md` - Pull request template
- `.github/ISSUE_TEMPLATE/bug_report.md` - Bug report template
- `.github/ISSUE_TEMPLATE/feature_request.md` - Feature request template
- `.github/SUPPORT.md` - Support resources and help

### Template System Enhancements

**Template Organization:**
```
templates/
├── LICENSE/
│   ├── base.j2
│   ├── cis.j2
│   ├── disa.j2
│   └── plain.j2
├── NOTICE/
│   ├── cis.j2
│   └── plain.j2
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── CONTRIBUTING.md
├── INSTALLATION.md
└── CHANGELOG.md.j2
```

**Detection Logic:**
- CIS baselines → CIS NOTICE template (third-party acknowledgment)
- DISA baselines → No NOTICE (DoD content)
- Tools/utilities → Plain NOTICE (dependencies only)

### CHANGELOG.md Features

**Template Support:**
- Follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format
- ISO 8601 date format (YYYY-MM-DD)
- Standard sections: Added, Changed, Deprecated, Removed, Fixed, Security
- Unreleased section for work in progress
- Optional: [Common Changelog](https://common-changelog.org/) support (more structured)

**Initial Generation:**
- Create CHANGELOG.md if missing
- Extract version from git tags or pyproject.toml
- Generate initial entry from commit history

### CLI Commands
```bash
# Check all standard files
cis-bench files verify --all

# Check specific file types
cis-bench files verify --type notice,security,contributing

# Add missing standard files
cis-bench files add --file CODE_OF_CONDUCT
cis-bench files add --all  # Add all missing standard files

# Update existing files
cis-bench files update --file SECURITY.md
```

---

## v1.2.0 - Template Preview & Rendering 🎨

**Priority:** High (UX improvement)
**Estimated Effort:** 1 week
**Target:** Q1 2025

### Interactive Template Preview

**Preview Commands:**
```bash
# Preview a template in terminal
cis-bench preview license --type cis

# Preview what will change for a repo
cis-bench preview license --repo aws-foundations-cis-baseline

# Show all available templates
cis-bench templates list

# Show template with variables rendered
cis-bench templates show cis --vars year=2025,case_number=18-3678
```

### Markdown Rendering in Terminal

- Use Rich's Markdown renderer for beautiful terminal display
- Syntax highlighting for code blocks
- Proper formatting of headers, lists, tables
- Diff view: show side-by-side before/after

### Template Comparison

```bash
# Compare two templates
cis-bench templates diff cis disa

# Show what changed between versions
cis-bench diff --repo saf --before HEAD~1 --after HEAD
```

---

## v1.3.0 - Fork Management 🔀

**Priority:** High (we found 7 forks with issues!)
**Estimated Effort:** 1 week
**Target:** Q1 2025

### Fork Detection & Sync

**Issues Discovered:**
- 7 forks have LICENSE files that differ from upstream
- Need automated way to detect and fix fork divergence

**New Features:**
```bash
# Check all forks for LICENSE divergence
cis-bench forks check

# Sync fork LICENSE with upstream
cis-bench forks sync RHEL9-STIG

# Sync all forks
cis-bench forks sync --all

# Show fork divergence report
cis-bench forks report --output json
```

### Fork Safety Enhancements

- Detect when upstream LICENSE changes
- Alert if fork has been modified
- Option to maintain fork-specific LICENSE (with warning)
- Track intentional vs accidental divergence

### Utilities
- `utils/check_fork_licenses.py` - Already created! ✅
- Integrate into main CLI

---

## v2.0.0 - Policy Enforcement & Compliance 📋

**Priority:** Medium
**Estimated Effort:** 3-4 weeks
**Target:** Q2 2025

### Compliance Scoring

**Repository Health Score:**
- 0-100% based on required files present
- Per-file scoring (LICENSE: 25%, SECURITY: 15%, etc.)
- Penalties for outdated content (old copyright years, broken links)

**Policy Profiles:**
```yaml
# policy-profiles/baseline-repo.yml
required_files:
  - LICENSE.md: required
  - NOTICE.md: required  # For CIS/DISA only
  - SECURITY.md: required
  - CODE_OF_CONDUCT.md: recommended
  - CONTRIBUTING.md: optional

scoring:
  LICENSE.md: 30
  SECURITY.md: 20
  CODE_OF_CONDUCT.md: 15
  NOTICE.md: 20
  CONTRIBUTING.md: 10
  CHANGELOG.md: 5
```

### Policy Commands
```bash
# Check compliance against policy
cis-bench policy check --profile baseline-repo

# Generate compliance report
cis-bench policy report --format json > compliance.json

# Enforce policy (add missing files)
cis-bench policy enforce --profile baseline-repo
```

### Required Files Per Repo Type

**Baseline Repositories (InSpec profiles):**
- LICENSE.md (required)
- NOTICE.md (required if CIS/DISA)
- SECURITY.md (required)
- CONTRIBUTING.md (recommended)
- README.md validation (must have Usage section)

**Tool Repositories:**
- LICENSE.md (required)
- SECURITY.md (required)
- CONTRIBUTING.md (required)
- INSTALLATION.md (recommended)
- CODE_OF_CONDUCT.md (recommended)

**Library/SDK Repositories:**
- LICENSE.md (required)
- CHANGELOG.md (required)
- CONTRIBUTING.md (required)
- API documentation (required)

---

## v2.1.0 - Advanced Verification 🔍

**Priority:** Medium
**Estimated Effort:** 2 weeks
**Target:** Q2 2025

### SPDX License Identifiers

- Detect SPDX identifiers in files
- Validate identifier matches actual license
- Add SPDX identifiers to templates
- Support dual licensing (Apache-2.0 AND CC-BY-SA-4.0)

### License Compatibility Checking

```bash
# Check for license conflicts
cis-bench license check-compatibility --repo saf

# Example: MIT + GPL = incompatible
# Example: Apache-2.0 + BSD-3-Clause = compatible
```

### Copyright Year Validation

- Detect outdated copyright years
- Suggest updates: "Copyright © 2020" → "Copyright © 2020-2025"
- Auto-update with `--fix-years` flag

### Link Validation

- Check all URLs in LICENSE/NOTICE files
- Verify links return 200 OK
- Flag broken links (404, DNS errors)
- Suggest archived versions (archive.org)

**Example Report:**
```
⚠️  Link Validation Issues:

  • LICENSE.md:14 - https://old-site.com/terms
    Status: 404 Not Found
    Suggestion: Update to https://new-site.com/terms

  • NOTICE.md:8 - https://cisecurity.org/benchmarks
    Status: 301 Redirect
    New URL: https://www.cisecurity.org/cis-benchmarks
```

---

## v2.2.0 - Organization & Team Support 🏢

**Priority:** Low (MITRE SAF-specific now)
**Estimated Effort:** 2 weeks
**Target:** Q3 2025

### Multi-Organization Support

```bash
# Work with multiple orgs
cis-bench --org mitre --team saf verify
cis-bench --org ansible-lockdown verify
cis-bench --org dev-sec verify
```

### Team-Specific Templates

**Template Inheritance Hierarchy:**
```
org defaults → team overrides → repo overrides
```

**Example:**
```yaml
# .license-standardizer/config.yml
organization:
  name: MITRE
  default_template: plain

teams:
  saf:
    templates:
      baseline: cis  # CIS baselines use CIS template
      tool: plain
  research:
    templates:
      default: plain
```

### Configuration Management

- Per-repo `.license-standardizer.yml` for overrides
- Template variables per repo
- Skip certain files for specific repos
- Custom templates per team

---

## v3.0.0 - Integration & Automation 🤖

**Priority:** Low
**Estimated Effort:** 4-6 weeks
**Target:** Q3-Q4 2025

### GitHub Action

```yaml
# .github/workflows/license-check.yml
name: License Check
on: [push, pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: mitre/license-standardizer-action@v1
        with:
          policy: baseline-repo
          fail-on-missing: true
```

### Pre-commit Hook

```bash
# Install pre-commit hook
cis-bench install-hooks

# Validates LICENSE.md before commit
# Prevents commits if LICENSE outdated
```

### Notifications

**Slack Integration:**
```bash
cis-bench verify --notify slack --webhook $SLACK_WEBHOOK
```

**Teams Integration:**
```bash
cis-bench verify --notify teams --webhook $TEAMS_WEBHOOK
```

**Email Reports:**
```bash
cis-bench verify --notify email --to compliance@mitre.org
```

### Web Dashboard

**Features:**
- Organization-wide compliance view
- Per-repo health scores
- Historical trend charts
- Drill-down to specific issues
- Export reports (PDF, CSV, JSON)

**Tech Stack:**
- Frontend: Vue.js + Nuxt
- Backend: FastAPI
- Database: SQLite/PostgreSQL
- Deploy: Docker + GitHub Pages

---

## Future Enhancements 💡

### Additional Ideas (Backlog)

**Bulk Operations:**
- `--resume-from-failure` - Continue after errors
- Better reporting (JSON/CSV exports)
- Scheduled runs (cron/GitHub Actions)

**Rollback & Recovery:**
- `cis-bench rollback` - Restore from backups/
- `cis-bench history` - Show change history per repo
- Audit log of all operations

**Template Customization:**
- Custom template variables (beyond year/case_number)
- Template versioning (track template changes over time)
- Template linting (validate structure)

**Performance:**
- Caching layer (avoid re-checking unchanged repos)
- Incremental verification (only check recently changed repos)
- Parallel processing for file operations

**Internationalization:**
- Multi-language templates (i18n support)
- Localized error messages
- Region-specific compliance (GDPR, etc.)

---

## Version Numbering

This project follows [Semantic Versioning](https://semver.org/):
- **MAJOR** (v2.0.0) - Breaking changes to CLI or API
- **MINOR** (v1.1.0) - New features, backwards compatible
- **PATCH** (v1.0.1) - Bug fixes, no new features

---

## Contributing to the Roadmap

Have ideas? Found this roadmap useful? We welcome feedback!

**How to suggest features:**
1. Check existing roadmap (this file)
2. Open an issue: `feat: [Feature Name]`
3. Describe the problem it solves
4. Provide example use cases

**Priority Guidelines:**
- High: Fixes major issues or adds critical functionality
- Medium: Improves UX or adds useful features
- Low: Nice-to-have enhancements

---

## Sources & References

- [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) - Changelog format standard
- [Common Changelog](https://common-changelog.org/) - Alternative changelog format
- [Semantic Versioning](https://semver.org/) - Version numbering standard
- [Contributor Covenant](https://www.contributor-covenant.org/) - Code of Conduct template
- [SPDX License List](https://spdx.org/licenses/) - Standard license identifiers
