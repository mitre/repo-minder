"""Unit tests for license template detection logic."""

import sys
from pathlib import Path

import pytest

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from standardize_licenses import LicenseStandardizer


@pytest.fixture
def standardizer():
    """Create standardizer instance for testing."""
    return LicenseStandardizer(dry_run=True)


class TestCISDetection:
    """Test CIS baseline/hardening detection."""

    def test_cis_baseline_repos(self, standardizer, sample_repos):
        """Test CIS baseline repo detection."""
        for repo in sample_repos["cis"]:
            assert standardizer.is_cis_baseline_repo(repo), f"{repo} should be CIS"
            template = standardizer.detect_template_type(repo_name=repo)
            assert template == "cis", f"{repo} should use CIS template"

    def test_cis_hardening_repos(self, standardizer):
        """Test CIS hardening repo detection."""
        hardening_repos = [
            "ansible-cis-docker-ce-hardening",
            "ansible-cis-tomcat-hardening",
            "cis-aws-foundations-hardening",
            "chef-cis-docker-ce-hardening",
        ]
        for repo in hardening_repos:
            assert standardizer.is_cis_baseline_repo(repo), f"{repo} should be CIS"
            template = standardizer.detect_template_type(repo_name=repo)
            assert template == "cis", f"{repo} should use CIS template"


class TestDISADetection:
    """Test DISA STIG/SRG detection."""

    def test_disa_stig_baseline_repos(self, standardizer, sample_repos):
        """Test DISA STIG baseline repo detection."""
        for repo in sample_repos["disa"]:
            assert standardizer.is_disa_baseline_repo(repo), f"{repo} should be DISA"
            template = standardizer.detect_template_type(repo_name=repo)
            assert template == "disa", f"{repo} should use DISA template"

    def test_srg_baseline_repos(self, standardizer):
        """Test DISA SRG baseline repo detection."""
        assert standardizer.is_disa_baseline_repo("apache-couchdb-srg-baseline")
        template = standardizer.detect_template_type(repo_name="apache-couchdb-srg-baseline")
        assert template == "disa"


class TestPlainDetection:
    """Test plain template detection."""

    def test_saf_tools_are_plain(self, standardizer):
        """Test SAF tools are detected as plain (not CIS/DISA)."""
        saf_tools = [
            "saf",
            "saf-cli",
            "saf-baseline-ingestion",
            "saf-training-lab-environment",
            "saf-development-lab-environment",
            "saf-lambda-function",
        ]
        for repo in saf_tools:
            assert not standardizer.is_cis_baseline_repo(repo), f"{repo} should NOT be CIS"
            assert not standardizer.is_disa_baseline_repo(repo), f"{repo} should NOT be DISA"
            template = standardizer.detect_template_type(repo_name=repo)
            assert template == "plain", f"{repo} should use plain template"

    def test_utilities_are_plain(self, standardizer, sample_repos):
        """Test utilities and tools are detected as plain."""
        for repo in sample_repos["plain"]:
            template = standardizer.detect_template_type(repo_name=repo)
            assert template == "plain", f"{repo} should use plain template"

    def test_stigready_is_plain(self, standardizer):
        """Test stigready repos are plain (not DISA)."""
        stigready_repos = [
            "nginx-stigready-baseline",
            "ansible-nginx-stigready-hardening",
        ]
        for repo in stigready_repos:
            assert not standardizer.is_disa_baseline_repo(repo), f"{repo} should NOT be DISA"
            template = standardizer.detect_template_type(repo_name=repo)
            assert template == "plain", f"{repo} should use plain template"

    def test_demo_repos_are_plain(self, standardizer):
        """Test demo and sample repos are plain."""
        demo_repos = [
            "demo-aws-baseline",
            "demo-aws-hardening",
            "helloworld-web-baseline",
            "sample-mysql-overlay",
        ]
        for repo in demo_repos:
            template = standardizer.detect_template_type(repo_name=repo)
            assert template == "plain", f"{repo} should use plain template"


class TestLicenseCorrection:
    """Test correction of incorrectly licensed repos."""

    def test_saf_tool_with_cis_license_corrected(self, standardizer):
        """Test that SAF tools with CIS license get corrected to plain."""
        content_with_cis = "CIS Benchmarks. Please visit www.cisecurity.org"
        template = standardizer.detect_template_type(
            content=content_with_cis, repo_name="saf-baseline-ingestion"
        )
        assert template == "plain", "SAF tool with CIS content should be corrected to plain"

    def test_saf_tool_with_disa_license_corrected(self, standardizer):
        """Test that SAF tools with DISA license get corrected to plain."""
        content_with_disa = "DISA STIGs. Please visit https://public.cyber.mil/stigs/"
        template = standardizer.detect_template_type(
            content=content_with_disa, repo_name="saf-training-lab-environment"
        )
        assert (
            template == "plain"
        ), "SAF training env with DISA content should be corrected to plain"

    def test_actual_baseline_keeps_correct_license(self, standardizer):
        """Test that actual baselines keep their correct licenses."""
        # CIS baseline with CIS content stays CIS
        cis_content = "CIS Benchmarks. Please visit www.cisecurity.org"
        template = standardizer.detect_template_type(
            content=cis_content, repo_name="aws-foundations-cis-baseline"
        )
        assert template == "cis", "Real CIS baseline should stay CIS"

        # DISA baseline with DISA content stays DISA
        disa_content = "DISA STIGs. Please visit https://public.cyber.mil/stigs/"
        template = standardizer.detect_template_type(
            content=disa_content, repo_name="redhat-enterprise-linux-7-stig-baseline"
        )
        assert template == "disa", "Real DISA baseline should stay DISA"
