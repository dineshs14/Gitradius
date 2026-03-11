"""
Kani-Store Local AI Engineering Agent
=======================================
A local AI-powered agent that monitors Jira, GitHub commits, and
local code changes for the Kani-Store project.

Since this is a prototype (no real APIs), it works via:
  - jira_state.txt   → simulates Jira tickets
  - github_state.txt → simulates GitHub commits
  - Local git diff   → detects real code changes

Output Format (always):
  1. Jira Update Summary
  2. Latest GitHub Commit Summary
  3. Code Change Impact Analysis
  4. Affected Modules
  5. Recommendations

Usage:
  python kani_agent.py                    # Full analysis (all 3 sources)
  python kani_agent.py --jira             # Only Jira updates
  python kani_agent.py --github          # Only GitHub commits
  python kani_agent.py --code            # Only code impact analysis
  python kani_agent.py --watch           # Watch mode (runs every 30s)
"""

import argparse
import json
import os
import sys
import time
import subprocess
import hashlib
import re
from datetime import datetime

# ── Fix Windows console encoding (cp1252 → UTF-8) ──────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

AGENT_DIR    = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(AGENT_DIR, ".."))

# The simulated data files (prototype: no real APIs)
JIRA_STATE_FILE   = os.path.join(AGENT_DIR, "jira_state.json")
GITHUB_STATE_FILE = os.path.join(AGENT_DIR, "github_state.json")
LAST_STATE_FILE   = os.path.join(AGENT_DIR, ".last_state.json")
OUTPUTS_DIR       = os.path.join(AGENT_DIR, "outputs")

# Kani-Store project structure (used for dependency graph)
KANI_MODULES = {
    "App.tsx":              ["types.ts", "constants.ts", "services/geminiService.ts", "components/Icons.tsx"],
    "constants.ts":         ["types.ts"],
    "types.ts":             [],
    "index.tsx":            ["App.tsx"],
    "services/geminiService.ts": ["types.ts"],
    "components/Icons.tsx": [],
    "index.html":           ["index.tsx"],
    "vite.config.ts":       [],
    "package.json":         [],
    "tsconfig.json":        [],
}

# Critical files — changes here have HIGH impact
CRITICAL_FILES = {"App.tsx", "types.ts", "constants.ts", "services/geminiService.ts"}

# Ollama config
OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "mistral"

# ──────────────────────────────────────────────
# ANSI Colors
# ──────────────────────────────────────────────

C = {
    "reset":   "\033[0m",
    "bold":    "\033[1m",
    "red":     "\033[91m",
    "green":   "\033[92m",
    "yellow":  "\033[93m",
    "blue":    "\033[94m",
    "magenta": "\033[95m",
    "cyan":    "\033[96m",
    "dim":     "\033[2m",
    "white":   "\033[97m",
}

def c(text, color):
    return f"{C.get(color,'')}{text}{C['reset']}"

def section(title, icon="▸"):
    print(f"\n{c(f'  {icon}  {title}', 'bold')}")
    print(c("  " + "─" * 56, "dim"))

def status(msg, icon="•", color="green"):
    print(f"  {c(icon, color)} {msg}")

def warn(msg):
    print(f"  {c('⚠', 'yellow')}  {c(msg, 'yellow')}")

def err(msg):
    print(f"  {c('✖', 'red')}  {c(msg, 'red')}")

# ──────────────────────────────────────────────
# Banner
# ──────────────────────────────────────────────

def print_banner():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(c("""
  +----------------------------------------------------------+
  |        Kani-Store Engineering Agent                      |
  |                                                          |
  |   Jira Tracker * GitHub Monitor * Code Impact Analyzer   |
  +----------------------------------------------------------+""", "cyan"))
    print(c(f"  [{now}]  Project: {PROJECT_ROOT}", "dim"))
    print()

# ──────────────────────────────────────────────
# State Management (detect changes between runs)
# ──────────────────────────────────────────────

