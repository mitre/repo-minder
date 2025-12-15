"""Test template detection through CLI interface (not internal methods)."""

import sys
from pathlib import Path

from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent))
from repo_minder import app

runner = CliRunner(env={"NO_COLOR": "1"})


class TestCISDetectionThroughCLI:
    """Test CIS template detection through public CLI interface."""

    def test_cis_baseline_repo_uses_cis_template(self, mocker):
        """CIS baseline repos should use CIS template (tested via CLI)."""
        mocker.patch(
            "repo_minder.RepoMinder.get_saf_repos",
            return_value=["aws-foundations-cis-baseline"],
        )
        mocker.patch(
            "repo_minder.RepoMinder.get_repo_metadata",
            return_value={"fork": False, "archived": False, "default_branch": "main"},
        )
        mocker.patch(
            "repo_minder.RepoMinder.check_license_file",
            return_value=("LICENSE", "abc"),
        )
        mocker.patch(
            "repo_minder.RepoMinder.get_license_content",
            return_value="Old content",
        )

        result = runner.invoke(app, ["--pattern", "*-cis-baseline", "--dry-run"])

        # Output should show CIS template being used
        assert "cis" in result.output.lower()
        assert result.exit_code == 0

    def test_cis_hardening_repo_uses_cis_template(self, mocker):
        """CIS hardening repos should use CIS template."""
        mocker.patch(
            "repo_minder.RepoMinder.get_saf_repos",
            return_value=["ansible-cis-docker-ce-hardening"],
        )
        mocker.patch(
            "repo_minder.RepoMinder.get_repo_metadata",
            return_value={"fork": False, "archived": False, "default_branch": "main"},
        )
        mocker.patch(
            "repo_minder.RepoMinder.check_license_file",
            return_value=("LICENSE", "abc"),
        )
        mocker.patch(
            "repo_minder.RepoMinder.get_license_content",
            return_value="Old content",
        )

        result = runner.invoke(app, ["--repo", "ansible-cis-docker-ce-hardening", "--dry-run"])

        # Should use CIS template
        assert "cis" in result.output.lower()


class TestDISADetectionThroughCLI:
    """Test DISA template detection through public CLI interface."""

    def test_stig_baseline_uses_disa_template(self, mocker):
        """STIG baseline repos should use DISA template."""
        mocker.patch(
            "repo_minder.RepoMinder.get_saf_repos",
            return_value=["rhel-7-stig-baseline"],
        )
        mocker.patch(
            "repo_minder.RepoMinder.get_repo_metadata",
            return_value={"fork": False, "archived": False, "default_branch": "main"},
        )
        mocker.patch(
            "repo_minder.RepoMinder.check_license_file",
            return_value=("LICENSE", "abc"),
        )
        mocker.patch(
            "repo_minder.RepoMinder.get_license_content",
            return_value="Old content",
        )

        result = runner.invoke(app, ["--repo", "rhel-7-stig-baseline", "--dry-run"])

        # Should use DISA template
        assert "disa" in result.output.lower()


class TestPlainDetectionThroughCLI:
    """Test plain template detection through public CLI interface."""

    def test_saf_tools_use_plain_template(self, mocker):
        """SAF tools should use plain template (not CIS/DISA)."""
        mocker.patch(
            "repo_minder.RepoMinder.get_saf_repos",
            return_value=["saf", "heimdall2", "vulcan"],
        )
        mocker.patch(
            "repo_minder.RepoMinder.get_repo_metadata",
            return_value={"fork": False, "archived": False, "default_branch": "main"},
        )
        mocker.patch(
            "repo_minder.RepoMinder.check_license_file",
            return_value=("LICENSE", "abc"),
        )
        mocker.patch(
            "repo_minder.RepoMinder.get_license_content",
            return_value="Old content",
        )

        result = runner.invoke(app, ["--pattern", "saf*", "--dry-run"])

        # All should be plain template
        assert result.exit_code == 0
        # Template distribution should show PLAIN
        assert "PLAIN" in result.output or "plain" in result.output


class TestLicenseCorrectionThroughCLI:
    """Test that incorrectly licensed repos get fixed."""

    def test_saf_tool_with_wrong_cis_license_corrected(self, mocker):
        """SAF tools with CIS license should be corrected to plain."""
        mocker.patch(
            "repo_minder.RepoMinder.get_saf_repos",
            return_value=["saf-baseline-ingestion"],
        )
        mocker.patch(
            "repo_minder.RepoMinder.get_repo_metadata",
            return_value={"fork": False, "archived": False, "default_branch": "main"},
        )
        mocker.patch(
            "repo_minder.RepoMinder.check_license_file",
            return_value=("LICENSE", "abc"),
        )
        # Has CIS content but is a tool (should be corrected to plain)
        mocker.patch(
            "repo_minder.RepoMinder.get_license_content",
            return_value="CIS Benchmarks. Please visit www.cisecurity.org",
        )

        result = runner.invoke(app, ["--repo", "saf-baseline-ingestion", "--dry-run"])

        # Should correct to plain template
        assert "plain" in result.output.lower()
        assert result.exit_code == 0
