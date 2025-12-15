#!/usr/bin/env python3
"""Standardize LICENSE files across MITRE SAF team repositories.

This script:
1. Gets all repos from MITRE SAF team via gh cli
2. Checks each repo for LICENSE or LICENSE.md
3. Determines correct template (CIS/DISA/Plain)
4. Updates to cleaned, standardized LICENSE.md
5. Verifies all changes
6. Handles forks, archived repos, rate limits, and errors

Usage:
    uv run python standardize_licenses.py --dry-run
    uv run python standardize_licenses.py --skip cis
    uv run python standardize_licenses.py --verify-only
    uv run python standardize_licenses.py --repo saf
    uv run python standardize_licenses.py --pattern '*-stig-baseline'
    uv run python standardize_licenses.py --skip-archived --resume-from nginx-baseline
    uv run python standardize_licenses.py --interactive
"""

import json
import logging
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import questionary
import typer
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from typing_extensions import Annotated

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False


# Configuration with Pydantic Settings
class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env file."""

    organization: str = Field(
        default="mitre", description="GitHub organization name (e.g., 'mitre', 'ansible-lockdown')"
    )
    team: str = Field(default="saf", description="GitHub team name within the organization")
    log_level: str = Field(
        default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )

    model_config = SettingsConfigDict(
        env_prefix="REPO_MINDER_",  # Reads REPO_MINDER_ORG, REPO_MINDER_TEAM, etc.
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Initialize settings
settings = Settings()

# Setup logging with Rich handler
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, markup=True)],
)
logger = logging.getLogger("repo_minder")

# Rich console for user-facing output (tables, panels, progress bars)
console = Console()
app = typer.Typer(
    name="repo-minder",
    help="Repository file standardization and compliance tool",
    add_completion=False,
)

# Template paths
SCRIPT_DIR = Path(__file__).parent
TEMPLATES_DIR = SCRIPT_DIR / "templates"

# Template variables
TEMPLATE_VARS = {
    "year": datetime.now().year,
    "case_number": "18-3678",
    "organization": "The MITRE Corporation",
}


class RepoMinder:
    """Repository file standardization and compliance tool."""

    def __init__(
        self,
        dry_run=False,
        skip_templates=None,
        skip_archived=False,
        delay=0.5,
        organization=None,
        team=None,
    ):
        # Use provided values or fall back to global settings
        self.organization = organization or settings.organization
        self.team = team or settings.team
        self.dry_run = dry_run
        self.skip_templates = skip_templates or []
        self.skip_archived = skip_archived
        self.delay = delay  # Delay between repos (rate limiting)
        self.quiet_mode = False  # Suppress per-repo messages in bulk operations
        self.stats = {
            "total": 0,
            "updated": 0,
            "created": 0,
            "renamed": 0,
            "unchanged": 0,
            "skipped": 0,
            "failed": 0,
            "verified": 0,
            "forks": 0,
            "archived": 0,
        }
        self.results = []
        self.dry_run_plan = []  # Store dry-run actions

        # Load templates using Jinja2
        if not HAS_JINJA2:
            raise ImportError("Jinja2 is required. Install with: pip install jinja2")

        env = Environment(
            loader=FileSystemLoader(TEMPLATES_DIR),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Render each template type
        self.templates = {
            "cis": env.get_template("cis.j2").render(**TEMPLATE_VARS),
            "disa": env.get_template("disa.j2").render(**TEMPLATE_VARS),
            "plain": env.get_template("plain.j2").render(**TEMPLATE_VARS),
        }

    def get_saf_repos(self) -> List[str]:
        """Get list of all team repos via gh cli."""
        logger.info(f"Fetching {self.organization}/{self.team} team repositories...")
        result = subprocess.run(
            [
                "gh",
                "api",
                f"orgs/{self.organization}/teams/{self.team}/repos",
                "--paginate",
                "--jq",
                ".[].name",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise ValueError(
                f"Failed to fetch {self.organization}/{self.team} team repositories. "
                "Make sure you're authenticated with 'gh auth login'"
            )

        repos = [line.strip() for line in result.stdout.strip().split("\n")]
        logger.info(f"Found {len(repos)} repos in {self.organization}/{self.team} team")
        return repos

    def check_license_file(self, repo_name: str) -> Tuple[Optional[str], Optional[str]]:
        """Check which LICENSE file exists.

        Returns:
            (file_path, sha) if exists, (None, None) if not
        """
        # Try common LICENSE file variants
        license_variants = [
            "LICENSE.md",
            "LICENSE",
            "LICENSE.txt",
            "LICENCE.md",
            "LICENCE",
            "license.md",
            "license",
        ]

        for filename in license_variants:
            result = subprocess.run(
                [
                    "gh",
                    "api",
                    f"repos/{self.organization}/{repo_name}/contents/{filename}",
                    "--jq",
                    '{"sha": .sha, "content": .content}',
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return (filename, data["sha"])

        return (None, None)

    def get_license_content(self, repo_name: str, file_path: str) -> str:
        """Get current LICENSE file content."""
        result = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{self.organization}/{repo_name}/contents/{file_path}",
                "--jq",
                ".content",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise ValueError(f"Failed to read {file_path} from repository")

        # Decode base64
        import base64

        content_b64 = result.stdout.strip().strip('"')
        return base64.b64decode(content_b64).decode("utf-8")

    def is_cis_baseline_repo(self, repo_name: str) -> bool:
        """Check if repo is an actual CIS baseline/hardening implementation."""
        name_lower = repo_name.lower()

        # Exclude SAF tools, ingestion utilities, demos, general tools
        excludes = ["saf-", "tool", "ingestion", "demo-", "helloworld-", "sample-"]
        if any(ex in name_lower for ex in excludes):
            return False

        # Must have "cis" AND ("baseline" OR "hardening")
        # Patterns: *-cis-baseline, cis-*-baseline, *-cis-hardening, cis-*-hardening
        has_cis = "cis" in name_lower
        has_baseline_or_hardening = "baseline" in name_lower or "hardening" in name_lower

        return has_cis and has_baseline_or_hardening

    def is_disa_baseline_repo(self, repo_name: str) -> bool:
        """Check if repo is an actual DISA STIG/SRG baseline implementation."""
        name_lower = repo_name.lower()
        # Exclude stigready, SAF tools, training, demos, samples
        excludes = ["stigready", "demo-", "helloworld-", "sample-"]
        if any(ex in name_lower for ex in excludes):
            return False
        if "saf-" in name_lower and "-baseline" not in name_lower:
            return False
        if "training" in name_lower and "-baseline" not in name_lower:
            return False

        disa_patterns = [
            "-stig-baseline",
            "-srg-baseline",
        ]
        return any(pattern in name_lower for pattern in disa_patterns)

    def detect_template_type(self, content: str = None, repo_name: str = None) -> str:
        """Detect which template to use based on content and repo name.

        Strategy:
        1. Check repo name first (most reliable)
        2. If existing LICENSE has wrong third-party section, fix it
        3. Default to plain for tools/utilities

        Returns:
            'cis', 'disa', or 'plain'
        """
        # Detect from repo name (most reliable)
        if repo_name:
            if self.is_cis_baseline_repo(repo_name):
                return "cis"
            elif self.is_disa_baseline_repo(repo_name):
                return "disa"

        # If we have content, verify it matches repo name
        # (This catches incorrectly licensed repos)
        if content and repo_name:
            has_cis_content = "CIS Benchmarks" in content
            has_disa_content = "DISA STIGs" in content or "DISA IASE" in content

            # If LICENSE claims CIS/DISA but repo is a tool → Fix to plain
            if (
                (has_cis_content or has_disa_content)
                and not self.is_cis_baseline_repo(repo_name)
                and not self.is_disa_baseline_repo(repo_name)
            ):
                return "plain"  # Fix incorrect LICENSE

        return "plain"

    def get_repo_metadata(self, repo_name: str) -> Dict:
        """Get repo metadata (fork status, archived status, default branch)."""
        result = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{self.organization}/{repo_name}",
                "--jq",
                '{"fork": .fork, "archived": .archived, "default_branch": .default_branch}',
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            # Friendly error message instead of raw exception
            if "Not Found" in result.stderr or "Could not resolve" in result.stderr:
                raise ValueError(
                    f"Repository '{self.organization}/{repo_name}' not found or you don't have access to it"
                )
            else:
                raise ValueError(f"Failed to get repository metadata: {result.stderr.strip()}")

        return json.loads(result.stdout)

    def get_default_branch(self, repo_name: str) -> str:
        """Get default branch for repo."""
        result = subprocess.run(
            ["gh", "api", f"repos/{self.organization}/{repo_name}", "--jq", ".default_branch"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise ValueError("Failed to get default branch for repository")

        return result.stdout.strip().strip('"')

    def create_license(self, repo_name: str, template_type: str, branch: str):
        """Create new LICENSE.md file."""
        template = self.templates[template_type]

        if self.dry_run:
            if not self.quiet_mode:
                console.print(
                    f"  [yellow][DRY RUN] Would create LICENSE.md using {template_type} template[/yellow]"
                )
            return True

        # Base64 encode content for GitHub API
        import base64

        content_b64 = base64.b64encode(template.encode("utf-8")).decode("utf-8")

        cmd = [
            "gh",
            "api",
            f"repos/{self.organization}/{repo_name}/contents/LICENSE.md",
            "-X",
            "PUT",
            "-F",
            "message=docs: add LICENSE.md [skip ci]",
            "-F",
            f"content={content_b64}",
            "-F",
            f"branch={branch}",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        return result.returncode == 0

    def update_license(
        self, repo_name: str, template_type: str, old_file: str, sha: str, branch: str
    ):
        """Update or create LICENSE.md file."""
        template = self.templates[template_type]

        if self.dry_run:
            if not self.quiet_mode:
                console.print(
                    f"  [yellow][DRY RUN] Would update {old_file} → LICENSE.md using {template_type} template[/yellow]"
                )
            return True

        # Base64 encode content for GitHub API
        import base64

        content_b64 = base64.b64encode(template.encode("utf-8")).decode("utf-8")

        if old_file == "LICENSE.md":
            # Update existing LICENSE.md
            cmd = [
                "gh",
                "api",
                f"repos/{self.organization}/{repo_name}/contents/LICENSE.md",
                "-X",
                "PUT",
                "-F",
                "message=docs: clean up LICENSE.md formatting [skip ci]",
                "-F",
                f"content={content_b64}",
                "-F",
                f"sha={sha}",
                "-F",
                f"branch={branch}",
            ]
        else:
            # Create new LICENSE.md
            cmd = [
                "gh",
                "api",
                f"repos/{self.organization}/{repo_name}/contents/LICENSE.md",
                "-X",
                "PUT",
                "-F",
                "message=docs: add LICENSE.md [skip ci]",
                "-F",
                f"content={content_b64}",
                "-F",
                f"branch={branch}",
            ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            console.print(f"  [red]❌ Failed to create LICENSE.md: {result.stderr}[/red]")
            return False

        # Delete old LICENSE if it existed
        if old_file == "LICENSE":
            self.delete_old_license(repo_name, branch)

        return True

    def delete_old_license(self, repo_name: str, branch: str):
        """Delete old LICENSE file (no .md extension)."""
        if self.dry_run:
            if not self.quiet_mode:
                console.print("  [yellow][DRY RUN] Would delete old LICENSE file[/yellow]")
            return

        # Get current SHA of LICENSE file
        result = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{self.organization}/{repo_name}/contents/LICENSE",
                "--jq",
                ".sha",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return  # File doesn't exist

        sha = result.stdout.strip().strip('"')
        subprocess.run(
            [
                "gh",
                "api",
                f"repos/{self.organization}/{repo_name}/contents/LICENSE",
                "-X",
                "DELETE",
                "-F",
                "message=docs: rename LICENSE to LICENSE.md [skip ci]",
                "-F",
                f"sha={sha}",
                "-F",
                f"branch={branch}",
            ],
            capture_output=True,
        )

    def verify_license(self, repo_name: str) -> bool:
        """Verify repo has any LICENSE file variant."""
        file_path, _ = self.check_license_file(repo_name)
        # Accept any LICENSE file (will be standardized to LICENSE.md)
        return file_path is not None

    def process_repo(self, repo_name: str) -> Dict:
        """Process a single repository.

        Returns:
            dict with result info
        """
        result = {
            "repo": repo_name,
            "status": "pending",
            "template": None,
            "action": None,
            "error": None,
        }

        try:
            # Get repo metadata (fork, archived, branch)
            metadata = self.get_repo_metadata(repo_name)

            # Skip forks - don't modify their licenses
            if metadata["fork"]:
                result["status"] = "skipped"
                result["action"] = "fork"
                self.stats["forks"] += 1
                self.stats["skipped"] += 1
                return result

            # Skip archived repos if requested
            if metadata["archived"] and self.skip_archived:
                result["status"] = "skipped"
                result["action"] = "archived"
                self.stats["archived"] += 1
                self.stats["skipped"] += 1
                return result

            # Check what LICENSE file exists
            file_path, sha = self.check_license_file(repo_name)
            branch = metadata["default_branch"]

            if file_path is None:
                # No license - detect template from repo name and create
                template_type = self.detect_template_type(content=None, repo_name=repo_name)
                result["template"] = template_type
                success = self.create_license(repo_name, template_type, branch)
                if success:
                    result["status"] = "success"
                    result["action"] = "created"
                    self.stats["created"] += 1
                else:
                    result["status"] = "failed"
                    result["error"] = "Failed to create LICENSE.md"
                    self.stats["failed"] += 1
                return result

            # Get current content and detect template type
            content = self.get_license_content(repo_name, file_path)
            template_type = self.detect_template_type(content=content, repo_name=repo_name)
            result["template"] = template_type

            # Check if should skip this template type
            if template_type in self.skip_templates:
                result["status"] = "skipped"
                result["action"] = f"skip_{template_type}"
                self.stats["skipped"] += 1
                return result

            # Check if LICENSE already matches our template (skip if unchanged)
            expected_template = self.templates[template_type]
            if content.strip() == expected_template.strip():
                result["status"] = "success"  # Success, no action needed
                result["action"] = "unchanged"
                self.stats["unchanged"] = self.stats.get("unchanged", 0) + 1
                return result

            # Layer 3: Backup original LICENSE if enabled (only if updating)
            if hasattr(self, "backup_dir") and self.backup_dir:
                backup_file = self.backup_dir / f"{repo_name}.{file_path}"
                backup_file.write_text(content)
                console.print(f"  [dim]📦 Backed up to {backup_file.name}[/dim]")

            # Update the license
            success = self.update_license(repo_name, template_type, file_path, sha, branch)

            if success:
                if file_path == "LICENSE":
                    result["action"] = "renamed"
                    self.stats["renamed"] += 1
                elif file_path == "LICENSE.md":
                    result["action"] = "updated"
                    self.stats["updated"] += 1
                result["status"] = "success"
            else:
                result["status"] = "failed"
                self.stats["failed"] += 1

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            self.stats["failed"] += 1

        return result

    def analyze_repo_status(self, repo_name: str) -> Dict:
        """Analyze a single repo's LICENSE status (for parallel execution)."""
        try:
            file_path, sha = self.check_license_file(repo_name)

            if not file_path:
                # No LICENSE file
                template_type = self.detect_template_type(content=None, repo_name=repo_name)
                return {
                    "repo": repo_name,
                    "status": "missing",
                    "template": template_type,
                    "detail": f"No LICENSE found, will create ({template_type.upper()})",
                }

            # Has a LICENSE file - check if it matches template
            content = self.get_license_content(repo_name, file_path)
            template_type = self.detect_template_type(content=content, repo_name=repo_name)
            expected = self.templates[template_type]

            if content.strip() == expected.strip():
                # Perfect match
                return {
                    "repo": repo_name,
                    "status": "correct",
                    "template": template_type,
                    "file": file_path,
                    "detail": f"Has {file_path} ({template_type.upper()})",
                }
            else:
                # Needs update
                if file_path != "LICENSE.md":
                    reason = f"Has {file_path}, needs rename + update ({template_type.upper()})"
                else:
                    reason = f"Has LICENSE.md, needs formatting cleanup ({template_type.upper()})"

                return {
                    "repo": repo_name,
                    "status": "needs_update",
                    "template": template_type,
                    "file": file_path,
                    "detail": reason,
                }

        except Exception as e:
            return {
                "repo": repo_name,
                "status": "error",
                "detail": str(e),
            }

    def verify_all(self, repos: List[str]):
        """Verify all repos have LICENSE files (parallel execution)."""
        console.print("\n")
        console.print(Panel.fit("[bold cyan]Verification[/bold cyan]", border_style="cyan"))
        console.print()

        results = []

        # Parallel verification with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Verifying LICENSE files...", total=len(repos))

            # Use ThreadPoolExecutor for parallel checking (20 workers for speed!)
            with ThreadPoolExecutor(max_workers=20) as executor:
                # Submit all repos for checking
                future_to_repo = {
                    executor.submit(self.analyze_repo_status, repo): repo for repo in repos
                }

                # Collect results as they complete
                for future in as_completed(future_to_repo):
                    result = future.result()
                    results.append(result)
                    progress.update(
                        task, description=f"[{len(results)}/{len(repos)}] Checked {result['repo']}"
                    )
                    progress.advance(task)

        console.print()

        # Group results
        correct = [r for r in results if r["status"] == "correct"]
        needs_update = [r for r in results if r["status"] == "needs_update"]
        missing = [r for r in results if r["status"] == "missing"]
        errors = [r for r in results if r["status"] == "error"]

        self.stats["verified"] = len(correct)

        # Show grouped results
        if correct:
            console.print(f"[green]✅ CORRECT ({len(correct)} repos)[/green]")
            for r in correct[:5]:  # Show first 5
                console.print(f"  [dim]• {r['repo']}: {r['file']} ({r['template'].upper()})[/dim]")
            if len(correct) > 5:
                console.print(f"  [dim]... and {len(correct) - 5} more[/dim]")
            console.print()

        if needs_update:
            table = Table(title=f"⚠️  NEEDS UPDATE ({len(needs_update)} repos)")
            table.add_column("Repository", style="cyan")
            table.add_column("Issue", style="yellow")

            for r in needs_update[:20]:
                table.add_row(r["repo"], r["detail"])

            console.print(table)
            if len(needs_update) > 20:
                console.print(f"\n[dim]... and {len(needs_update) - 20} more[/dim]")
            console.print()

        if missing:
            table = Table(title=f"❌ MISSING LICENSE ({len(missing)} repos)")
            table.add_column("Repository", style="cyan")
            table.add_column("Will Create", style="yellow")

            for r in missing[:20]:
                table.add_row(r["repo"], r["template"].upper())

            console.print(table)
            if len(missing) > 20:
                console.print(f"\n[dim]... and {len(missing) - 20} more[/dim]")
            console.print()
            console.print("[cyan]💡 Tip: Run without --verify-only to create LICENSE files[/cyan]")

        if errors:
            console.print(f"\n[red]❌ ERRORS ({len(errors)} repos)[/red]")
            for r in errors:
                console.print(f"  - {r['repo']}: {r['detail']}")

        # Summary
        console.print()
        summary = Panel.fit(
            f"[bold]Verification Complete[/bold]\n\n"
            f"[green]✅ Correct:[/green] {len(correct)}\n"
            f"[yellow]⚠️  Needs Update:[/yellow] {len(needs_update)}\n"
            f"[red]❌ Missing:[/red] {len(missing)}",
            title="Summary",
            border_style="cyan",
        )
        console.print(summary)

    def save_dry_run_plan(self, output_format="txt", output_file=None):
        """Save dry-run plan to file for review.

        Args:
            output_format: Output format ('txt', 'json', 'csv')
            output_file: Custom output filename (default: dry_run_plan.{format})
        """
        if not self.dry_run or not self.results:
            return

        # Text format
        if output_format == "txt":
            plan_file = Path(output_file) if output_file else Path("dry_run_plan.txt")
            with open(plan_file, "w") as f:
                f.write("DRY RUN PLAN - Review before executing\n")
                f.write("=" * 70 + "\n\n")

                # Group by action type
                by_action = {}
                for r in self.results:
                    if r["status"] == "success":
                        action = r["action"]
                        if action not in by_action:
                            by_action[action] = []
                        by_action[action].append(f"{r['repo']} ({r['template']})")

                for action, repos in by_action.items():
                    f.write(f"\n{action.upper()}:\n")
                    for repo in repos:
                        f.write(f"  - {repo}\n")

                f.write("\n" + "=" * 70 + "\n")
                f.write(f"Total repos:      {self.stats['total']}\n")
                f.write(f"Will update:      {self.stats['updated']}\n")
                f.write(f"Will create:      {self.stats['created']}\n")
                f.write(f"Will rename:      {self.stats['renamed']}\n")
                f.write(f"Will skip:        {self.stats['skipped']}\n")

            console.print()
            console.print(
                Panel.fit(
                    f"[green]📝 Dry-run plan saved[/green]\n\n"
                    f"[cyan]File:[/cyan] {plan_file.absolute()}\n"
                    f"[cyan]Format:[/cyan] {output_format.upper()}\n"
                    f"[cyan]Actions:[/cyan] {len([r for r in self.results if r['status'] == 'success'])} planned",
                    title="Dry-Run Report",
                    border_style="green",
                )
            )

        # JSON format
        elif output_format == "json":
            import json as json_lib

            plan_file = Path(output_file) if output_file else Path("dry_run_plan.json")
            output_data = {
                "summary": self.stats,
                "results": self.results,
            }
            with open(plan_file, "w") as f:
                json_lib.dump(output_data, f, indent=2)

            console.print()
            console.print(
                Panel.fit(
                    f"[green]📝 Dry-run plan saved[/green]\n\n"
                    f"[cyan]File:[/cyan] {plan_file.absolute()}\n"
                    f"[cyan]Format:[/cyan] JSON\n"
                    f"[cyan]Repos:[/cyan] {len(self.results)} analyzed",
                    title="Dry-Run Report",
                    border_style="green",
                )
            )

        # CSV format
        elif output_format == "csv":
            import csv

            plan_file = Path(output_file) if output_file else Path("dry_run_plan.csv")
            with open(plan_file, "w", newline="") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["repo", "status", "action", "template", "error"]
                )
                writer.writeheader()
                writer.writerows(self.results)

            console.print()
            console.print(
                Panel.fit(
                    f"[green]📝 Dry-run plan saved[/green]\n\n"
                    f"[cyan]File:[/cyan] {plan_file.absolute()}\n"
                    f"[cyan]Format:[/cyan] CSV\n"
                    f"[cyan]Rows:[/cyan] {len(self.results)} repos",
                    title="Dry-Run Report",
                    border_style="green",
                )
            )

    def show_grouped_results(self):
        """Show clean grouped summary of what happened/will happen."""
        if not self.results:
            return

        # Group results by action
        unchanged = [r for r in self.results if r["action"] == "unchanged"]
        will_update = [r for r in self.results if r["action"] == "updated"]
        will_rename = [r for r in self.results if r["action"] == "renamed"]
        will_create = [r for r in self.results if r["action"] == "created"]
        skipped_forks = [r for r in self.results if r["action"] == "fork"]
        skipped_archived = [r for r in self.results if r["action"] == "archived"]
        skipped_other = [
            r
            for r in self.results
            if r["status"] == "skipped"
            and r["action"] not in ["unchanged", "fork", "archived"]
            and r["action"]
            and r["action"].startswith("skip_")
        ]
        failed = [r for r in self.results if r["status"] == "failed"]

        # Build summary lines
        lines = []

        if unchanged:
            lines.append(f"[green]✅ Already correct:[/green] {len(unchanged)} repos")

        if will_update:
            action_word = "Will update" if self.dry_run else "Updated"
            lines.append(
                f"[yellow]📝 {action_word}:[/yellow] {len(will_update)} repos (formatting cleanup)"
            )

        if will_rename:
            action_word = "Will rename" if self.dry_run else "Renamed"
            lines.append(
                f"[yellow]🔄 {action_word}:[/yellow] {len(will_rename)} repos (LICENSE → LICENSE.md)"
            )

        if will_create:
            action_word = "Will create" if self.dry_run else "Created"
            lines.append(f"[cyan]➕ {action_word}:[/cyan] {len(will_create)} repos")

        # Combine skipped categories
        total_skipped = len(skipped_forks) + len(skipped_archived) + len(skipped_other)
        if total_skipped > 0:
            skip_details = []
            if skipped_forks:
                skip_details.append(f"{len(skipped_forks)} forks")
            if skipped_archived:
                skip_details.append(f"{len(skipped_archived)} archived")
            if skipped_other:
                # Extract template types from skip_X actions
                template_types = set()
                for r in skipped_other:
                    if r["action"].startswith("skip_"):
                        template_types.add(r["action"].replace("skip_", ""))
                if template_types:
                    skip_details.append(f"{len(skipped_other)} {'/'.join(template_types).upper()}")

            lines.append(f"[dim]⏭️  Skipped:[/dim] {', '.join(skip_details)}")

        if failed:
            lines.append(f"[red]❌ Failed:[/red] {len(failed)} repos")

        # Show panel only if we have something to show
        if lines:
            console.print(
                Panel.fit(
                    "\n".join(lines),
                    title="Results" if self.dry_run else "Changes Applied",
                    border_style="cyan",
                )
            )

    def print_summary(self):
        """Print summary of operations."""
        table = Table(title="Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", style="green", justify="right")

        table.add_row("Total repos", str(self.stats["total"]))
        table.add_row("Updated", str(self.stats["updated"]))
        table.add_row("Created", str(self.stats["created"]))
        table.add_row("Renamed", str(self.stats["renamed"]))
        if self.stats.get("unchanged", 0) > 0:
            table.add_row("Unchanged", str(self.stats["unchanged"]), style="dim")
        table.add_row("Skipped", str(self.stats["skipped"]))
        if self.stats["forks"] > 0:
            table.add_row("  - Forks", str(self.stats["forks"]))
        if self.stats["archived"] > 0:
            table.add_row("  - Archived", str(self.stats["archived"]))
        table.add_row(
            "Failed",
            str(self.stats["failed"]),
            style="red" if self.stats["failed"] > 0 else "green",
        )
        if self.stats["verified"] > 0:
            table.add_row("Verified", str(self.stats["verified"]))

        console.print("\n")
        console.print(table)

        if self.stats["failed"] > 0:
            console.print("\n[red]Failed repos:[/red]")
            for r in self.results:
                if r["status"] == "failed":
                    console.print(f"  - {r['repo']}: {r.get('error', 'unknown error')}")

    def run(
        self,
        repo_filter: Optional[str] = None,
        pattern: Optional[str] = None,
        resume_from: Optional[str] = None,
        force: bool = False,
        backup_enabled: bool = True,
    ):
        """Run standardization on all repos."""
        # Get repos
        repos = self.get_saf_repos()

        if repo_filter:
            repos = [r for r in repos if repo_filter.lower() in r.lower()]
            console.print(f"[cyan]Filtered to {len(repos)} repos matching '{repo_filter}'[/cyan]\n")

        if pattern:
            import fnmatch

            repos = [r for r in repos if fnmatch.fnmatch(r, pattern)]
            console.print(
                f"[cyan]Filtered to {len(repos)} repos matching pattern '{pattern}'[/cyan]\n"
            )

        # Resume from specific repo
        if resume_from:
            try:
                start_index = repos.index(resume_from)
                repos = repos[start_index:]
                console.print(
                    f"[cyan]Resuming from '{resume_from}' ({len(repos)} repos remaining)[/cyan]\n"
                )
            except ValueError:
                console.print(f"[red]❌ Resume repo '{resume_from}' not found in list[/red]")
                return 1

        self.stats["total"] = len(repos)

        # Layer 2: Bulk confirmation - require confirmation for large batches
        if len(repos) > 10 and not self.dry_run and not force:
            console.print(f"\n[yellow]⚠️  About to update {len(repos)} repositories[/yellow]")
            confirmed = questionary.confirm(
                f"This will modify {len(repos)} repos. Continue?",
                default=False,
            ).ask()

            if not confirmed:
                console.print("[yellow]Cancelled by user[/yellow]")
                return 0

        # Layer 3: Create backup directory if enabled
        backup_dir = None
        if backup_enabled and not self.dry_run:
            backup_dir = Path("backups") / datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir.mkdir(parents=True, exist_ok=True)
            console.print(f"[cyan]📦 Backups will be saved to: {backup_dir}[/cyan]\n")
            self.backup_dir = backup_dir

        # Enable quiet mode for bulk operations (>1 repo)
        if len(repos) > 1:
            self.quiet_mode = True

        # Process each repo with progress bar (with Ctrl-C handling)
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    f"Processing {len(repos)} repositories...", total=len(repos)
                )

                for i, repo in enumerate(repos, 1):
                    progress.update(task, description=f"[{i}/{len(repos)}] {repo}")
                    result = self.process_repo(repo)
                    self.results.append(result)

                    # Only show errors and important changes (not every repo)
                    if result["status"] == "failed":
                        console.print(f"  [red]❌ {repo}: {result['error']}[/red]")
                    elif result["action"] != "unchanged" and result["status"] == "success":
                        if self.dry_run:
                            self.dry_run_plan.append(
                                f"{repo}: {result['action']} ({result['template']})"
                            )

                    progress.advance(task)

                    # Rate limiting delay
                    if i < len(repos) and not self.dry_run:
                        time.sleep(self.delay)

        except KeyboardInterrupt:
            console.print("\n\n[yellow]⚠️  Interrupted by user (Ctrl-C)[/yellow]")
            console.print(
                f"[cyan]Processed {len(self.results)}/{len(repos)} repos before interruption[/cyan]"
            )
            # Continue to show results for what was processed
            pass

        # Show clean grouped results
        console.print()
        self.show_grouped_results()

        # Layer 4: Template distribution (only for large batches)
        if len(repos) > 20:
            self.show_template_distribution()

        # Layer 5: Sanity checks (only for large batches)
        if len(repos) > 20:
            self.show_sanity_warnings()

        # Save dry-run plan (will be set from args in main())
        if self.dry_run:
            self.save_dry_run_plan(
                output_format=getattr(self, "output_format", "txt"),
                output_file=getattr(self, "output_file", None),
            )

        # Print summary
        self.print_summary()

        # Verify if not dry run
        if not self.dry_run:
            self.verify_all(repos)

        return 0 if self.stats["failed"] == 0 else 1

    def show_template_distribution(self):
        """Layer 4: Show template type distribution."""
        # Count by template type
        template_counts = {"cis": 0, "disa": 0, "plain": 0}
        for r in self.results:
            if r.get("template") and r["status"] == "success":
                template_counts[r["template"]] += 1

        if sum(template_counts.values()) == 0:
            return

        table = Table(title="Template Distribution")
        table.add_column("Template Type", style="cyan")
        table.add_column("Count", style="green", justify="right")
        table.add_column("Percentage", style="yellow", justify="right")

        total = sum(template_counts.values())
        for tmpl, count in template_counts.items():
            if count > 0:
                pct = (count / total) * 100
                table.add_row(tmpl.upper(), str(count), f"{pct:.1f}%")

        console.print("\n")
        console.print(table)

    def show_sanity_warnings(self):
        """Layer 5: Show sanity check warnings."""
        warnings = []

        total_processed = len([r for r in self.results if r["status"] != "skipped"])
        if total_processed == 0:
            return

        # Check 1: All same template type (suspicious)
        template_types = {r.get("template") for r in self.results if r.get("template")}
        if len(template_types) == 1 and total_processed > 5:
            warnings.append(
                f"⚠️  All {total_processed} repos detected as same template type ({list(template_types)[0].upper()})"
            )

        # Check 2: Too many creates (>50%)
        creates = self.stats.get("created", 0)
        if creates > 0 and total_processed > 5:
            create_pct = (creates / total_processed) * 100
            if create_pct > 50:
                warnings.append(
                    f"⚠️  {create_pct:.0f}% of repos need LICENSE created (expected <50%)"
                )

        # Check 3: Too many forks (>30%)
        forks = self.stats.get("forks", 0)
        total_checked = self.stats.get("total", 0)
        if forks > 0 and total_checked > 10:
            fork_pct = (forks / total_checked) * 100
            if fork_pct > 30:
                warnings.append(
                    f"⚠️  {fork_pct:.0f}% of repos are forks (might have selected wrong team)"
                )

        if warnings:
            console.print("\n[yellow bold]⚠️  SANITY CHECK WARNINGS:[/yellow bold]")
            for warning in warnings:
                console.print(f"[yellow]{warning}[/yellow]")


