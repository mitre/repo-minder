"""Tests for CLI improvements and bug fixes."""

import sys
from pathlib import Path

from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent))
from standardize_licenses import app

runner = CliRunner(env={"NO_COLOR": "1"})


class TestCtrlCHandling:
    """Test graceful Ctrl-C handling."""

    def test_keyboard_interrupt_exits_gracefully(self, mocker):
        """Ctrl-C should exit gracefully without stack trace."""
        # Mock to raise KeyboardInterrupt
        mocker.patch(
            "standardize_licenses.LicenseStandardizer.get_saf_repos",
            side_effect=KeyboardInterrupt(),
        )

        result = runner.invoke(app, ["--pattern", "*", "--dry-run"])

        # Should exit cleanly (not crash)
        assert result.exit_code in [0, 1, 130]  # 130 is standard for SIGINT
        # Should not show Python traceback
        assert "Traceback" not in result.output


class TestSkipUnchangedFiles:
    """Test skipping files that already match template."""

    def test_skip_if_license_already_correct(self, mocker):
        """Don't update if LICENSE.md already matches our template."""
        # Mock repo with LICENSE.md that already has correct content
        mocker.patch(
            "standardize_licenses.LicenseStandardizer.get_saf_repos",
            return_value=["saf"],
        )
        mocker.patch(
            "standardize_licenses.LicenseStandardizer.get_repo_metadata",
            return_value={"fork": False, "archived": False, "default_branch": "main"},
        )
        mocker.patch(
            "standardize_licenses.LicenseStandardizer.check_license_file",
            return_value=("LICENSE.md", "abc123"),
        )

        # Return content that MATCHES our plain template
        from jinja2 import Environment, FileSystemLoader

        from standardize_licenses import TEMPLATE_VARS

        env = Environment(loader=FileSystemLoader("templates"))
        correct_content = env.get_template("plain.j2").render(**TEMPLATE_VARS)

        mocker.patch(
            "standardize_licenses.LicenseStandardizer.get_license_content",
            return_value=correct_content,
        )

        result = runner.invoke(app, ["--repo", "saf", "--dry-run"])

        # Should say "no changes" or "unchanged" or "skipped"
        assert (
            "unchanged" in result.output.lower()
            or "no changes" in result.output.lower()
            or "skipped" in result.output.lower()
        )

    def test_update_if_license_needs_formatting(self, mocker):
        """Update if LICENSE.md needs formatting cleanup."""
        mocker.patch(
            "standardize_licenses.LicenseStandardizer.get_saf_repos",
            return_value=["saf"],
        )
        mocker.patch(
            "standardize_licenses.LicenseStandardizer.get_repo_metadata",
            return_value={"fork": False, "archived": False, "default_branch": "main"},
        )
        mocker.patch(
            "standardize_licenses.LicenseStandardizer.check_license_file",
            return_value=("LICENSE.md", "abc123"),
        )

        # Return content that DIFFERS from template (needs formatting)
        old_messy_content = "Licensed under Apache 2.0\n\n\nToo many blank lines"
        mocker.patch(
            "standardize_licenses.LicenseStandardizer.get_license_content",
            return_value=old_messy_content,
        )

        result = runner.invoke(app, ["--repo", "saf", "--dry-run"])

        # Should say "update" because content differs
        assert "update" in result.output.lower() or "format" in result.output.lower()

    def test_unchanged_stat_exists_in_code(self):
        """Verify 'unchanged' stat is tracked in stats dict."""
        from standardize_licenses import LicenseStandardizer

        standardizer = LicenseStandardizer(dry_run=True)
        assert "unchanged" in standardizer.stats
        assert standardizer.stats["unchanged"] == 0
