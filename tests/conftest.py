"""Pytest configuration and fixtures."""

import pytest
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from standardize_licenses import HAS_JINJA2

@pytest.fixture
def template_dir():
    """Return path to templates directory."""
    return Path(__file__).parent.parent / "templates"

@pytest.fixture
def jinja_env(template_dir):
    """Create Jinja2 environment."""
    if not HAS_JINJA2:
        pytest.skip("Jinja2 not installed")
    from jinja2 import Environment, FileSystemLoader
    return Environment(loader=FileSystemLoader(template_dir))

@pytest.fixture
def cis_template(template_dir):
    """Return CIS template content."""
    return (template_dir / "LICENSE_TEMPLATE_CIS.md").read_text()

@pytest.fixture
def disa_template(template_dir):
    """Return DISA template content."""
    return (template_dir / "LICENSE_TEMPLATE_DISA.md").read_text()

@pytest.fixture
def plain_template(template_dir):
    """Return plain template content."""
    return (template_dir / "LICENSE_TEMPLATE_PLAIN.md").read_text()

@pytest.fixture
def sample_repos():
    """Return sample repo names for testing."""
    return {
        "cis": [
            "aws-foundations-cis-baseline",
            "docker-ce-cis-baseline",
            "ansible-cis-docker-ce-hardening",
        ],
        "disa": [
            "microsoft-windows-server-2019-stig-baseline",
            "redhat-enterprise-linux-7-stig-baseline",
            "apache-couchdb-srg-baseline",
        ],
        "plain": [
            "saf",
            "heimdall2",
            "vulcan",
            "nginx-stigready-baseline",
            "saf-baseline-ingestion",
        ],
    }
