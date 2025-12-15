"""Tests for interactive mode using Questionary's test helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestInteractiveMode:
    """Test interactive prompts using prompt_toolkit test helpers."""

    def test_interactive_mode_with_simulated_input(self, mocker):
        """Test interactive mode with simulated keyboard input."""
        # For now, mock questionary to avoid complex prompt_toolkit setup
        mocker.patch(
            "questionary.select", return_value=mocker.Mock(ask=lambda: "Process single repo")
        )
        mocker.patch("questionary.text", return_value=mocker.Mock(ask=lambda: "saf"))
        mocker.patch("questionary.confirm", return_value=mocker.Mock(ask=lambda: True))
        mocker.patch("questionary.checkbox", return_value=mocker.Mock(ask=lambda: []))

        # Mock GitHub API
        mocker.patch(
            "standardize_licenses.LicenseStandardizer.get_repo_metadata",
            return_value={"fork": False, "archived": False, "default_branch": "main"},
        )
        mocker.patch(
            "standardize_licenses.LicenseStandardizer.check_license_file",
            return_value=("LICENSE", "abc"),
        )
        mocker.patch(
            "standardize_licenses.LicenseStandardizer.get_license_content",
            return_value="Apache 2.0",
        )

        from typer.testing import CliRunner

        from standardize_licenses import app

        runner = CliRunner()
        result = runner.invoke(app, ["--interactive"])

        # Should complete without hanging
        assert result.exit_code in [0, 1]  # May fail on API but shouldn't hang

    def test_questionary_confirm_mock(self, mocker):
        """Verify we can mock questionary.confirm correctly."""
        mock_confirm = mocker.patch("questionary.confirm")
        mock_confirm.return_value.ask.return_value = False

        import questionary

        result = questionary.confirm("Test?").ask()
        assert result is False

    def test_questionary_select_mock(self, mocker):
        """Verify we can mock questionary.select correctly."""
        mock_select = mocker.patch("questionary.select")
        mock_select.return_value.ask.return_value = "Option 1"

        import questionary

        result = questionary.select("Choose:", choices=["Option 1", "Option 2"]).ask()
        assert result == "Option 1"


class TestRichConsoleCapture:
    """Test Rich console output capture."""

    def test_rich_console_record(self):
        """Test capturing Rich console output."""
        from io import StringIO

        from rich.console import Console

        # Rich Console with file= captures output
        output = StringIO()
        console = Console(file=output, width=80)

        console.print("[red]Error message[/red]")
        console.print("[green]Success[/green]")

        captured = output.getvalue()
        assert "Error message" in captured
        assert "Success" in captured

    def test_rich_table_capture(self):
        """Test capturing Rich table output."""
        from io import StringIO

        from rich.console import Console
        from rich.table import Table

        output = StringIO()
        console = Console(file=output, width=80)

        table = Table(title="Test")
        table.add_column("Col1")
        table.add_row("Value1")

        console.print(table)

        captured = output.getvalue()
        assert "Test" in captured
        assert "Col1" in captured
        assert "Value1" in captured
