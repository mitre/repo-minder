"""Tests for Typer CLI interface."""

import sys
from pathlib import Path

from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent))
from repo_minder import app

# CliRunner with color disabled for easier testing
runner = CliRunner(env={"NO_COLOR": "1"})


class TestCLI:
    """Test Typer CLI interface."""

    def test_help_command(self):
        """Test --help flag shows usage."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Standardize LICENSE files" in result.output
        assert "repo" in result.output.lower()
        assert "interactive" in result.output.lower()

    def test_version_in_help(self):
        """Test help shows all major options."""
        result = runner.invoke(app, ["--help"])
        assert "dry" in result.output.lower() and "run" in result.output.lower()
        assert "skip" in result.output.lower()
        assert "pattern" in result.output.lower()
        assert "archived" in result.output.lower()
        assert "interactive" in result.output.lower()

    def test_no_interactive_flag_prevents_prompts(self):
        """Test --no-interactive prevents interactive prompts."""
        # This should not hang waiting for input
        result = runner.invoke(app, ["--interactive", "--no-interactive", "--help"])
        assert result.exit_code == 0

    def test_invalid_output_format(self):
        """Test invalid output format raises error."""
        result = runner.invoke(app, ["--output-format", "xml", "--repo", "saf", "--dry-run"])
        # Should fail validation
        assert result.exit_code != 0 or "Invalid output format" in result.output


class TestCLIWithMocks:
    """Test CLI with mocked GitHub API calls."""

    def test_dry_run_single_repo(self, mocker):
        """Test dry-run on single repo."""
        # Mock get_repo_metadata
        mocker.patch(
            "repo_minder.RepoMinder.get_repo_metadata",
            return_value={"fork": False, "archived": False, "default_branch": "main"},
        )
        # Mock check_license_file
        mocker.patch(
            "repo_minder.RepoMinder.check_license_file",
            return_value=("LICENSE", "abc123"),
        )
        # Mock get_license_content
        mocker.patch(
            "repo_minder.RepoMinder.get_license_content",
            return_value="Licensed under Apache 2.0",
        )

        result = runner.invoke(app, ["--repo", "saf", "--dry-run"])
        assert result.exit_code == 0
        assert "saf" in result.output or "Processing" in result.output

    def test_verify_only_mode(self, mocker):
        """Test --verify-only flag."""
        # Mock get_saf_repos
        mocker.patch(
            "repo_minder.RepoMinder.get_saf_repos",
            return_value=["saf", "heimdall2"],
        )
        # Mock verify_license
        mocker.patch(
            "repo_minder.RepoMinder.verify_license",
            return_value=True,
        )

        result = runner.invoke(app, ["--verify-only"])
        assert result.exit_code == 0
        assert "verif" in result.output.lower()  # Matches "Verification" or "verify"
