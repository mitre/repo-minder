# MITRE Repo Minder

Repository file standardization and compliance tool for MITRE open-source projects.

## Features

- **Auto-detection**: Identifies CIS, DISA, or plain license templates
- **Batch processing**: Updates 240+ repos efficiently
- **Fork-aware**: Automatically skips forked repositories
- **Rate limiting**: Built-in delays to respect GitHub API limits
- **Resume capability**: Continue from where you left off if interrupted
- **Pattern matching**: Process specific repo subsets
- **Dry-run mode**: Preview changes before applying
- **Verification**: Double-checks all changes after completion

## Quick Start

```bash
# Install the tool
pip install mitre-repo-minder

# Or use with uv (development)
uv run python standardize_licenses.py --repo saf --dry-run

# Test on single repo (dry-run)
repo-minder --repo saf --dry-run

# Process all SAF repos, skip CIS baselines
repo-minder --skip cis

# Process only STIG baselines
repo-minder --pattern '*-stig-baseline'

# Interactive mode
repo-minder --interactive
```

## Usage

```
repo-minder [OPTIONS]

Options:
  --repo REPO                  Process single repo (test mode)
  --pattern PATTERN            Process repos matching glob pattern
  --skip {cis,disa,plain}      Skip specific template types (repeatable)
  --skip-archived              Skip archived repositories
  --resume-from REPO           Resume from specific repo
  --delay SECONDS              Delay between repos (default: 0.5)
  --dry-run                    Preview changes without applying
  --verify-only                Only verify LICENSE.md exists
  --repo-filter TEXT           Filter repos by substring
  --output-format {txt,json,csv}  Dry-run output format (default: txt)
  -o, --output FILE            Custom output filename for dry-run plan
```

## License Templates

### CIS Template
Used for CIS Benchmark baseline and hardening repositories.

**Pattern:** `*-cis-baseline`, `*-cis-hardening`

**Third-party section:**
```
CIS Benchmarks. Please visit www.cisecurity.org for full terms of use.
```

### DISA Template
Used for DISA STIG and SRG baseline repositories.

**Pattern:** `*-stig-baseline`, `*-srg-baseline`

**Third-party section:**
```
DISA STIGs. Please visit https://cyber.mil/stigs/downloads for full
terms of use.
```

### Plain Template
Used for all other repositories (tools, utilities, libraries).

**Pattern:** Everything else

**Third-party section:** None

## Detection Logic

The script uses intelligent pattern matching to determine the correct
license template:

1. **Check if fork** → Skip (preserve upstream license)
2. **Check if archived** → Skip if `--skip-archived`
3. **Detect template type:**
   - CIS: Has "cis" + ("baseline" OR "hardening"), not a tool/demo/sample
   - DISA: Has "-stig-baseline" OR "-srg-baseline", not stigready
   - Plain: Everything else
4. **Apply template** → Create or update LICENSE.md
5. **Clean up** → Delete old LICENSE file if renamed
6. **Verify** → Confirm LICENSE.md exists

## Examples

### Update all SAF repos (skip CIS baselines already updated)
```bash
uv run python standardize_licenses.py --skip cis
```

### Process only STIG baselines with verification
```bash
uv run python standardize_licenses.py --pattern '*-stig-baseline' --dry-run --output-format json
# Review dry_run_plan.json
uv run python standardize_licenses.py --pattern '*-stig-baseline'
```

### Fix a specific repo
```bash
uv run python standardize_licenses.py --repo heimdall2
```

### Resume after network failure
```bash
uv run python standardize_licenses.py --resume-from nginx-baseline
```

## How It Works

### Step 1: Get Repository List
```bash
gh api orgs/mitre/teams/saf/repos --paginate
```

### Step 2: For Each Repo
1. Check for LICENSE or LICENSE.md
2. Read content if exists
3. Detect correct template (CIS/DISA/Plain)
4. Update to cleaned, 80-char formatted LICENSE.md
5. Delete old LICENSE if renamed
6. Add delay (rate limiting)

### Step 3: Verification
1. Check all repos have LICENSE.md
2. Report any missing or failed updates

## Statistics

Example output:
```
======================================================================
SUMMARY
======================================================================
Total repos:      243
Updated:          89
Created:          12
Renamed:          47
Skipped:          95
  - Forks:        23
  - Archived:     15
Failed:           0
Verified:         148
```

## Requirements

- Python 3.8+
- uv (https://docs.astral.sh/uv/)
- GitHub CLI (`gh`) authenticated
- Access to MITRE org and SAF team

## Installation

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup
git clone https://github.com/mitre/license-standardizer
cd license-standardizer

# Install dependencies (creates .venv and installs packages)
uv sync --dev

# Run the tool
uv run python standardize_licenses.py --help
```

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Run linting
uv run black --check .
uv run ruff check .

# Run security scan
uv run bandit -r standardize_licenses.py -ll

# Add new dependency
uv add <package>

# Add dev dependency
uv add --dev <package>
```

## Contributing

This tool was created to standardize LICENSE files across MITRE's 240+
Security Automation Framework repositories. Improvements welcome!

## License

Copyright © 2025 The MITRE Corporation.

Licensed under the Apache License 2.0.

Approved for Public Release; Distribution Unlimited. Case Number 18-3678.

## Authors

- MITRE SAF Team <saf@mitre.org>

## Acknowledgments

Developed to maintain consistency across MITRE's open-source security
automation tools including SAF CLI, Heimdall, Vulcan, and 240+ InSpec
compliance baselines.

## Technology

- **uv**: Modern Python package manager (10-100x faster than pip)
- **Jinja2**: Template engine with inheritance (base + child templates)
- **GitHub CLI**: API access for repository operations
- **pytest**: 43 comprehensive tests (unit + functional + integration)