def load_last_state():
    if os.path.exists(LAST_STATE_FILE):
        with open(LAST_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_state(state: dict):
    with open(LAST_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def file_hash(path: str) -> str:
    """MD5 hash of a file — used to detect changes."""
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

# ──────────────────────────────────────────────
# Jira Tracker (File-based prototype)
# ──────────────────────────────────────────────

def load_jira_state() -> dict:
    """Load simulated Jira tickets from jira_state.json."""
    if not os.path.exists(JIRA_STATE_FILE):
        return {"tickets": []}
    with open(JIRA_STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def analyze_jira_updates(last_state: dict) -> dict:
    """
    Compare current Jira state with last state.
    Returns: dict with new tickets, status changes, comment additions.
    """
    current = load_jira_state()
    last_tickets = {t["id"]: t for t in last_state.get("jira_tickets", [])}
    current_tickets = {t["id"]: t for t in current.get("tickets", [])}

    result = {
        "new_tickets":         [],
        "status_changes":      [],
        "comment_additions":   [],
        "description_updates": [],
        "all_tickets":         current.get("tickets", []),
        "has_changes":         False,
    }

    for tid, ticket in current_tickets.items():
        if tid not in last_tickets:
            result["new_tickets"].append(ticket)
            result["has_changes"] = True
        else:
            prev = last_tickets[tid]
            if ticket.get("status") != prev.get("status"):
                result["status_changes"].append({
                    "id":   tid,
                    "from": prev.get("status"),
                    "to":   ticket.get("status"),
                    "title": ticket.get("title"),
                })
                result["has_changes"] = True
            if ticket.get("description") != prev.get("description"):
                result["description_updates"].append(ticket)
                result["has_changes"] = True
            prev_comments = len(prev.get("comments", []))
            curr_comments = len(ticket.get("comments", []))
            if curr_comments > prev_comments:
                new_comments = ticket["comments"][prev_comments:]
                result["comment_additions"].append({
                    "id":       tid,
                    "title":    ticket.get("title"),
                    "comments": new_comments,
                })
                result["has_changes"] = True

    return result

def print_jira_summary(jira_result: dict):
    """Print Jira Update Summary block."""
    section("JIRA UPDATE SUMMARY", "🎫")

    tickets = jira_result.get("all_tickets", [])
    if not tickets:
        warn("No Jira tickets found in jira_state.json")
        print(f"  {c('→ Create', 'dim')} {c(JIRA_STATE_FILE, 'cyan')} {c('to simulate Jira tickets', 'dim')}")
        return

    if not jira_result.get("has_changes"):
        status("No changes since last run", "✓", "green")

    # New tickets
    for t in jira_result.get("new_tickets", []):
        print(f"\n  {c('NEW TICKET', 'green')}  {c(t['id'], 'cyan')} — {t['title']}")
        print(f"    Priority: {_priority_color(t.get('priority','?'))}  |  Status: {c(t.get('status','?'), 'yellow')}")
        if t.get("description"):
            desc_short = t["description"][:120].replace("\n", " ")
            print(f"    Desc: {c(desc_short + '...', 'dim')}")
        _print_dev_impact(t)

    # Status changes
    for sc in jira_result.get("status_changes", []):
        print(f"\n  {c('STATUS CHANGE', 'yellow')}  {c(sc['id'], 'cyan')} — {sc['title']}")
        print(f"    {c(sc['from'], 'red')} → {c(sc['to'], 'green')}")

    # Comment additions
    for ca in jira_result.get("comment_additions", []):
        print(f"\n  {c('NEW COMMENTS', 'blue')}  {c(ca['id'], 'cyan')} — {ca['title']}")
        for cm in ca["comments"]:
            body_short = cm.get("body", "")[:100].replace("\n", " ")
            print(f"    [{cm.get('author','?')}]: {body_short}")

    # Description updates
    for du in jira_result.get("description_updates", []):
        print(f"\n  {c('DESCRIPTION UPDATED', 'magenta')}  {c(du['id'], 'cyan')} — {du['title']}")

    # Table of all tickets
    print(f"\n  {c('All Active Tickets:', 'bold')}")
    print(f"  {'ID':<12} {'Status':<14} {'Priority':<10} {'Title'}")
    print(c("  " + "─" * 60, "dim"))
    for t in tickets:
        sid = c(f"{t.get('id','?'):<12}", "cyan")
        sstatus = f"{t.get('status','?'):<14}"
        sprint = _priority_color(f"{t.get('priority','?'):<10}")
        print(f"  {sid}{sstatus}{sprint}{t.get('title','')[:40]}")

def _priority_color(p: str) -> str:
    p_str = str(p).strip()
    if "Critical" in p_str or "Blocker" in p_str:
        return c(p_str, "red")
    elif "High" in p_str:
        return c(p_str, "yellow")
    elif "Medium" in p_str:
        return c(p_str, "blue")
    return c(p_str, "dim")

def _print_dev_impact(ticket: dict):
    """Infer dev impact from ticket data."""
    title = ticket.get("title", "").lower()
    affected = []
    if any(k in title for k in ["product", "cart", "catalog", "price", "stock"]):
        affected.append("constants.ts (PRODUCTS data)")
    if any(k in title for k in ["ui", "component", "design", "layout", "page"]):
        affected.append("App.tsx (UI components)")
    if any(k in title for k in ["api", "gemini", "ai", "service"]):
        affected.append("services/geminiService.ts")
    if any(k in title for k in ["type", "interface", "model", "schema"]):
        affected.append("types.ts")
    if any(k in title for k in ["order", "checkout", "payment"]):
        affected.extend(["App.tsx (order flow)", "types.ts (Order interface)"])
    if affected:
        print(f"    {c('→ Likely dev impact:', 'dim')} {', '.join(affected)}")

# ──────────────────────────────────────────────
# GitHub Monitor (File-based prototype)
# ──────────────────────────────────────────────

def load_github_state() -> dict:
    """Load simulated GitHub commit history from github_state.json."""
    if not os.path.exists(GITHUB_STATE_FILE):
        return {"commits": [], "repo": "Kani-Store"}
    with open(GITHUB_STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def get_real_git_log() -> list[dict]:
    """Get actual git commits from the Kani-Store repo."""
    try:
        result = subprocess.run(
            ["git", "-C", PROJECT_ROOT, "log", "--oneline", "-10",
             "--pretty=format:%H|%an|%ae|%ai|%s"],
            capture_output=True, text=True, timeout=15
        )
        commits = []
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split("|", 4)
                if len(parts) == 5:
                    commits.append({
                        "hash":    parts[0][:8],
                        "author":  parts[1],
                        "email":   parts[2],
                        "date":    parts[3][:19],
                        "message": parts[4],
                    })
        return commits
    except Exception:
        return []

def get_real_changed_files(commit_hash: str = None) -> list[dict]:
    """Get files changed in the last commit or uncommitted changes."""
    try:
        if commit_hash:
            cmd = ["git", "-C", PROJECT_ROOT, "diff-tree", "--no-commit-id",
                   "-r", "--name-status", commit_hash]
        else:
            cmd = ["git", "-C", PROJECT_ROOT, "diff", "--name-status", "HEAD"]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        files = []
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split("\t", 1)
                if len(parts) == 2:
                    status_map = {"M": "modified", "A": "added", "D": "deleted", "R": "renamed"}
                    files.append({
                        "status": status_map.get(parts[0][0], "changed"),
                        "path":   parts[1],
                    })
        return files
    except Exception:
        return []

def analyze_github_updates(last_state: dict) -> dict:
    """Detect new commits vs last run."""
    real_commits = get_real_git_log()
    simulated    = load_github_state()
    sim_commits  = simulated.get("commits", [])

    last_commit_hash = last_state.get("last_commit_hash", "")

    # Determine latest commit
    latest = None
    new_commits = []

    if real_commits:
        latest = real_commits[0]
        for rc in real_commits:
            if rc["hash"] == last_commit_hash:
                break
            new_commits.append(rc)
    elif sim_commits:
        latest = sim_commits[0]
        for sc in sim_commits:
            if sc.get("hash", "") == last_commit_hash:
                break
            new_commits.append(sc)

    # Get changed files for latest commit
    changed_files = []
    if real_commits:
        changed_files = get_real_changed_files(real_commits[0]["hash"])
    elif sim_commits and sim_commits[0].get("changed_files"):
        changed_files = sim_commits[0]["changed_files"]

    return {
        "latest_commit":  latest,
        "new_commits":    new_commits,
        "changed_files":  changed_files,
        "all_commits":    real_commits or sim_commits,
        "has_changes":    len(new_commits) > 0,
        "is_real_git":    bool(real_commits),
    }

def infer_jira_ticket(commit_msg: str, jira_tickets: list) -> str:
    """Try to infer which Jira ticket a commit relates to."""
    # Direct ticket ID in message (e.g., KS-123 or KANI-42)
    match = re.search(r'\b([A-Z]+-\d+)\b', commit_msg)
    if match:
        return match.group(1)

    # Keyword matching
    msg_lower = commit_msg.lower()
    for ticket in jira_tickets:
        title_words = set(ticket.get("title", "").lower().split())
        msg_words   = set(msg_lower.split())
        overlap = title_words & msg_words
        meaningful = {w for w in overlap if len(w) > 4}
        if len(meaningful) >= 2:
            return ticket.get("id", "")

    return "Unknown (no ticket linked)"

def print_github_summary(gh_result: dict, jira_tickets: list):
    """Print Latest GitHub Commit Summary block."""
    section("LATEST GITHUB COMMIT SUMMARY", "🐙")

    latest = gh_result.get("latest_commit")
    is_real = gh_result.get("is_real_git", False)

    label = c("[Real Git]", "green") if is_real else c("[Simulated]", "yellow")
    print(f"  Source: {label}")

    if not latest:
        warn("No commits found — check jira_state.json or ensure git is initialized")
        return

    if gh_result.get("has_changes"):
        status(f"{len(gh_result['new_commits'])} new commit(s) since last run", "🆕", "green")
    else:
        status("No new commits since last run", "✓", "green")

    # Latest commit card
    print(f"\n  {c('Latest Commit:', 'bold')}")
    print(f"  {'Hash':<10} {c(latest.get('hash', '?'), 'cyan')}")
    print(f"  {'Author':<10} {latest.get('author', latest.get('name', '?'))}")
    print(f"  {'Date':<10} {c(latest.get('date', '?'), 'dim')}")
    print(f"  {'Message':<10} {c(latest.get('message', '?'), 'white')}")

    ticket_ref = infer_jira_ticket(latest.get("message", ""), jira_tickets)
    if ticket_ref and ticket_ref != "Unknown (no ticket linked)":
        print(f"  {'→ Ticket':<10} {c(ticket_ref, 'cyan')}")
    else:
        print(f"  {'→ Ticket':<10} {c('No direct ticket link found', 'dim')}")

    # Changed files
    changed_files = gh_result.get("changed_files", [])
    if changed_files:
        print(f"\n  {c('Changed Files:', 'bold')}")
        for f in changed_files[:15]:
            icon = {"modified": "✏️", "added": "➕", "deleted": "🗑️"}.get(f["status"], "📄")
            print(f"    {icon}  {f['path']}  {c(f['status'], 'dim')}")
        if len(changed_files) > 15:
            print(f"    … {len(changed_files) - 15} more files")

    # Recent commit log
    all_commits = gh_result.get("all_commits", [])
    if len(all_commits) > 1:
        print(f"\n  {c('Recent History:', 'bold')}")
        for cm in all_commits[1:6]:
            msg = cm.get("message", "")[:55]
            h   = cm.get("hash", "?")
            print(f"    {c(h, 'dim')}  {msg}")

# ──────────────────────────────────────────────
# Code Impact Analysis (Real git diff)
# ──────────────────────────────────────────────

def get_uncommitted_diff() -> str:
    """Get the full diff of uncommitted changes in Kani-Store."""
    try:
        staged = subprocess.run(
            ["git", "-C", PROJECT_ROOT, "diff", "--cached"],
            capture_output=True, text=True, timeout=15
        ).stdout
        unstaged = subprocess.run(
            ["git", "-C", PROJECT_ROOT, "diff"],
            capture_output=True, text=True, timeout=15
        ).stdout
        return staged + "\n" + unstaged
    except Exception:
        return ""

def get_changed_files_with_status() -> list[dict]:
    """Get ALL changed files (uncommitted) in Kani-Store."""
    try:
        result = subprocess.run(
            ["git", "-C", PROJECT_ROOT, "status", "--porcelain"],
            capture_output=True, text=True, timeout=15
        )
        files = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            status_code = line[:2].strip()
            filepath = line[3:].strip()
            status_map = {
                "M": "modified", "A": "added", "D": "deleted",
                "R": "renamed", "?": "untracked", "MM": "modified",
            }
            files.append({
                "path":   filepath,
                "status": status_map.get(status_code[0], "changed"),
            })
        return files
    except Exception:
        return []

def resolve_impact(changed_paths: list[str]) -> dict:
    """
    Compute blast radius for the Kani-Store dependency graph.
    Returns impacted modules and risk level.
    """
    directly_changed  = set()
    indirectly_impacted = set()
    risk_score = 0

    # Normalize paths (basename for matching)
    for path in changed_paths:
        basename = os.path.basename(path)
        rel_path = path.replace("\\", "/")
        # Match against known modules
        for module, deps in KANI_MODULES.items():
            if basename == os.path.basename(module) or rel_path.endswith(module):
                directly_changed.add(module)
                if module in CRITICAL_FILES:
                    risk_score += 3
                else:
                    risk_score += 1

    # Propagate: find modules that depend ON the changed files
    for changed_mod in list(directly_changed):
        for module, deps in KANI_MODULES.items():
            if module not in directly_changed:
                for dep in deps:
                    if dep == changed_mod or os.path.basename(dep) == os.path.basename(changed_mod):
                        indirectly_impacted.add(module)
                        risk_score += 0.5

    # Risk level
    if risk_score >= 5:
        risk = "HIGH"
    elif risk_score >= 2:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    return {
        "directly_changed":     list(directly_changed),
        "indirectly_impacted":  list(indirectly_impacted),
        "risk_level":           risk,
        "risk_score":           round(risk_score, 1),
    }

def parse_diff_for_functions(diff_text: str) -> list[str]:
    """Extract function/component names from a diff."""
    patterns = [
        r"^[+\-].*(?:const|function|class|export)\s+(\w+)",
        r"^[+\-].*(\w+)\s*=\s*(?:\(|async)",
        r"^[+\-].*(?:interface|type)\s+(\w+)",
    ]
    found = set()
    for line in diff_text.split("\n"):
        for pat in patterns:
            m = re.search(pat, line)
            if m:
                name = m.group(1)
                if len(name) > 2 and not name.startswith("_"):
                    found.add(name)
    return list(found)[:20]

def analyze_code_impact() -> dict:
    """Full code impact analysis on Kani-Store uncommitted changes."""
    changed_files = get_changed_files_with_status()
    diff_text     = get_uncommitted_diff()

    if not changed_files and not diff_text.strip():
        return {
            "has_changes":    False,
            "changed_files":  [],
            "impact":         {},
            "diff_summary":   "",
            "functions_changed": [],
        }

    changed_paths = [f["path"] for f in changed_files]
    impact        = resolve_impact(changed_paths)
    funcs         = parse_diff_for_functions(diff_text)

    # Build a short diff summary (first 2000 chars)
    diff_summary = ""
    if diff_text.strip():
        lines = diff_text.strip().split("\n")
        added   = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
        diff_summary = f"+{added} lines added, -{removed} lines removed"

    return {
        "has_changes":       len(changed_files) > 0,
        "changed_files":     changed_files,
        "impact":            impact,
        "diff_summary":      diff_summary,
        "functions_changed": funcs,
        "diff_text":         diff_text[:3000] if diff_text else "",
    }

def print_code_impact(code_result: dict, jira_tickets: list):
    """Print Code Change Impact Analysis block."""
    section("CODE CHANGE IMPACT ANALYSIS", "⚡")

    if not code_result.get("has_changes"):
        status("No uncommitted changes detected in Kani-Store", "✓", "green")
        return

    changed = code_result.get("changed_files", [])
    impact  = code_result.get("impact", {})
    risk    = impact.get("risk_level", "UNKNOWN")

    # Risk badge
    risk_display = {
        "HIGH":   c("🔴  HIGH RISK", "red"),
        "MEDIUM": c("🟡  MEDIUM RISK", "yellow"),
        "LOW":    c("🟢  LOW RISK", "green"),
    }.get(risk, c(risk, "dim"))

    _score = impact.get("risk_score", 0)
    print(f"\n  Risk Level: {risk_display}  {c(f'(score: {_score})', 'dim')}")
    print(f"  Diff:       {c(code_result.get('diff_summary', 'N/A'), 'dim')}")

    # What changed
    print(f"\n  {c('What Changed:', 'bold')}")
    for f in changed[:20]:
        icon = {"modified": "✏️", "added": "➕", "deleted": "🗑️", "untracked": "🆕"}.get(f["status"], "📄")
        is_crit = os.path.basename(f["path"]) in {os.path.basename(k) for k in CRITICAL_FILES}
        marker = c(" ← CRITICAL FILE", "red") if is_crit else ""
        print(f"    {icon}  {f['path']}{marker}")

    # Functions changed
    funcs = code_result.get("functions_changed", [])
    if funcs:
        print(f"\n  {c('Functions/Components Modified:', 'bold')}")
        for fn in funcs:
            print(f"    • {c(fn, 'cyan')}")

    # Impact propagation
    print(f"\n  {c('Affected Modules:', 'bold')}")
    for m in impact.get("directly_changed", []):
        print(f"    {c('● Direct', 'red')}      {m}")
    for m in impact.get("indirectly_impacted", []):
        print(f"    {c('○ Indirect', 'yellow')}    {m}")

    # Reason why it matters
    print(f"\n  {c('Why It Matters:', 'bold')}")
    _explain_impact(impact, changed)

def _explain_impact(impact: dict, changed_files: list):
    """Generate human-readable impact explanation."""
    direct = impact.get("directly_changed", [])
    indirect = impact.get("indirectly_impacted", [])

    explanations = {
        "App.tsx":           "Core UI — all pages, routing, and state management live here. Any change affects the entire frontend.",
        "types.ts":          "Shared type definitions — changes here can break ALL modules that import these interfaces.",
        "constants.ts":      "Product catalog and mock data — changes affect product listings, cart, and orders.",
        "services/geminiService.ts": "AI/Gemini integration — changes affect chatbot and AI-powered features.",
        "components/Icons.tsx": "Shared icon components — changes affect UI rendering across pages.",
        "index.tsx":         "App entry point — only impacts initial render.",
        "vite.config.ts":    "Build config — affects bundling, dev server, and production builds.",
        "package.json":      "Dependencies — can break builds or introduce security issues.",
    }

    for mod in direct:
        if mod in explanations:
            print(f"    {c('→', 'red')} {c(mod, 'cyan')}: {explanations[mod]}")

    for mod in indirect:
        if mod in explanations:
            print(f"    {c('→', 'yellow')} {c(mod, 'cyan')}: Indirectly affected because it imports from changed modules.")

# ──────────────────────────────────────────────
# Recommendations
# ──────────────────────────────────────────────

def print_recommendations(jira_result: dict, gh_result: dict, code_result: dict):
    """Print unified recommendations based on all 3 analyses."""
    section("RECOMMENDATIONS", "💡")

    recs = []
    impact = code_result.get("impact", {})
    risk   = impact.get("risk_level", "LOW")

    # Code-based recommendations
    if code_result.get("has_changes"):
        if risk == "HIGH":
            recs.append(("🔴", "HIGH RISK change detected — run full test suite before committing"))
            recs.append(("🔴", "Check all pages in browser: Home, Cart, Orders, Profile, Admin"))
        if "types.ts" in impact.get("directly_changed", []):
            recs.append(("⚠️", "types.ts changed — verify CartItem, Product, Order interfaces are backward-compatible"))
        if "constants.ts" in impact.get("directly_changed", []):
            recs.append(("⚠️", "constants.ts changed — check PRODUCTS array for required fields (id, name, price, stock)"))
        if "services/geminiService.ts" in impact.get("directly_changed", []):
            recs.append(("🤖", "geminiService.ts changed — test Gemini AI chat feature end-to-end"))
        if "App.tsx" in impact.get("directly_changed", []):
            recs.append(("🖥️", "App.tsx changed — test navigation, state management, and all route transitions"))

    # Jira-based recommendations
    for t in jira_result.get("new_tickets", []):
        priority = t.get("priority", "").lower()
        if priority in ("critical", "blocker", "high"):
            recs.append(("🎫", f"HIGH-PRIORITY Jira ticket {t['id']}: '{t['title'][:50]}' — needs immediate attention"))

    for sc in jira_result.get("status_changes", []):
        if sc.get("to", "").lower() in ("in review", "done", "closed"):
            recs.append(("✅", f"{sc['id']} moved to '{sc['to']}' — ensure PR/code is linked"))

    # GitHub-based recommendations
    if gh_result.get("has_changes"):
        recs.append(("🔄", "New commits detected — sync your local branch: git pull"))

    # Generic best practices
    if not recs:
        recs.append(("✅", "Everything looks good — no critical changes detected"))
        recs.append(("💡", "Run 'npm run dev' to verify the app starts correctly"))

    recs.append(("📝", "After changes, update jira_state.json to mark tickets In Progress"))
    recs.append(("🧪", "Test checklist: Product listing → Add to cart → Checkout → Orders page"))

    for icon, text in recs:
        print(f"  {icon}  {text}")

# ──────────────────────────────────────────────
# Ollama AI Deep Analysis (optional)
# ──────────────────────────────────────────────

def check_ollama() -> bool:
    """Check if Ollama is running."""
    try:
        import urllib.request
        r = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
        return r.status == 200
    except Exception:
        return False

def run_ai_analysis(code_result: dict, jira_result: dict, gh_result: dict):
    """Run deep AI analysis via Ollama if available."""
    section("AI DEEP ANALYSIS (Ollama)", "🤖")

    if not check_ollama():
        warn("Ollama not running — skipping AI analysis")
        print(f"  {c('→ To enable:', 'dim')} ollama serve  (then: ollama pull mistral)")
        return

    # Build diff context
    diff = code_result.get("diff_text", "")[:2000] or "(no uncommitted changes)"
    changed_files = [f["path"] for f in code_result.get("changed_files", [])]

    jira_context = ""
    for t in jira_result.get("all_tickets", [])[:3]:
        jira_context += f"  - {t['id']}: {t['title']} [{t.get('status','')}]\n"

    commit = gh_result.get("latest_commit") or {}
    commit_context = f"{commit.get('hash','?')} — {commit.get('message','?')}"

    prompt = f"""You are an AI engineering assistant for a React/TypeScript e-commerce project called Kani-Store.

Project structure:
- App.tsx (main UI, 71KB — contains ALL pages: Home, Products, Cart, Orders, Profile, Admin)
- types.ts (shared interfaces: Product, CartItem, Order, Address, ChatMessage)
- constants.ts (PRODUCTS array, CATEGORIES, mock data)
- services/geminiService.ts (Gemini AI integration)
- components/Icons.tsx (SVG icons)

Current Jira tickets:
{jira_context or "  (none)"}

Latest GitHub commit:
  {commit_context}

Uncommitted code changes:
  Files: {', '.join(changed_files) if changed_files else 'none'}
  Diff (excerpt):
{diff}

Please provide a concise analysis in EXACTLY this format:

What Changed:
  → [specific description]

Root Cause / Purpose:
  → [why this change exists]

Impacted Modules:
  → [list each file and why]

Risk Level: [LOW / MEDIUM / HIGH]
  → [justification]

Suggested Tests:
  → [specific things to manually test]

Recommended Next Steps:
  → [1-3 actionable items]
"""

    try:
        import urllib.request
        import json as _json

        payload = _json.dumps({
            "model": DEFAULT_MODEL,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": 0.2, "num_predict": 800},
        }).encode()

        req = urllib.request.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        print()
        with urllib.request.urlopen(req, timeout=120) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if line:
                    try:
                        chunk = _json.loads(line)
                        print(chunk.get("response", ""), end="", flush=True)
                        if chunk.get("done"):
                            break
                    except Exception:
                        pass
        print("\n")

    except Exception as e:
        warn(f"Ollama analysis failed: {e}")

# ──────────────────────────────────────────────
# Save Output
# ──────────────────────────────────────────────

def save_output(content: str):
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTPUTS_DIR, f"kani_analysis_{ts}.txt")
    # Strip ANSI codes for file
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    clean = ansi_escape.sub("", content)
    with open(path, "w", encoding="utf-8") as f:
        f.write(clean)
    status(f"Report saved → {c(path, 'cyan')}", "💾")

# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def run_analysis(args):
    """Run the full Kani-Store analysis pipeline."""
    import io as _io

    # Tee: stream to terminal and capture simultaneously
    captured = _io.StringIO()
    _orig_write = sys.stdout.write

    def _tee(text):
        _orig_write(text)
        captured.write(text)

    sys.stdout.write = _tee  # type: ignore[method-assign]

    print_banner()

    last_state = load_last_state()

    # ── Jira Analysis
    jira_result = {"all_tickets": [], "has_changes": False, "new_tickets": [],
                   "status_changes": [], "comment_additions": [], "description_updates": []}
    if not args.github and not args.code:
        jira_result = analyze_jira_updates(last_state)
        print_jira_summary(jira_result)

    # ── GitHub Analysis  
    gh_result = {"latest_commit": None, "has_changes": False, "changed_files": [],
                 "all_commits": [], "is_real_git": False, "new_commits": []}
    if not args.jira and not args.code:
        gh_result = analyze_github_updates(last_state)
        jira_tickets = jira_result.get("all_tickets", [])
        print_github_summary(gh_result, jira_tickets)

    # ── Code Impact Analysis
    code_result = {"has_changes": False, "changed_files": [], "impact": {},
                   "diff_summary": "", "functions_changed": [], "diff_text": ""}
    if not args.jira and not args.github:
        code_result = analyze_code_impact()
        jira_tickets = jira_result.get("all_tickets", [])
        print_code_impact(code_result, jira_tickets)

    # ── Affected Modules (aggregated)
    if not (args.jira or args.github or args.code):
        section("AFFECTED MODULES (AGGREGATED)", "[MAP]")
        impact = code_result.get("impact", {})
        all_affected = set(
            impact.get("directly_changed", []) +
            impact.get("indirectly_impacted", [])
        )
        gh_files = {f["path"] for f in gh_result.get("changed_files", [])}
        if all_affected or gh_files:
            print(f"\n  {'Module':<35} {'Type':<15} {'Risk'}")
            print(c("  " + "-" * 65, "dim"))
            for mod in sorted(all_affected):
                mod_risk = "CRITICAL" if mod in CRITICAL_FILES else "Standard"
                etype = "Direct change" if mod in impact.get("directly_changed", []) else "Impacted"
                risk_c = c(mod_risk, "red") if mod_risk == "CRITICAL" else c(mod_risk, "dim")
                print(f"  {c(mod, 'cyan'):<44} {etype:<15} {risk_c}")
            for path in sorted(gh_files):
                if path not in str(all_affected):
                    print(f"  {c(path, 'blue'):<44} {'Commit file':<15} {c('Needs review', 'yellow')}")
        else:
            status("No modules currently affected", "OK", "green")

    # ── Recommendations
    if not (args.jira or args.github or args.code):
        print_recommendations(jira_result, gh_result, code_result)

    # ── AI Deep Analysis (optional)
    if args.ai and not (args.jira or args.github or args.code):
        run_ai_analysis(code_result, jira_result, gh_result)

    # ── Save state for next run
    new_state = {
        "jira_tickets":     jira_result.get("all_tickets", []),
        "last_commit_hash": (gh_result.get("latest_commit") or {}).get("hash", ""),
        "last_run":         datetime.now().isoformat(),
    }
    save_state(new_state)

    print(f"\n{c('  ' + '=' * 56, 'dim')}")
    status(f"Analysis complete at {datetime.now().strftime('%H:%M:%S')}", "[DONE]", "green")
    print()

    # ── finalize tee and save captured output
    sys.stdout.write = _orig_write  # type: ignore[method-assign]
    save_output(captured.getvalue())


def parse_args():
    parser = argparse.ArgumentParser(
        description="Kani-Store Local AI Engineering Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python kani_agent.py              Full analysis
  python kani_agent.py --jira      Jira updates only
  python kani_agent.py --github    GitHub commits only
  python kani_agent.py --code      Code impact only
  python kani_agent.py --ai        Full + AI deep analysis
  python kani_agent.py --watch     Watch mode (runs every 60s)
        """
    )
    parser.add_argument("--jira",   action="store_true", help="Only show Jira updates")
    parser.add_argument("--github", action="store_true", help="Only show GitHub commits")
    parser.add_argument("--code",   action="store_true", help="Only show code impact")
    parser.add_argument("--ai",     action="store_true", help="Enable Ollama AI deep analysis")
    parser.add_argument("--watch",  action="store_true", help="Watch mode — re-run every 60 seconds")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.watch:
        print(c("\n  👁️  Watch mode enabled — running every 60 seconds (Ctrl+C to stop)\n", "cyan"))
        try:
            while True:
                os.system("cls" if os.name == "nt" else "clear")
                run_analysis(args)
                print(c(f"\n  ⏳  Next check in 60s...", "dim"))
                time.sleep(60)
        except KeyboardInterrupt:
            print(c("\n\n  Stopped.\n", "dim"))
    else:
        run_analysis(args)


if __name__ == "__main__":
    main()