@app.command()
def standardize(
    org: Annotated[
        Optional[str],
        typer.Option("--org", help="GitHub organization (default: from env or 'mitre')"),
    ] = None,
    team: Annotated[
        Optional[str], typer.Option("--team", help="GitHub team (default: from env or 'saf')")
    ] = None,
    repo: Annotated[Optional[str], typer.Option(help="Process single repo (test mode)")] = None,
    pattern: Annotated[
        Optional[str], typer.Option(help="Glob pattern (e.g., '*-stig-baseline')")
    ] = None,
    skip: Annotated[Optional[List[str]], typer.Option(help="Skip template types")] = None,
    skip_archived: Annotated[bool, typer.Option(help="Skip archived repositories")] = False,
    resume_from: Annotated[Optional[str], typer.Option(help="Resume from specific repo")] = None,
    delay: Annotated[float, typer.Option(help="Delay between repos (seconds)")] = 0.5,
    dry_run: Annotated[bool, typer.Option(help="Preview changes without applying")] = False,
    verify_only: Annotated[bool, typer.Option(help="Only verify LICENSE.md exists")] = False,
    repo_filter: Annotated[Optional[str], typer.Option(help="Filter repos by substring")] = None,
    output_format: Annotated[str, typer.Option(help="Dry-run output format")] = "txt",
    output: Annotated[Optional[str], typer.Option("-o", help="Custom output filename")] = None,
    interactive: Annotated[
        bool, typer.Option("--interactive", "-i", help="Interactive mode with prompts")
    ] = False,
    no_interactive: Annotated[
        bool, typer.Option("--no-interactive", help="Disable interactive prompts (for CI)")
    ] = False,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation prompts")] = False,
    backup: Annotated[
        bool, typer.Option("--backup", help="Backup original LICENSE files before update")
    ] = True,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable colored output")] = False,
):
    """Standardize LICENSE files in MITRE SAF repositories."""
    # Set NO_COLOR if requested
    if no_color:
        import os

        os.environ["NO_COLOR"] = "1"

    # Layer 1: Command Validation - Must specify target
    if not (repo or pattern or repo_filter or verify_only or interactive):
        console.print("[red]❌ No target specified![/red]")
        console.print(
            "Use one of: --repo, --pattern, --repo-filter, --verify-only, or --interactive"
        )
        console.print("Run with --help for usage information")
        raise typer.Exit(1)
    # Interactive mode (only if not explicitly disabled)
    if interactive and not no_interactive:
        console.print("\n")
        console.print(
            Panel.fit(
                "[bold cyan]MITRE License Standardizer[/bold cyan]\n" "[dim]Interactive Mode[/dim]",
                border_style="cyan",
            )
        )
        console.print()

        try:
            # Step 1: Choose action
            action = questionary.select(
                "What would you like to do?",
                choices=[
                    "Analyze single repo (check compliance)",
                    "Verify all repos (find missing licenses)",
                    "Update repos by pattern",
                    "Update all SAF repos",
                ],
            ).ask()

            if not action:
                raise KeyboardInterrupt

            # Step 2: Get target based on action
            if action == "Analyze single repo (check compliance)":
                repo = questionary.text("Enter repo name:").ask()
                if repo is None:
                    raise KeyboardInterrupt

                console.print()
                console.print(Panel.fit("[cyan]Analyzing...[/cyan]", border_style="cyan"))

                # Force dry-run for analysis
                dry_run = True

            elif action == "Verify all repos (find missing licenses)":
                # Verification is always read-only, no other questions needed
                verify_only = True
                console.print()
                console.print(Panel.fit("[cyan]Verifying all repos...[/cyan]", border_style="cyan"))

            elif action == "Update repos by pattern":
                pattern = questionary.text("Enter pattern (e.g., '*-stig-baseline', 'saf*'):").ask()
                if pattern is None:
                    raise KeyboardInterrupt

                console.print()

                # Ask if preview or apply
                mode = questionary.select(
                    "How would you like to proceed?",
                    choices=["Preview changes (dry-run)", "Apply changes now"],
                ).ask()
                if mode is None:
                    raise KeyboardInterrupt

                dry_run = mode == "Preview changes (dry-run)"

                # Ask about filters
                skip_archived = questionary.confirm("Skip archived repos?", default=True).ask()
                if skip_archived is None:
                    raise KeyboardInterrupt

            elif action == "Update all SAF repos":
                console.print()
                console.print("[yellow]⚠️  This will process all 243 SAF repos[/yellow]")

                confirmed = questionary.confirm("Are you sure?", default=False).ask()
                if not confirmed:
                    raise KeyboardInterrupt

                # Force dry-run for safety
                dry_run = True
                console.print(
                    "[cyan]Running in dry-run mode for safety (use --force to apply)[/cyan]"
                )

            console.print()
            console.print(Panel.fit("[green]✓ Starting...[/green]", border_style="green"))
            console.print()

        except KeyboardInterrupt:
            console.print("\n\n[yellow]⚠️  Cancelled by user[/yellow]")
            raise typer.Exit(0) from None

    # Verify Jinja2 templates exist
    required_templates = ["base.j2", "cis.j2", "disa.j2", "plain.j2"]
    for tmpl in required_templates:
        if not (TEMPLATES_DIR / tmpl).exists():
            console.print(f"[red]❌ Template not found: {TEMPLATES_DIR / tmpl}[/red]")
            raise typer.Exit(1)

    # Validate output format
    if output_format not in ["txt", "json", "csv"]:
        console.print(f"[red]❌ Invalid output format: {output_format}[/red]")
        raise typer.Exit(1)

    # Run standardization
    standardizer = RepoMinder(
        organization=org,  # Uses settings default if None
        team=team,  # Uses settings default if None
        dry_run=dry_run or verify_only,
        skip_templates=skip or [],
        skip_archived=skip_archived,
        delay=delay,
    )
    standardizer.output_format = output_format
    standardizer.output_file = output

    # Single repo test mode (show friendly analysis)
    if repo:
        console.print(f"[cyan]Analyzing '{repo}'...[/cyan]\n")
        result = standardizer.process_repo(repo)
        standardizer.results.append(result)
        standardizer.stats["total"] = 1

        # Show friendly message for single repo
        console.print()
        if result["action"] == "unchanged":
            console.print(
                Panel.fit(
                    f"[green]✅ LICENSE is correct[/green]\n\n"
                    f"[cyan]Template:[/cyan] {result['template'].upper()}\n"
                    f"[cyan]Status:[/cyan] No changes needed",
                    title=f"✓ {repo}",
                    border_style="green",
                )
            )
        elif result["status"] == "success":
            console.print(
                Panel.fit(
                    f"[yellow]⚠️  LICENSE needs update[/yellow]\n\n"
                    f"[cyan]Template:[/cyan] {result['template'].upper()}\n"
                    f"[cyan]Action:[/cyan] {result['action']}\n"
                    f"[cyan]Change:[/cyan] {'Formatting cleanup' if result['action'] == 'updated' else result['action'].title()}",
                    title=f"⚠️  {repo}",
                    border_style="yellow",
                )
            )
        elif result["status"] == "skipped":
            console.print(
                Panel.fit(f"[dim]Skipped: {result['action']}[/dim]", title=repo, border_style="dim")
            )
        else:
            console.print(
                Panel.fit(
                    f"[red]❌ Error: {result.get('error', 'Unknown')}[/red]",
                    title=repo,
                    border_style="red",
                )
            )

        # Also show summary table
        console.print()
        standardizer.print_summary()
        if not dry_run:
            standardizer.verify_all([repo])
        raise typer.Exit(0 if result["status"] == "success" else 1)

    if verify_only:
        repos = standardizer.get_saf_repos()
        if repo_filter:
            repos = [r for r in repos if repo_filter.lower() in r.lower()]
        if pattern:
            import fnmatch

            repos = [r for r in repos if fnmatch.fnmatch(r, pattern)]
        standardizer.stats["total"] = len(repos)
        standardizer.verify_all(repos)
        raise typer.Exit(0) from None

    exit_code = standardizer.run(
        repo_filter=repo_filter,
        pattern=pattern,
        resume_from=resume_from,
        force=force,
        backup_enabled=backup,
    )
    raise typer.Exit(exit_code)


def main():
    """Entry point for script execution."""
    app()


if __name__ == "__main__":
    app()
