"""
GitHub Handler Module
======================
Fetches Pull Request details, code diffs, and repository structure
from the GitHub API for automated blast radius analysis.

Usage:
    handler = GitHubHandler(token="ghp_xxx")
    pr_data = handler.fetch_pr_data("owner/repo", pr_number=42)
"""

import requests
import base64
import json
import sys

# ──────────────────────────────────────────────
# GitHub API Client
# ──────────────────────────────────────────────

GITHUB_API = "https://api.github.com"


class GitHubHandler:
    """Interact with the GitHub REST API to pull PR and repo data."""

    def __init__(self, token: str = None):
        """
        Initialize the handler.

        Args:
            token: GitHub Personal Access Token (optional for public repos,
                   required for private repos and higher rate limits).
        """
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "BlastRadiusAgent/1.0",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    # ──────────────────────────────────────────
    # Pull Request Data
    # ──────────────────────────────────────────

    def fetch_pr_details(self, repo: str, pr_number: int) -> dict:
        """
        Fetch PR metadata (title, body, state, author).

        Args:
            repo: "owner/repo" format (e.g. "microsoft/vscode")
            pr_number: Pull request number

        Returns:
            dict with title, body, state, author, labels, created_at
        """
        url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}"
        resp = self._request(url)

        return {
            "title": resp.get("title", ""),
            "body": resp.get("body", "") or "",
            "state": resp.get("state", ""),
            "author": resp.get("user", {}).get("login", ""),
            "labels": [l["name"] for l in resp.get("labels", [])],
            "created_at": resp.get("created_at", ""),
            "head_branch": resp.get("head", {}).get("ref", ""),
            "base_branch": resp.get("base", {}).get("ref", ""),
            "html_url": resp.get("html_url", ""),
        }

    def fetch_pr_diff(self, repo: str, pr_number: int) -> list[dict]:
        """
        Fetch the list of changed files in a PR with their patches.

        Returns:
            List of dicts, each with: filename, status, additions,
            deletions, patch (unified diff text).
        """
        url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/files"
        resp = self._request(url)

        files = []
        for file_data in resp:
            files.append({
                "filename": file_data.get("filename", ""),
                "status": file_data.get("status", ""),       # added/modified/removed
                "additions": file_data.get("additions", 0),
                "deletions": file_data.get("deletions", 0),
                "changes": file_data.get("changes", 0),
                "patch": file_data.get("patch", ""),          # unified diff
            })

        return files

    def fetch_file_content(self, repo: str, path: str, ref: str = "main") -> str:
        """
        Fetch raw content of a specific file from a branch/commit.

        Args:
            repo: "owner/repo"
            path: file path within the repo
            ref: branch name, tag, or commit SHA

        Returns:
            File content as a string
        """
        url = f"{GITHUB_API}/repos/{repo}/contents/{path}?ref={ref}"
        resp = self._request(url)

        content = resp.get("content", "")
        encoding = resp.get("encoding", "")

        if encoding == "base64":
            return base64.b64decode(content).decode("utf-8", errors="replace")
        return content

    # ──────────────────────────────────────────
    # Repository Structure
    # ──────────────────────────────────────────

    def fetch_repo_tree(self, repo: str, ref: str = "main", max_depth: int = 3) -> str:
        """
        Fetch the repository file tree structure.

        Args:
            repo: "owner/repo"
            ref: branch name or commit SHA
            max_depth: max directory depth to include

        Returns:
            Formatted tree string
        """
        url = f"{GITHUB_API}/repos/{repo}/git/trees/{ref}?recursive=1"
        resp = self._request(url)

        tree_items = resp.get("tree", [])

        # Filter to max depth and build formatted output
        lines = [f"{repo}/"]
        for item in tree_items:
            path = item["path"]
            depth = path.count("/")
            if depth >= max_depth:
                continue

            item_type = item["type"]  # "blob" = file, "tree" = directory
            indent = "│   " * depth
            connector = "├── " if item_type == "blob" else "├── "
            name = path.split("/")[-1]

            if item_type == "tree":
                name += "/"

            lines.append(f"{indent}{connector}{name}")

        return "\n".join(lines[:200])  # Cap at 200 lines

    # ──────────────────────────────────────────
    # PR Comments (for additional context)
    # ──────────────────────────────────────────

    def fetch_pr_comments(self, repo: str, pr_number: int) -> list[dict]:
        """Fetch review comments on a PR."""
        url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/comments"
        resp = self._request(url)

        comments = []
        for c in resp[:20]:  # Limit to 20 comments
            comments.append({
                "author": c.get("user", {}).get("login", ""),
                "body": c.get("body", ""),
                "path": c.get("path", ""),
                "created_at": c.get("created_at", ""),
            })

        return comments

    # ──────────────────────────────────────────
    # Issue Details (linked issues)
    # ──────────────────────────────────────────

    def fetch_issue(self, repo: str, issue_number: int) -> dict:
        """Fetch issue details (can serve as the 'ticket')."""
        url = f"{GITHUB_API}/repos/{repo}/issues/{issue_number}"
        resp = self._request(url)

        return {
            "title": resp.get("title", ""),
            "body": resp.get("body", "") or "",
            "state": resp.get("state", ""),
            "labels": [l["name"] for l in resp.get("labels", [])],
            "author": resp.get("user", {}).get("login", ""),
            "created_at": resp.get("created_at", ""),
        }

    # ──────────────────────────────────────────
    # Aggregate: Prepare all inputs from a PR
    # ──────────────────────────────────────────

    def fetch_pr_data(self, repo: str, pr_number: int) -> dict:
        """
        Fetch all data needed for blast radius analysis from a single PR.

        Returns:
            dict with keys matching agent input format:
            ticket, logs, code_before, code_after, repo_structure
        """
        print(f"  📡 Fetching PR #{pr_number} from {repo}...")

        # 1. PR details → ticket
        pr = self.fetch_pr_details(repo, pr_number)
        ticket_text = self._format_ticket(pr)
        print(f"  ✓ PR details loaded: \"{pr['title']}\"")

        # 2. PR diff → code_before / code_after
        diff_files = self.fetch_pr_diff(repo, pr_number)
        code_before, code_after = self._format_diffs(diff_files)
        print(f"  ✓ Diff loaded: {len(diff_files)} file(s) changed")

        # 3. PR comments → use as supplementary logs
        comments = self.fetch_pr_comments(repo, pr_number)
        logs_text = self._format_comments_as_logs(comments)
        print(f"  ✓ Comments loaded: {len(comments)} comment(s)")

        # 4. Repo tree → repo_structure
        base_branch = pr.get("base_branch", "main")
        repo_tree = self.fetch_repo_tree(repo, ref=base_branch)
        print(f"  ✓ Repo structure loaded ({base_branch} branch)")

        return {
            "ticket": ticket_text,
            "logs": logs_text if logs_text else "(No error logs available — review the code diff for potential issues)",
            "code_before": code_before,
            "code_after": code_after,
            "repo_structure": repo_tree,
        }

    # ──────────────────────────────────────────
    # Formatting helpers
    # ──────────────────────────────────────────

    def _format_ticket(self, pr: dict) -> str:
        """Format PR details as a ticket description."""
        labels = ", ".join(pr["labels"]) if pr["labels"] else "None"
        return (
            f"Title: {pr['title']}\n"
            f"Author: {pr['author']}\n"
            f"State: {pr['state']}\n"
            f"Labels: {labels}\n"
            f"Branch: {pr['head_branch']} → {pr['base_branch']}\n"
            f"URL: {pr['html_url']}\n"
            f"\nDescription:\n{pr['body']}"
        )

    def _format_diffs(self, files: list[dict]) -> tuple[str, str]:
        """
        Convert PR file diffs into code_before and code_after blocks.

        Uses the unified diff patch to show what changed.
        """
        before_lines = []
        after_lines = []

        for f in files:
            filename = f["filename"]
            status = f["status"]
            patch = f.get("patch", "")

            before_lines.append(f"# === {filename} ({status}) ===")
            after_lines.append(f"# === {filename} ({status}) ===")

            if not patch:
                before_lines.append("(binary file or no diff available)")
                after_lines.append("(binary file or no diff available)")
                continue

            # Parse unified diff into before/after
            for line in patch.split("\n"):
                if line.startswith("@@"):
                    before_lines.append(line)
                    after_lines.append(line)
                elif line.startswith("-"):
                    before_lines.append(line[1:])     # Removed line → belongs to "before"
                elif line.startswith("+"):
                    after_lines.append(line[1:])       # Added line → belongs to "after"
                else:
                    before_lines.append(line)
                    after_lines.append(line)

            before_lines.append("")
            after_lines.append("")

        return "\n".join(before_lines), "\n".join(after_lines)

    def _format_comments_as_logs(self, comments: list[dict]) -> str:
        """Format PR review comments as supplementary log info."""
        if not comments:
            return ""

        lines = ["# PR Review Comments (may contain error context):"]
        for c in comments:
            lines.append(f"\n[{c['created_at']}] {c['author']} on {c['path']}:")
            lines.append(c["body"])

        return "\n".join(lines)

    # ──────────────────────────────────────────
    # HTTP helper
    # ──────────────────────────────────────────

    def _request(self, url: str) -> dict | list:
        """Make an authenticated GET request to the GitHub API."""
        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
        except requests.ConnectionError:
            print(f"\n  ✖ ERROR: Cannot connect to GitHub API")
            print(f"    Check your internet connection.\n")
            sys.exit(1)
        except requests.Timeout:
            print(f"\n  ✖ ERROR: GitHub API request timed out\n")
            sys.exit(1)

        if resp.status_code == 401:
            print(f"\n  ✖ ERROR: GitHub authentication failed")
            print(f"    Check your token with --token flag.\n")
            sys.exit(1)
        elif resp.status_code == 403:
            rate = resp.headers.get("X-RateLimit-Remaining", "?")
            print(f"\n  ✖ ERROR: GitHub API rate limit exceeded (remaining: {rate})")
            print(f"    Use a token with --token to increase limits.\n")
            sys.exit(1)
        elif resp.status_code == 404:
            print(f"\n  ✖ ERROR: Resource not found: {url}")
            print(f"    Check the repo name and PR number.\n")
            sys.exit(1)
        elif resp.status_code != 200:
            print(f"\n  ✖ ERROR: GitHub API returned {resp.status_code}")
            print(f"    {resp.text[:300]}\n")
            sys.exit(1)

        return resp.json()
