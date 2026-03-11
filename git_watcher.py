"""
Git Watcher Module
===================
Scans a local Git repository for changes (staged, unstaged, or between commits)
and extracts diff data for blast radius analysis.

This is the TRIGGER — clone a repo, make changes, and this module detects them.

Usage:
    watcher = GitWatcher("C:/projects/my-app")
    changes = watcher.get_changes()      # auto-detect uncommitted changes
    changes = watcher.get_changes("abc123")  # diff against a specific commit
"""

import os
import subprocess
import sys


class GitWatcher:
    """Watch a local Git repo for changes and extract diff data."""

    def __init__(self, repo_path: str):
        """
        Initialize with path to a local git repository.

        Args:
            repo_path: Absolute path to the cloned repo root
        """
        self.repo_path = os.path.abspath(repo_path)

        if not os.path.isdir(os.path.join(self.repo_path, ".git")):
            raise ValueError(
                f"Not a git repository: {self.repo_path}\n"
                f"Make sure you've cloned the repo first:\n"
                f"  git clone <repo-url>\n"
                f"  python agent.py --repo <path-to-repo>"
            )

    # ──────────────────────────────────────────
    # Change Detection (THE TRIGGER)
    # ──────────────────────────────────────────

    def has_changes(self) -> bool:
        """Check if the repo has any uncommitted changes (staged or unstaged)."""
        status = self._run_git("status", "--porcelain")
        return len(status.strip()) > 0

    def get_changes(self, base_ref: str = None) -> dict:
        """
        Detect and extract all changes for blast radius analysis.

        This is the main TRIGGER function. It:
        1. Detects what files changed
        2. Extracts the before/after code (diff)
        3. Gets the repo structure
        4. Builds a "What Changed" summary

        Args:
            base_ref: Git ref to diff against (commit SHA, branch, tag).
                      If None, diffs against HEAD (uncommitted changes).

        Returns:
            dict with: code_before, code_after, repo_structure, what_changed
        """
        print(f"  🔍 Scanning repo: {self.repo_path}")

        # Detect changed files
        if base_ref:
            changed_files = self._get_diff_files(base_ref)
            diff_text = self._get_diff(base_ref)
            diff_desc = f"Changes since {base_ref[:8]}..."
        else:
            changed_files = self._get_uncommitted_files()
            diff_text = self._get_uncommitted_diff()
            diff_desc = "Uncommitted changes"

        if not changed_files:
            print("  ⚠ No changes detected in the repository.")
            print("  Make some code changes first, then re-run the agent.")
            sys.exit(0)

        print(f"  ✓ Found {len(changed_files)} changed file(s)")

        # Build code before / after from diff
        code_before, code_after = self._parse_diff(diff_text)

        # Build "What Changed" summary
        what_changed = self._build_change_summary(changed_files, diff_desc)

        # Get repo structure
        repo_structure = self._get_repo_structure()

        return {
            "code_before": code_before,
            "code_after": code_after,
            "repo_structure": repo_structure,
            "what_changed": what_changed,
            "changed_files": changed_files,
        }

    # ──────────────────────────────────────────
    # Git Diff Extraction
    # ──────────────────────────────────────────

    def _get_uncommitted_files(self) -> list[dict]:
        """Get list of files with uncommitted changes (staged + unstaged)."""
        output = self._run_git("diff", "--name-status", "HEAD")
        # Also include untracked files
        untracked = self._run_git("ls-files", "--others", "--exclude-standard")

        files = []
        for line in output.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t", 1)
            if len(parts) == 2:
                status_code, filepath = parts
                status = {
                    "M": "modified", "A": "added", "D": "deleted",
                    "R": "renamed", "C": "copied"
                }.get(status_code[0], "changed")
                files.append({"path": filepath, "status": status})

        for line in untracked.strip().split("\n"):
            if line.strip():
                files.append({"path": line.strip(), "status": "new (untracked)"})

        return files

    def _get_diff_files(self, base_ref: str) -> list[dict]:
        """Get list of files changed between base_ref and HEAD."""
        output = self._run_git("diff", "--name-status", base_ref, "HEAD")
        files = []
        for line in output.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t", 1)
            if len(parts) == 2:
                status_code, filepath = parts
                status = {
                    "M": "modified", "A": "added", "D": "deleted",
                    "R": "renamed"
                }.get(status_code[0], "changed")
                files.append({"path": filepath, "status": status})
        return files

    def _get_uncommitted_diff(self) -> str:
        """Get full unified diff of uncommitted changes."""
        # Staged changes
        staged = self._run_git("diff", "--cached")
        # Unstaged changes
        unstaged = self._run_git("diff")
        return staged + "\n" + unstaged

    def _get_diff(self, base_ref: str) -> str:
        """Get full unified diff between base_ref and HEAD."""
        return self._run_git("diff", base_ref, "HEAD")

    def _parse_diff(self, diff_text: str) -> tuple[str, str]:
        """
        Parse a unified diff into code_before and code_after blocks.

        Returns:
            (code_before, code_after) as formatted strings
        """
        before_lines = []
        after_lines = []
        current_file = ""

        for line in diff_text.split("\n"):
            if line.startswith("diff --git"):
                # Extract filename
                parts = line.split(" b/")
                if len(parts) >= 2:
                    current_file = parts[-1]
                    before_lines.append(f"\n# === {current_file} ===")
                    after_lines.append(f"\n# === {current_file} ===")
            elif line.startswith("@@"):
                before_lines.append(line)
                after_lines.append(line)
            elif line.startswith("-") and not line.startswith("---"):
                before_lines.append(line[1:])  # Removed line → before
            elif line.startswith("+") and not line.startswith("+++"):
                after_lines.append(line[1:])   # Added line → after
            elif not line.startswith("\\"):
                before_lines.append(line)
                after_lines.append(line)

        return "\n".join(before_lines), "\n".join(after_lines)

    # ──────────────────────────────────────────
    # "What Changed" Summary Builder
    # ──────────────────────────────────────────

    def _build_change_summary(self, files: list[dict], desc: str) -> str:
        """
        Build a human-readable summary of what changed.

        This provides the AI model with a clear overview before
        diving into the diff details.
        """
        lines = [
            f"Change Type: {desc}",
            f"Total Files Changed: {len(files)}",
            f"Repository: {os.path.basename(self.repo_path)}",
            "",
            "Changed Files:",
        ]

        # Group by status
        by_status = {}
        for f in files:
            by_status.setdefault(f["status"], []).append(f["path"])

        for status, paths in by_status.items():
            lines.append(f"  [{status.upper()}]")
            for p in paths[:15]:  # Cap at 15 per status
                lines.append(f"    - {p}")
            if len(paths) > 15:
                lines.append(f"    ... and {len(paths) - 15} more")

        # Get recent commit messages for context
        recent_commits = self._get_recent_commits(5)
        if recent_commits:
            lines.append("")
            lines.append("Recent Commits (for context):")
            for commit in recent_commits:
                lines.append(f"  • {commit}")

        return "\n".join(lines)

    # ──────────────────────────────────────────
    # Repo Structure
    # ──────────────────────────────────────────

    def _get_repo_structure(self) -> str:
        """Get the repository file tree (tracked files only)."""
        output = self._run_git("ls-tree", "-r", "--name-only", "HEAD")
        if not output.strip():
            # Fallback: list files in directory
            output = self._run_git("ls-files")

        lines = output.strip().split("\n")
        # Build tree-like structure
        tree_lines = [f"{os.path.basename(self.repo_path)}/"]

        dirs_seen = set()
        for filepath in lines[:200]:  # Cap at 200 files
            parts = filepath.split("/")
            # Add directory entries
            for i in range(len(parts) - 1):
                dir_path = "/".join(parts[:i+1])
                if dir_path not in dirs_seen:
                    dirs_seen.add(dir_path)
                    indent = "│   " * i
                    tree_lines.append(f"{indent}├── {parts[i]}/")
            # Add file entry
            indent = "│   " * (len(parts) - 1)
            tree_lines.append(f"{indent}├── {parts[-1]}")

        return "\n".join(tree_lines)

    # ──────────────────────────────────────────
    # Recent commits
    # ──────────────────────────────────────────

    def _get_recent_commits(self, count: int = 5) -> list[str]:
        """Get the last N commit messages."""
        output = self._run_git(
            "log", f"-{count}", "--oneline", "--no-decorate"
        )
        return [line.strip() for line in output.strip().split("\n") if line.strip()]

    # ──────────────────────────────────────────
    # Git command runner
    # ──────────────────────────────────────────

    def _run_git(self, *args) -> str:
        """Run a git command in the repo directory."""
        cmd = ["git", "-C", self.repo_path] + list(args)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace"
            )
            if result.returncode != 0 and result.stderr:
                # Non-fatal: some git commands return non-zero for valid reasons
                pass
            return result.stdout
        except FileNotFoundError:
            print(f"\n  ✖ ERROR: 'git' command not found.")
            print(f"    Install Git from https://git-scm.com\n")
            sys.exit(1)
        except subprocess.TimeoutExpired:
            print(f"\n  ✖ ERROR: Git command timed out: {' '.join(cmd)}\n")
            return ""
