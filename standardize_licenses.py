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
    python3 standardize_mitre_licenses.py --dry-run
    python3 standardize_mitre_licenses.py --skip cis
    python3 standardize_mitre_licenses.py --verify-only
    python3 standardize_mitre_licenses.py --repo saf
    python3 standardize_mitre_licenses.py --pattern '*-stig-baseline'
    python3 standardize_mitre_licenses.py --skip-archived --resume-from nginx-baseline
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False

# Template paths
SCRIPT_DIR = Path(__file__).parent
TEMPLATES_DIR = SCRIPT_DIR / "templates"

# Template variables
TEMPLATE_VARS = {
    "year": datetime.now().year,
    "case_number": "18-3678",
    "organization": "The MITRE Corporation",
}


class LicenseStandardizer:
    """Standardize LICENSE files across MITRE repos."""

    def __init__(self, dry_run=False, skip_templates=None, skip_archived=False, delay=0.5):
        self.dry_run = dry_run
        self.skip_templates = skip_templates or []
        self.skip_archived = skip_archived
        self.delay = delay  # Delay between repos (rate limiting)
        self.stats = {
            "total": 0,
            "updated": 0,
            "created": 0,
            "renamed": 0,
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
        """Get list of all SAF team repos via gh cli."""
        print("Fetching SAF team repositories...")
        result = subprocess.run(
            ["gh", "api", "orgs/mitre/teams/saf/repos", "--paginate", "--jq", ".[].name"],
            capture_output=True,
            text=True,
            check=True,
        )
        repos = [line.strip() for line in result.stdout.strip().split("\n")]
        print(f"Found {len(repos)} repos in SAF team\n")
        return repos

    def check_license_file(self, repo_name: str) -> Tuple[Optional[str], Optional[str]]:
        """Check which LICENSE file exists.

        Returns:
            (file_path, sha) if exists, (None, None) if not
        """
        # Try LICENSE.md first
        for filename in ["LICENSE.md", "LICENSE"]:
            result = subprocess.run(
                [
                    "gh",
                    "api",
                    f"repos/mitre/{repo_name}/contents/{filename}",
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
            ["gh", "api", f"repos/mitre/{repo_name}/contents/{file_path}", "--jq", ".content"],
            capture_output=True,
            text=True,
            check=True,
        )
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
                f"repos/mitre/{repo_name}",
                "--jq",
                '{"fork": .fork, "archived": .archived, "default_branch": .default_branch}',
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)

    def get_default_branch(self, repo_name: str) -> str:
        """Get default branch for repo."""
        result = subprocess.run(
            ["gh", "api", f"repos/mitre/{repo_name}", "--jq", ".default_branch"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip().strip('"')

    def create_license(self, repo_name: str, template_type: str, branch: str):
        """Create new LICENSE.md file."""
        template = self.templates[template_type]

        if self.dry_run:
            print(f"  [DRY RUN] Would create LICENSE.md using {template_type} template")
            return True

        with open("temp_license.md", "w") as f:
            f.write(template)

        cmd = [
            "gh",
            "api",
            f"repos/mitre/{repo_name}/contents/LICENSE.md",
            "-X",
            "PUT",
            "-F",
            "message=docs: add LICENSE.md [skip ci]",
            "-F",
            "content=@temp_license.md",
            "-F",
            f"branch={branch}",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        Path("temp_license.md").unlink()

        return result.returncode == 0

    def update_license(
        self, repo_name: str, template_type: str, old_file: str, sha: str, branch: str
    ):
        """Update or create LICENSE.md file."""
        template = self.templates[template_type]

        if self.dry_run:
            print(
                f"  [DRY RUN] Would update {old_file} → LICENSE.md using {template_type} template"
            )
            return True

        # Create/update LICENSE.md
        with open("temp_license.md", "w") as f:
            f.write(template)

        if old_file == "LICENSE.md":
            # Update existing LICENSE.md
            cmd = [
                "gh",
                "api",
                f"repos/mitre/{repo_name}/contents/LICENSE.md",
                "-X",
                "PUT",
                "-F",
                "message=docs: clean up LICENSE.md formatting [skip ci]",
                "-F",
                "content=@temp_license.md",
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
                f"repos/mitre/{repo_name}/contents/LICENSE.md",
                "-X",
                "PUT",
                "-F",
                "message=docs: add LICENSE.md [skip ci]",
                "-F",
                "content=@temp_license.md",
                "-F",
                f"branch={branch}",
            ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        Path("temp_license.md").unlink()

        if result.returncode != 0:
            print(f"  ❌ Failed to create LICENSE.md: {result.stderr}")
            return False

        # Delete old LICENSE if it existed
        if old_file == "LICENSE":
            self.delete_old_license(repo_name, branch)

        return True

    def delete_old_license(self, repo_name: str, branch: str):
        """Delete old LICENSE file (no .md extension)."""
        if self.dry_run:
            print("  [DRY RUN] Would delete old LICENSE file")
            return

        # Get current SHA of LICENSE file
        result = subprocess.run(
            ["gh", "api", f"repos/mitre/{repo_name}/contents/LICENSE", "--jq", ".sha"],
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
                f"repos/mitre/{repo_name}/contents/LICENSE",
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
        """Verify repo has LICENSE.md with correct content."""
        file_path, _ = self.check_license_file(repo_name)
        if file_path == "LICENSE.md":
            return True
        return False

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

    def verify_all(self, repos: List[str]):
        """Verify all repos have LICENSE.md."""
        print("\n" + "=" * 70)
        print("VERIFICATION")
        print("=" * 70 + "\n")

        missing = []
        for repo in repos:
            if self.verify_license(repo):
                self.stats["verified"] += 1
            else:
                missing.append(repo)

        if missing:
            print(f"❌ {len(missing)} repos still missing LICENSE.md:")
            for repo in missing:
                print(f"  - {repo}")
        else:
            print(f"✅ All {self.stats['verified']} repos have LICENSE.md")

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

            print(f"\n📝 Dry-run plan saved to: {plan_file}")

        # JSON format
        elif output_format == "json":
            import json as json_lib

            plan_file = Path(output_file) if output_file else Path("dry_run_plan.json")
            output = {
                "summary": self.stats,
                "results": self.results,
            }
            with open(plan_file, "w") as f:
                json_lib.dump(output, f, indent=2)
            print(f"\n📝 Dry-run plan saved to: {plan_file}")

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
            print(f"\n📝 Dry-run plan saved to: {plan_file}")

    def print_summary(self):
        """Print summary of operations."""
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Total repos:      {self.stats['total']}")
        print(f"Updated:          {self.stats['updated']}")
        print(f"Created:          {self.stats['created']}")
        print(f"Renamed:          {self.stats['renamed']}")
        print(f"Skipped:          {self.stats['skipped']}")
        if self.stats["forks"] > 0:
            print(f"  - Forks:        {self.stats['forks']}")
        if self.stats["archived"] > 0:
            print(f"  - Archived:     {self.stats['archived']}")
        print(f"Failed:           {self.stats['failed']}")
        if self.stats["verified"] > 0:
            print(f"Verified:         {self.stats['verified']}")

        if self.stats["failed"] > 0:
            print("\nFailed repos:")
            for r in self.results:
                if r["status"] == "failed":
                    print(f"  - {r['repo']}: {r.get('error', 'unknown error')}")

    def run(
        self,
        repo_filter: Optional[str] = None,
        pattern: Optional[str] = None,
        resume_from: Optional[str] = None,
    ):
        """Run standardization on all repos."""
        # Get repos
        repos = self.get_saf_repos()

        if repo_filter:
            repos = [r for r in repos if repo_filter.lower() in r.lower()]
            print(f"Filtered to {len(repos)} repos matching '{repo_filter}'\n")

        if pattern:
            import fnmatch

            repos = [r for r in repos if fnmatch.fnmatch(r, pattern)]
            print(f"Filtered to {len(repos)} repos matching pattern '{pattern}'\n")

        # Resume from specific repo
        if resume_from:
            try:
                start_index = repos.index(resume_from)
                repos = repos[start_index:]
                print(f"Resuming from '{resume_from}' ({len(repos)} repos remaining)\n")
            except ValueError:
                print(f"❌ Resume repo '{resume_from}' not found in list")
                return 1

        self.stats["total"] = len(repos)

        # Process each repo
        print("Processing repositories...\n")
        for i, repo in enumerate(repos, 1):
            print(f"[{i}/{len(repos)}] {repo}...", end=" ", flush=True)
            result = self.process_repo(repo)
            self.results.append(result)

            # Print status
            if result["status"] == "success":
                action_msg = f"✅ {result['action']} ({result['template']})"
                print(action_msg)
                if self.dry_run:
                    self.dry_run_plan.append(f"{repo}: {result['action']} ({result['template']})")
            elif result["status"] == "skipped":
                print(f"⏭️  {result['action']}")
            else:
                print(f"❌ {result['error']}")

            # Rate limiting delay (except for last repo)
            if i < len(repos) and not self.dry_run:
                time.sleep(self.delay)

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


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Standardize LICENSE files in MITRE SAF repos")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--skip",
        action="append",
        choices=["cis", "disa", "plain"],
        help="Skip repos with specific template types (can specify multiple times)",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify LICENSE.md exists, don't update",
    )
    parser.add_argument(
        "--repo-filter",
        help="Filter repos by name substring",
    )
    parser.add_argument(
        "--repo",
        help="Process single repo only (test mode)",
    )
    parser.add_argument(
        "--pattern",
        help="Process repos matching glob pattern (e.g., 'stig-*', '*-baseline')",
    )
    parser.add_argument(
        "--skip-archived",
        action="store_true",
        help="Skip archived repositories",
    )
    parser.add_argument(
        "--resume-from",
        help="Resume from specific repo (if script failed mid-run)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay between repos in seconds (default: 0.5)",
    )
    parser.add_argument(
        "--output-format",
        choices=["txt", "json", "csv"],
        default="txt",
        help="Dry-run output format (default: txt)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output file for dry-run plan (default: dry_run_plan.{format})",
    )

    args = parser.parse_args()

    # Verify Jinja2 templates exist
    required_templates = ["base.j2", "cis.j2", "disa.j2", "plain.j2"]
    for tmpl in required_templates:
        if not (TEMPLATES_DIR / tmpl).exists():
            print(f"❌ Template not found: {TEMPLATES_DIR / tmpl}")
            return 1

    # Run standardization
    standardizer = LicenseStandardizer(
        dry_run=args.dry_run or args.verify_only,
        skip_templates=args.skip or [],
        skip_archived=args.skip_archived,
        delay=args.delay,
    )
    standardizer.output_format = args.output_format  # For dry-run reporting
    standardizer.output_file = args.output  # For custom output filename

    # Single repo test mode
    if args.repo:
        print(f"Test mode: Processing single repo '{args.repo}'\n")
        result = standardizer.process_repo(args.repo)
        standardizer.results.append(result)
        standardizer.stats["total"] = 1
        standardizer.print_summary()
        if not args.dry_run:
            standardizer.verify_all([args.repo])
        return 0 if result["status"] == "success" else 1

    if args.verify_only:
        repos = standardizer.get_saf_repos()
        if args.repo_filter:
            repos = [r for r in repos if args.repo_filter.lower() in r.lower()]
        if args.pattern:
            import fnmatch

            repos = [r for r in repos if fnmatch.fnmatch(r, args.pattern)]
        standardizer.stats["total"] = len(repos)
        standardizer.verify_all(repos)
        return 0

    return standardizer.run(
        repo_filter=args.repo_filter, pattern=args.pattern, resume_from=args.resume_from
    )


if __name__ == "__main__":
    sys.exit(main())
