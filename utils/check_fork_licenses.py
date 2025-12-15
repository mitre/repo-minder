#!/usr/bin/env python3
"""Check if any SAF team forks have LICENSE files that differ from upstream.

This utility helps identify forks where we may have accidentally modified
the LICENSE file, which should match the upstream repository.
"""

import json
import subprocess


def get_saf_repos():
    """Get all SAF team repository names."""
    result = subprocess.run(
        ["gh", "api", "orgs/mitre/teams/saf/repos", "--paginate", "--jq", ".[].name"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("Failed to fetch SAF repos")
    return [line.strip() for line in result.stdout.strip().split("\n")]


def is_fork(repo_name):
    """Check if a repo is a fork and return parent info."""
    result = subprocess.run(
        [
            "gh",
            "api",
            f"repos/mitre/{repo_name}",
            "--jq",
            "{fork: .fork, parent: .parent.full_name}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False, None

    data = json.loads(result.stdout)
    return data.get("fork", False), data.get("parent")


def get_license_content(repo_full_name, variant):
    """Get LICENSE file content from a repo."""
    result = subprocess.run(
        ["gh", "api", f"repos/{repo_full_name}/contents/{variant}", "--jq", ".content"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def check_fork_licenses():
    """Check all forks for LICENSE differences from upstream."""
    repos = get_saf_repos()
    variants = ["LICENSE.md", "LICENSE", "LICENSE.txt"]

    forks_checked = 0
    forks_with_differences = []

    for repo in repos:
        is_forked, parent = is_fork(repo)
        if not is_forked or not parent:
            continue

        forks_checked += 1

        # Check each LICENSE variant
        for variant in variants:
            fork_content = get_license_content(f"mitre/{repo}", variant)
            if not fork_content:
                continue

            parent_content = get_license_content(parent, variant)
            if not parent_content:
                continue

            # Compare content
            if fork_content != parent_content:
                forks_with_differences.append((repo, parent, variant))
            break  # Found matching variant, don't check others

    return forks_checked, forks_with_differences


def main():
    """Main entry point."""
    print("Checking SAF team forks for LICENSE differences...\n")

    forks_checked, differences = check_fork_licenses()

    print(f"Checked {forks_checked} forks\n")

    if differences:
        print(f"⚠️  Found {len(differences)} forks with LICENSE differences:\n")
        for repo, parent, variant in differences:
            print(f"  • {repo}")
            print(f"    Fork of: {parent}")
            print(f"    File: {variant}")
            print()
        print("\n💡 These forks should have their LICENSE reverted to match upstream")
    else:
        print("✅ All fork LICENSEs match their upstream repos")


if __name__ == "__main__":
    main()
