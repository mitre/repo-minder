"""Functional tests for end-to-end license standardization."""

# Import after ensuring parent dir in path
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from repo_minder import RepoMinder


@pytest.fixture
def mock_gh_api():
    """Mock gh api calls."""
    with patch("subprocess.run") as mock_run:
        yield mock_run


class TestRepoMinderFunctional:
    """Functional tests for RepoMinder class."""

    def test_fork_detection_skips_repo(self, mock_gh_api):
        """Test that forked repos are skipped."""
        # Mock get_repo_metadata to return fork=true
        mock_gh_api.return_value = Mock(
            returncode=0, stdout='{"fork": true, "archived": false, "default_branch": "main"}'
        )

        standardizer = RepoMinder(dry_run=True)
        result = standardizer.process_repo("some-fork")

        assert result["status"] == "skipped"
        assert result["action"] == "fork"
        assert standardizer.stats["forks"] == 1

    def test_archived_repo_skipped_when_flag_set(self, mock_gh_api):
        """Test that archived repos are skipped when --skip-archived."""
        # Mock get_repo_metadata to return archived=true
        mock_gh_api.return_value = Mock(
            returncode=0, stdout='{"fork": false, "archived": true, "default_branch": "main"}'
        )

        standardizer = RepoMinder(dry_run=True, skip_archived=True)
        result = standardizer.process_repo("archived-repo")

        assert result["status"] == "skipped"
        assert result["action"] == "archived"
        assert standardizer.stats["archived"] == 1

    def test_archived_repo_processed_without_flag(self, mock_gh_api):
        """Test that archived repos are processed when flag not set."""
        # First call: metadata (archived)
        # Second call: check LICENSE file (exists)
        # Third call: get content
        mock_gh_api.side_effect = [
            Mock(
                returncode=0, stdout='{"fork": false, "archived": true, "default_branch": "main"}'
            ),
            Mock(returncode=0, stdout='{"sha": "abc123", "content": "base64content"}'),
            Mock(returncode=0, stdout='"TGljZW5zZSBjb250ZW50"'),  # "License content" in base64
        ]

        standardizer = RepoMinder(dry_run=True, skip_archived=False)
        result = standardizer.process_repo("archived-repo")

        assert result["status"] == "success"

    def test_skip_template_type(self, mock_gh_api):
        """Test that --skip cis skips CIS repos."""
        # Mock metadata, license check, and content
        mock_gh_api.side_effect = [
            Mock(
                returncode=0, stdout='{"fork": false, "archived": false, "default_branch": "main"}'
            ),
            Mock(returncode=0, stdout='{"sha": "abc123", "content": "base64"}'),
            Mock(returncode=0, stdout='"Q0lTIEJlbmNobWFya3M="'),  # "CIS Benchmarks" in base64
        ]

        standardizer = RepoMinder(dry_run=True, skip_templates=["cis"])
        result = standardizer.process_repo("aws-foundations-cis-baseline")

        assert result["status"] == "skipped"
        assert result["action"] == "skip_cis"

    def test_creates_license_for_repo_without_one(self, mock_gh_api):
        """Test that LICENSE.md is created for repos without license."""
        # Mock metadata and no license file
        # Mock: metadata + all 7 license variants return 404
        mock_gh_api.side_effect = [
            Mock(
                returncode=0, stdout='{"fork": false, "archived": false, "default_branch": "main"}'
            ),
            *[Mock(returncode=1) for _ in range(7)],  # All license variants don't exist
        ]

        standardizer = RepoMinder(dry_run=True)
        result = standardizer.process_repo("nginx-stigready-baseline")

        assert result["status"] == "success"
        assert result["action"] == "created"
        assert result["template"] == "plain"
        assert standardizer.stats["created"] == 1

    def test_renames_license_to_license_md(self, mock_gh_api):
        """Test that LICENSE is renamed to LICENSE.md."""
        # Mock: metadata, no LICENSE.md, has LICENSE, get content
        import base64

        content = base64.b64encode(b"Licensed under Apache 2.0").decode()

        mock_gh_api.side_effect = [
            Mock(
                returncode=0, stdout='{"fork": false, "archived": false, "default_branch": "main"}'
            ),
            Mock(returncode=1),  # No LICENSE.md
            Mock(
                returncode=0, stdout=f'{{"sha": "abc123", "content": "{content}"}}'
            ),  # Has LICENSE
            Mock(returncode=0, stdout=f'"{content}"'),  # Get content
        ]

        standardizer = RepoMinder(dry_run=True)
        result = standardizer.process_repo("saf")

        assert result["status"] == "success"
        assert result["action"] == "renamed"
        assert standardizer.stats["renamed"] == 1

    def test_updates_existing_license_md(self, mock_gh_api):
        """Test that existing LICENSE.md is updated with cleaned format."""
        import base64

        content = base64.b64encode(b"Licensed under Apache 2.0").decode()

        mock_gh_api.side_effect = [
            Mock(
                returncode=0, stdout='{"fork": false, "archived": false, "default_branch": "main"}'
            ),
            Mock(
                returncode=0, stdout=f'{{"sha": "abc123", "content": "{content}"}}'
            ),  # Has LICENSE.md
            Mock(returncode=0, stdout=f'"{content}"'),  # Get content
        ]

        standardizer = RepoMinder(dry_run=True)
        result = standardizer.process_repo("heimdall2")

        assert result["status"] == "success"
        assert result["action"] == "updated"
        assert standardizer.stats["updated"] == 1


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_handles_api_errors_gracefully(self, mock_gh_api):
        """Test that API errors are caught and reported."""
        mock_gh_api.side_effect = Exception("API rate limit exceeded")

        standardizer = RepoMinder(dry_run=True)
        result = standardizer.process_repo("test-repo")

        assert result["status"] == "failed"
        assert "API rate limit" in result["error"]
        assert standardizer.stats["failed"] == 1

    def test_dry_run_creates_plan_file(self, tmp_path, monkeypatch):
        """Test that dry-run mode creates plan file."""
        monkeypatch.chdir(tmp_path)

        standardizer = RepoMinder(dry_run=True)
        standardizer.results = [
            {
                "repo": "saf",
                "status": "success",
                "action": "renamed",
                "template": "plain",
                "error": None,
            },
            {
                "repo": "heimdall2",
                "status": "success",
                "action": "updated",
                "template": "plain",
                "error": None,
            },
        ]
        standardizer.stats["total"] = 2
        standardizer.stats["renamed"] = 1
        standardizer.stats["updated"] = 1
        standardizer.save_dry_run_plan(output_format="txt")

        plan_file = tmp_path / "dry_run_plan.txt"
        assert plan_file.exists()
        content = plan_file.read_text()
        assert "RENAMED" in content or "renamed" in content
        assert "saf" in content
        assert "heimdall2" in content

    def test_statistics_tracking(self):
        """Test that statistics are tracked correctly."""
        standardizer = RepoMinder(dry_run=True)

        assert standardizer.stats["total"] == 0
        assert standardizer.stats["updated"] == 0
        assert standardizer.stats["created"] == 0
        assert standardizer.stats["renamed"] == 0
        assert standardizer.stats["skipped"] == 0
        assert standardizer.stats["failed"] == 0
        assert standardizer.stats["forks"] == 0
        assert standardizer.stats["archived"] == 0
