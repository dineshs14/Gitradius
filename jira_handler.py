"""
Jira Handler Module
====================
Fetches ticket details from Jira Cloud or Jira Server
for use as context in blast radius analysis.

Usage:
    handler = JiraHandler(
        base_url="https://yourcompany.atlassian.net",
        email="you@company.com",
        api_token="your-jira-api-token"
    )
    ticket = handler.fetch_ticket("PROJ-1234")
"""

import requests
import base64
import sys


class JiraHandler:
    """Fetch ticket details from Jira REST API."""

    def __init__(self, base_url: str, email: str = None, api_token: str = None):
        """
        Initialize the Jira client.

        Args:
            base_url: Jira instance URL (e.g. https://yourcompany.atlassian.net)
            email: Your Jira email (for Jira Cloud authentication)
            api_token: Jira API token (generate at https://id.atlassian.com/manage-profile/security/api-tokens)
        """
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # Basic auth: email:api_token (base64 encoded)
        if email and api_token:
            credentials = base64.b64encode(f"{email}:{api_token}".encode()).decode()
            self.headers["Authorization"] = f"Basic {credentials}"
        elif api_token:
            # Bearer token for Jira Server / Data Center
            self.headers["Authorization"] = f"Bearer {api_token}"

    # ──────────────────────────────────────────
    # Fetch Ticket
    # ──────────────────────────────────────────

    def fetch_ticket(self, ticket_id: str) -> dict:
        """
        Fetch a Jira ticket by its key (e.g. PROJ-1234).

        Returns:
            dict with: key, summary, description, status, priority,
            assignee, reporter, labels, issue_type, created, updated
        """
        url = f"{self.base_url}/rest/api/2/issue/{ticket_id}"

        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
        except requests.ConnectionError:
            print(f"\n  ✖ ERROR: Cannot connect to Jira at {self.base_url}")
            print(f"    Check the URL and your network connection.\n")
            sys.exit(1)
        except requests.Timeout:
            print(f"\n  ✖ ERROR: Jira request timed out\n")
            sys.exit(1)

        if resp.status_code == 401:
            print(f"\n  ✖ ERROR: Jira authentication failed")
            print(f"    Check your email and API token.\n")
            print(f"    Generate a token at: https://id.atlassian.com/manage-profile/security/api-tokens\n")
            sys.exit(1)
        elif resp.status_code == 403:
            print(f"\n  ✖ ERROR: Access denied to ticket {ticket_id}")
            print(f"    You may not have permission to view this ticket.\n")
            sys.exit(1)
        elif resp.status_code == 404:
            print(f"\n  ✖ ERROR: Jira ticket not found: {ticket_id}")
            print(f"    Check the ticket key (e.g. PROJ-1234).\n")
            sys.exit(1)
        elif resp.status_code != 200:
            print(f"\n  ✖ ERROR: Jira API returned {resp.status_code}")
            print(f"    {resp.text[:300]}\n")
            sys.exit(1)

        data = resp.json()
        fields = data.get("fields", {})

        return {
            "key": data.get("key", ticket_id),
            "summary": fields.get("summary", ""),
            "description": fields.get("description", "") or "",
            "status": self._safe_nested(fields, "status", "name"),
            "priority": self._safe_nested(fields, "priority", "name"),
            "issue_type": self._safe_nested(fields, "issuetype", "name"),
            "assignee": self._safe_nested(fields, "assignee", "displayName"),
            "reporter": self._safe_nested(fields, "reporter", "displayName"),
            "labels": fields.get("labels", []),
            "components": [c.get("name", "") for c in fields.get("components", [])],
            "created": fields.get("created", ""),
            "updated": fields.get("updated", ""),
            "resolution": self._safe_nested(fields, "resolution", "name"),
        }

    def fetch_ticket_comments(self, ticket_id: str) -> list[dict]:
        """Fetch comments on a Jira ticket (useful as supplementary logs)."""
        url = f"{self.base_url}/rest/api/2/issue/{ticket_id}/comment"

        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
            if resp.status_code != 200:
                return []
        except Exception:
            return []

        data = resp.json()
        comments = []
        for c in data.get("comments", [])[:15]:  # Cap at 15
            comments.append({
                "author": self._safe_nested(c, "author", "displayName"),
                "body": c.get("body", ""),
                "created": c.get("created", ""),
            })

        return comments

    # ──────────────────────────────────────────
    # Format ticket for the agent
    # ──────────────────────────────────────────

    def format_ticket_for_agent(self, ticket_id: str) -> str:
        """
        Fetch and format a Jira ticket as a text block for the AI prompt.

        Returns:
            Formatted string with all ticket details
        """
        ticket = self.fetch_ticket(ticket_id)
        comments = self.fetch_ticket_comments(ticket_id)

        labels = ", ".join(ticket["labels"]) if ticket["labels"] else "None"
        components = ", ".join(ticket["components"]) if ticket["components"] else "None"

        text = (
            f"Ticket: {ticket['key']}\n"
            f"Title: {ticket['summary']}\n"
            f"Type: {ticket['issue_type']}\n"
            f"Status: {ticket['status']}\n"
            f"Priority: {ticket['priority']}\n"
            f"Assignee: {ticket['assignee'] or 'Unassigned'}\n"
            f"Reporter: {ticket['reporter'] or 'Unknown'}\n"
            f"Labels: {labels}\n"
            f"Components: {components}\n"
            f"Created: {ticket['created']}\n"
            f"Updated: {ticket['updated']}\n"
            f"Resolution: {ticket['resolution'] or 'Unresolved'}\n"
            f"\nDescription:\n{ticket['description']}"
        )

        if comments:
            text += "\n\n--- Ticket Comments ---"
            for c in comments:
                text += f"\n\n[{c['created']}] {c['author']}:\n{c['body']}"

        return text

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    def _safe_nested(self, data: dict, *keys) -> str:
        """Safely extract a nested dict value, returning '' if not found."""
        current = data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return ""
        return current or ""
