"""
Kani-Store Smart Engineering Agent
=====================================
An autonomous code-review agent that connects Git commits with Jira tickets,
detects breaking changes, traces ripple effects across all layers, and flags
incomplete or inconsistent implementations.

Four pillars:
  1. COMMIT ANALYSIS       — detect failures / breaking changes per commit
  2. JIRA COMPLETENESS     — validate every ticket has matching code changes
  3. RIPPLE EFFECT ENGINE  — trace how changes propagate across all layers
  4. FAILURE INSIGHT       — explain root cause + corrective actions via AI

Supports both simulated data (json files) and real git + Jira/GitHub APIs.

Usage:
  python kani_agent.py             # full analysis (all 4 pillars)
  python kani_agent.py --jira      # Jira-only
  python kani_agent.py --github    # GitHub-only
  python kani_agent.py --code      # code diff only
  python kani_agent.py --ai        # include Ollama AI deep-analysis
  python kani_agent.py --commit abc1234   # analyze specific commit
  python kani_agent.py --watch     # continuous watch mode (re-runs on change)
"""

from __future__ import annotations

import sys, os, io, re, json, hashlib, time, subprocess, argparse, textwrap
from datetime import datetime
from typing import Any

# Fix Windows console encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ─────────────────────────────────────────────────────────────────
# Paths & config
# ─────────────────────────────────────────────────────────────────

AGENT_DIR    = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(AGENT_DIR, ".."))

JIRA_STATE_FILE   = os.path.join(AGENT_DIR, "jira_state.json")
GITHUB_STATE_FILE = os.path.join(AGENT_DIR, "github_state.json")
LAST_STATE_FILE   = os.path.join(AGENT_DIR, ".last_state.json")
OUTPUTS_DIR       = os.path.join(AGENT_DIR, "outputs")

OLLAMA_URL    = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "mistral"

# ─────────────────────────────────────────────────────────────────
# Kani-Store dependency graph (layered architecture)
# ─────────────────────────────────────────────────────────────────

# Full dependency map: file → files it imports from
KANI_DEPS: dict[str, list[str]] = {
    "index.tsx":                    ["App.tsx"],
    "App.tsx":                      ["types.ts", "constants.ts",
                                     "services/geminiService.ts",
                                     "components/Icons.tsx"],
    "constants.ts":                 ["types.ts"],
    "services/geminiService.ts":    ["types.ts"],
    "components/Icons.tsx":         [],
    "types.ts":                     [],
    "index.html":                   ["index.tsx"],
    "vite.config.ts":               [],
    "package.json":                 [],
    "tsconfig.json":                [],
    "utils/csvParser.ts":           ["types.ts"],
}

# Layer model: each layer feeds the next
LAYERS = {
    "L1_UI":       ["App.tsx", "components/Icons.tsx", "index.tsx", "index.html"],
    "L2_TYPES":    ["types.ts"],
    "L3_DATA":     ["constants.ts", "utils/csvParser.ts"],
    "L4_SERVICES": ["services/geminiService.ts"],
    "L5_CONFIG":   ["vite.config.ts", "tsconfig.json", "package.json"],
}

LAYER_LABELS = {
    "L1_UI":       "Frontend / UI Components",
    "L2_TYPES":    "Type Contracts (TypeScript interfaces)",
    "L3_DATA":     "Data / Constants / Mock DB",
    "L4_SERVICES": "Service Layer / External APIs",
    "L5_CONFIG":   "Build Config / Dependencies",
}

CRITICAL_FILES = {"App.tsx", "types.ts", "constants.ts", "services/geminiService.ts"}

# ─────────────────────────────────────────────────────────────────
# Jira ticket → expected code layers
# ─────────────────────────────────────────────────────────────────

TICKET_KEYWORD_LAYERS: list[tuple[list[str], list[str], str]] = [
    (["type", "interface", "schema", "model", "field", "remove field",
      "add field", "phone", "email", "address"],
     ["types.ts"],
     "Schema/type change → types.ts MUST be updated"),

    (["product", "catalog", "price", "stock", "category", "mock data",
      "products array", "recommendation"],
     ["constants.ts", "types.ts"],
     "Product data change → constants.ts + types.ts MUST be updated"),

    (["cart", "checkout", "order", "payment", "quantity", "persist",
      "localstorage"],
     ["App.tsx", "types.ts"],
     "Cart/Order flow → App.tsx + types.ts MUST be updated"),

    (["ui", "component", "design", "layout", "page", "gallery", "zoom",
      "image", "icon", "button", "form"],
     ["App.tsx"],
     "UI change → App.tsx MUST be updated"),

    (["ai", "gemini", "chatbot", "recommendation", "service", "api"],
     ["services/geminiService.ts", "types.ts"],
     "AI/service change → geminiService.ts + types.ts MUST be updated"),

    (["admin", "import", "csv", "bulk", "upload"],
     ["App.tsx", "utils/csvParser.ts", "types.ts"],
     "Admin/import change → App.tsx + csvParser.ts + types.ts required"),

    (["performance", "lazy", "memo", "virtual", "paginate"],
     ["App.tsx", "constants.ts"],
     "Performance change → App.tsx + constants.ts to check"),

    (["dependency", "package", "upgrade", "version"],
     ["package.json"],
     "Dependency change → package.json MUST be updated"),
]

# Breaking-change pattern detectors (applied to diff text)
BREAKING_PATTERNS: list[tuple[str, str, str]] = [
    (r"^-\s*(interface|type)\s+(\w+)",
     "Interface/type REMOVED or renamed",
     "All files importing this type will break. Check all imports."),

    (r"^-\s+(\w+)\s*[?:]",
     "Field REMOVED from interface",
     "Any code accessing this field will throw a runtime error."),

    (r"^-\s*export\s+(const|function|class|default)\s+(\w+)",
     "Exported symbol REMOVED",
     "All importers of this symbol will fail to compile."),

    (r"^-\s*import\s+.*from",
     "Import REMOVED",
     "Dependency removed — verify nothing else needs it."),

    (r"^\+\s*(interface|type)\s+(\w+)",
     "New interface/type ADDED",
     "Ensure all layers that use this type are updated consistently."),

    (r"^\+\s+(\w+)\s*[?:]",
     "New field ADDED to interface",
     "Ensure constants.ts mock data and App.tsx are updated to include this field."),

    (r"localStorage\.(remove|clear)",
     "localStorage cleared/removed",
     "Cart/session persistence may be broken — test page reload behaviour."),

    (r"(delete|DROP|ALTER|TRUNCATE)\s+\w+",
     "Destructive data operation detected",
     "Verify data integrity and ensure backups exist."),

    (r"password|secret|token|api_key|apikey",
     "Possible credential in diff",
     "SECURITY: Ensure no secrets are committed. Use environment variables."),
]

# ─────────────────────────────────────────────────────────────────
# ANSI colour helpers
# ─────────────────────────────────────────────────────────────────

C = {
    "reset":   "\033[0m",  "bold":  "\033[1m",  "dim":    "\033[2m",
    "red":     "\033[91m", "green": "\033[92m",  "yellow": "\033[93m",
    "blue":    "\033[94m", "magenta": "\033[95m","cyan":   "\033[96m",
    "white":   "\033[97m",
}

def col(t: str, c: str) -> str:
    return f"{C.get(c,'')}{t}{C['reset']}"

def section(title: str, icon: str = "▸"):
    print(f"\n{col(f'  {icon}  {title}', 'bold')}")
    print(col("  " + "─" * 60, "dim"))

def ok(msg: str):   print(f"  {col('✓', 'green')} {msg}")
def info(msg: str): print(f"  {col('·', 'cyan')} {msg}")
def warn(msg: str): print(f"  {col('⚠', 'yellow')} {col(msg, 'yellow')}")
def err(msg: str):  print(f"  {col('✖', 'red')} {col(msg, 'red')}")
def flag(msg: str): print(f"  {col('⚑', 'magenta')} {col(msg, 'magenta')}")

def risk_badge(level: str) -> str:
    return {
        "CRITICAL": col("CRITICAL", "red"),
        "HIGH":     col("HIGH",     "red"),
        "MEDIUM":   col("MEDIUM",   "yellow"),
        "LOW":      col("LOW",      "green"),
    }.get(level, col(level, "dim"))

def priority_col(p: str) -> str:
    p = str(p).strip()
    if any(x in p for x in ("Critical", "Blocker")): return col(p, "red")
    if "High"   in p: return col(p, "yellow")
    if "Medium" in p: return col(p, "blue")
    return col(p, "dim")

# ─────────────────────────────────────────────────────────────────
# State management
# ─────────────────────────────────────────────────────────────────

def load_last_state() -> dict:
    if os.path.exists(LAST_STATE_FILE):
        with open(LAST_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_state(state: dict):
    with open(LAST_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def file_hash(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

# ─────────────────────────────────────────────────────────────────
# PILLAR 1 — Commit Analysis
# ─────────────────────────────────────────────────────────────────

def git_run(args: list[str], cwd: str = PROJECT_ROOT) -> str:
    """Run a git command and return stdout."""
    try:
        r = subprocess.run(["git", "-C", cwd] + args,
                           capture_output=True, text=True, timeout=20)
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""

def get_real_commits(n: int = 15) -> list[dict]:
    raw = git_run(["log", f"-{n}", "--pretty=format:%H|%an|%ae|%ai|%s"])
    commits = []
    for line in raw.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("|", 4)
        if len(parts) == 5:
            commits.append({
                "hash": parts[0][:10], "full_hash": parts[0],
                "author": parts[1], "email": parts[2],
                "date": parts[3][:19], "message": parts[4],
                "source": "real",
            })
    return commits

def get_commit_diff(commit_hash: str) -> str:
    """Get the full diff introduced by a commit."""
    diff = git_run(["show", "--no-color", commit_hash])
    return diff[:6000] if diff else ""

def get_commit_files(commit_hash: str) -> list[dict]:
    raw = git_run(["diff-tree", "--no-commit-id", "-r", "--name-status", commit_hash])
    files = []
    for line in raw.strip().split("\n"):
        parts = line.split("\t", 1)
        if len(parts) == 2:
            status_map = {"M": "modified", "A": "added", "D": "deleted",
                          "R": "renamed", "C": "copied"}
            files.append({"status": status_map.get(parts[0][0], "changed"),
                          "path": parts[1]})
    return files

def get_uncommitted_diff() -> str:
    staged   = git_run(["diff", "--cached"]) or ""
    unstaged = git_run(["diff"]) or ""
    return (staged + "\n" + unstaged).strip()

def get_uncommitted_files() -> list[dict]:
    raw = git_run(["status", "--porcelain"]) or ""
    files = []
    for line in raw.strip().split("\n"):
        if not line.strip():
            continue
        code = line[:2].strip()
        path = line[3:].strip()
        sm = {"M": "modified", "A": "added", "D": "deleted",
              "R": "renamed", "?": "untracked"}
        files.append({"path": path, "status": sm.get(code[0] if code else "?", "changed")})
    return files

def infer_ticket_id(msg: str, tickets: list[dict]) -> str:
    m = re.search(r'\b([A-Z]+-\d+)\b', msg)
    if m:
        return m.group(1)
    msg_lower = msg.lower()
    for t in tickets:
        words = set(t.get("title", "").lower().split())
        overlap = {w for w in words if len(w) > 4 and w in msg_lower}
        if len(overlap) >= 2:
            return t["id"]
    return ""

def detect_breaking_changes(diff_text: str) -> list[dict]:
    """Scan diff for patterns that indicate breaking changes."""
    findings = []
    for pattern, label, guidance in BREAKING_PATTERNS:
        matches = re.findall(pattern, diff_text, re.MULTILINE | re.IGNORECASE)
        if matches:
            match_examples = [str(m) for m in matches[:3]]
            findings.append({
                "pattern": label,
                "guidance": guidance,
                "examples": match_examples,
            })
    return findings

def score_commit_health(commit: dict, diff_text: str,
                        changed_files: list[dict],
                        tickets: list[dict]) -> dict:
    """Score a commit 0-100; return grade, issues, and breaking change list."""
    issues: list[str] = []
    score = 100

    ticket_id = infer_ticket_id(commit.get("message", ""), tickets)
    if not ticket_id:
        issues.append("No Jira ticket linked in commit message")
        score -= 20
    commit["_ticket_id"] = ticket_id

    breaking = detect_breaking_changes(diff_text)
    for b in breaking:
        if "credential" in b["pattern"].lower():
            issues.append(f"SECURITY — {b['pattern']}: {b['guidance']}")
            score -= 30
        else:
            issues.append(f"Breaking change — {b['pattern']}: {b['guidance']}")
            score -= 15

    paths = [f["path"] for f in changed_files]
    if any("App.tsx" in p for p in paths) and not any("types.ts" in p for p in paths):
        issues.append("App.tsx modified but types.ts unchanged — verify no new types needed")
        score -= 5

    if any("types.ts" in p for p in paths) and not any("constants.ts" in p for p in paths):
        issues.append("types.ts changed but constants.ts not updated — mock data may be stale")
        score -= 5

    if any("package.json" in p for p in paths) and not any(
            "package-lock" in p or "yarn.lock" in p for p in paths):
        issues.append("package.json changed but no lock-file update — run npm install")
        score -= 10

    lines = diff_text.count("\n")
    if lines > 400:
        issues.append(f"Very large diff ({lines} lines) — consider splitting commits")
        score -= 10

    score = max(0, score)
    grade = ("A" if score >= 85 else "B" if score >= 70 else
             "C" if score >= 50 else "D" if score >= 30 else "F")

    return {"score": score, "grade": grade, "issues": issues,
            "breaking": breaking, "ticket_id": ticket_id}

def analyze_commits(target_hash: str | None, tickets: list[dict]) -> dict:
    """Analyze recent commits (or one specific commit) for health + breaking changes."""
    real_commits = get_real_commits(10)
    sim_state    = _load_json(GITHUB_STATE_FILE)
    sim_commits  = sim_state.get("commits", [])

    commits = real_commits if real_commits else sim_commits
    if not commits:
        return {"commits": [], "has_real_git": False, "summary": "No commits found"}

    results = []
    for i, cm in enumerate(commits[:6]):
        h = cm.get("full_hash") or cm.get("hash", "")
        if target_hash and not h.startswith(target_hash):
            continue

        if real_commits:
            diff_text = get_commit_diff(h)
            changed   = get_commit_files(h)
        else:
            diff_text = cm.get("diff", "")
            changed   = cm.get("changed_files", [])

        health      = score_commit_health(cm, diff_text, changed, tickets)
        prev_commit = commits[i + 1] if i + 1 < len(commits) else None

        results.append({
            "commit": cm, "diff_text": diff_text,
            "changed_files": changed, "health": health,
            "prev_commit": prev_commit, "index": i,
        })

    return {"commits": results, "has_real_git": bool(real_commits),
            "total_analyzed": len(results)}

def print_commit_analysis(data: dict):
    section("COMMIT ANALYSIS  —  Health Scores & Breaking Changes", ">>")
    src = col("[Real Git]", "green") if data.get("has_real_git") else col("[Simulated]", "yellow")
    info(f"Source: {src}  |  Analyzed: {data.get('total_analyzed', 0)} commits")

    for item in data.get("commits", []):
        cm     = item["commit"]
        health = item["health"]
        score  = health["score"]
        grade  = health["grade"]
        grade_col = ("green" if grade == "A" else
                     "cyan"  if grade == "B" else
                     "yellow" if grade == "C" else "red")

        print(f"\n  {'─'*58}")
        print(f"  {col(cm.get('hash','?'), 'cyan')}  {cm.get('date','')}")
        msg = cm.get("message", "")[:72]
        print(f"  {col(msg, 'white')}")
        print(f"  Author: {cm.get('author','?')}  |  "
              f"Score: {col(str(score), grade_col)}/100  Grade: {col(grade, grade_col)}")

        tid = health.get("ticket_id")
        if tid:
            print(f"  Jira: {col(tid, 'cyan')}")
        else:
            warn("No Jira ticket linked")

        cf = item.get("changed_files", [])
        if cf:
            icons = {"modified": "~", "added": "+", "deleted": "-", "renamed": ">"}
            for f in cf[:8]:
                ic   = icons.get(f["status"], ".")
                crit = col(" [CRITICAL]", "red") if os.path.basename(f["path"]) in CRITICAL_FILES else ""
                print(f"    {ic} {f['path']}{crit}")
            if len(cf) > 8:
                print(f"    ... {len(cf)-8} more files")

        for b in health.get("breaking", []):
            print(f"\n  {col('[BREAKING]', 'red')} {b['pattern']}")
            print(f"    Guidance : {b['guidance']}")
            if b.get("examples"):
                print(f"    Examples : {', '.join(str(x) for x in b['examples'][:2])}")

        for issue in health.get("issues", []):
            if issue.startswith("SECURITY"):
                err(issue)
            else:
                warn(issue)

        prev = item.get("prev_commit")
        if prev and health.get("breaking"):
            print(f"\n  {col('Compared to previous commit:', 'bold')}")
            print(f"    Prev: {col(prev.get('hash','?'),'dim')}  {prev.get('message','?')[:55]}")
            print(f"    {col('-> This commit introduced a regression vs previous commit.', 'red')}")


# ─────────────────────────────────────────────────────────────────
# PILLAR 2 — Jira Completeness Checker
# ─────────────────────────────────────────────────────────────────

def _load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_jira_tickets() -> list[dict]:
    return _load_json(JIRA_STATE_FILE).get("tickets", [])

def expected_files_for_ticket(ticket: dict) -> list[tuple[str, str]]:
    """Return (filename, reason) pairs that SHOULD be modified for this ticket."""
    text = " ".join([
        ticket.get("title", ""),
        ticket.get("description", ""),
        " ".join(ticket.get("labels", [])),
    ]).lower()

    required: dict[str, str] = {}
    for keywords, files, reason in TICKET_KEYWORD_LAYERS:
        if any(kw in text for kw in keywords):
            for f in files:
                if f not in required:
                    required[f] = reason
    return list(required.items())

def get_commits_for_ticket(ticket_id: str, commits: list[dict]) -> list[dict]:
    pattern = re.compile(r'\b' + re.escape(ticket_id) + r'\b', re.IGNORECASE)
    return [c for c in commits if pattern.search(c.get("message", ""))]

def check_ticket_completeness(ticket: dict, all_commits: list[dict]) -> dict:
    tid      = ticket["id"]
    expected = expected_files_for_ticket(ticket)
    linked   = get_commits_for_ticket(tid, all_commits)

    changed_paths: set[str] = set()
    for c in linked:
        for f in c.get("changed_files", []):
            changed_paths.add(os.path.basename(f["path"]))

    present, missing = [], []
    for fname, reason in expected:
        base = os.path.basename(fname)
        if base in changed_paths or fname in changed_paths:
            present.append((fname, reason))
        else:
            missing.append((fname, reason))

    total = len(expected)
    pct   = int(100 * len(present) / total) if total else 100

    status_label = ticket.get("status", "?")
    is_closed    = status_label.lower() in ("done", "closed", "resolved")

    risk = ("HIGH" if missing and is_closed else
            "MEDIUM" if missing else "LOW")

    return {
        "ticket": ticket, "expected": expected,
        "present": present, "missing": missing,
        "linked_commits": linked, "completeness_pct": pct,
        "risk": risk, "is_closed": is_closed,
    }

def analyze_jira_completeness(all_commits: list[dict]) -> list[dict]:
    return [check_ticket_completeness(t, all_commits) for t in load_jira_tickets()]

def print_jira_completeness(results: list[dict]):
    section("JIRA COMPLETENESS CHECK", ">>")
    if not results:
        warn("No tickets found in jira_state.json")
        return

    print(f"\n  {'ID':<10} {'Status':<14} {'Priority':<12} {'Done':<8} {'Risk':<8} Title")
    print(col("  " + "-" * 70, "dim"))
    for r in results:
        t   = r["ticket"]
        pct = r["completeness_pct"]
        pct_col = "green" if pct == 100 else "yellow" if pct >= 50 else "red"
        risk_c  = "red" if r["risk"] == "HIGH" else "yellow" if r["risk"] == "MEDIUM" else "green"
        print(f"  {col(t['id'],'cyan'):<19} {t.get('status','?'):<14} "
              f"{priority_col(t.get('priority','?')):<21} "
              f"{col(str(pct)+'%', pct_col):<19} "
              f"{col(r['risk'], risk_c):<19} "
              f"{t.get('title','')[:38]}")

    for r in results:
        t       = r["ticket"]
        missing = r["missing"]
        linked  = r["linked_commits"]
        if not missing and r["linked_commits"]:
            continue

        print(f"\n  {'─'*58}")
        print(f"  {col(t['id'], 'cyan')} — {t['title']}")
        print(f"  Status: {t.get('status','?')}  Priority: {priority_col(t.get('priority','?'))}  "
              f"Completeness: {r['completeness_pct']}%")

        if linked:
            print(f"\n  Linked commits ({len(linked)}):")
            for c in linked[:4]:
                print(f"    {col(c.get('hash','?'),'dim')}  {c.get('message','?')[:60]}")
        else:
            warn(f"No commits linked to {t['id']} — add ticket ID to commit messages")

        if r["present"]:
            print(f"\n  {col('Changed correctly:', 'green')}")
            for fname, _ in r["present"]:
                print(f"    {col('[OK]', 'green')} {fname}")

        if missing:
            print(f"\n  {col('MISSING changes:', 'red')}")
            for fname, reason in missing:
                print(f"    {col('[X]', 'red')} {fname}")
                print(f"      Reason: {col(reason, 'dim')}")
            if r["is_closed"]:
                flag(f"{t['id']} is CLOSED but missing code changes — may cause prod issues!")
            else:
                warn(f"{len(missing)} file(s) still need changes for {t['id']} to be complete")

        desc = t.get("description", "")
        if desc:
            print(f"\n  {col('Brief:', 'dim')} {desc[:160].replace(chr(10),' ')}")


# ─────────────────────────────────────────────────────────────────
# PILLAR 3 — Ripple Effect Engine
# ─────────────────────────────────────────────────────────────────

def resolve_blast_radius(changed_paths: list[str]) -> dict:
    """Compute full cross-layer ripple propagation for changed files."""
    directly: set[str] = set()
    for path in changed_paths:
        bn = os.path.basename(path)
        for mod in KANI_DEPS:
            if bn == os.path.basename(mod) or path.replace("\\", "/").endswith(mod):
                directly.add(mod)

    indirect: set[str] = set()
    queue = list(directly)
    while queue:
        current = queue.pop()
        for mod, deps in KANI_DEPS.items():
            if mod not in directly and mod not in indirect:
                dep_bases = {os.path.basename(d) for d in deps}
                if os.path.basename(current) in dep_bases:
                    indirect.add(mod)
                    queue.append(mod)

    def get_layer(fname: str) -> str:
        bn = os.path.basename(fname)
        for lid, files in LAYERS.items():
            if any(os.path.basename(f) == bn or fname == f for f in files):
                return lid
        return "UNKNOWN"

    score = sum(4 if m in CRITICAL_FILES else 1 for m in directly) + \
            sum(2 if m in CRITICAL_FILES else 0.5 for m in indirect)
    risk  = ("CRITICAL" if score >= 10 else "HIGH" if score >= 5 else
             "MEDIUM" if score >= 2 else "LOW")

    return {
        "directly":  sorted(directly),
        "indirect":  sorted(indirect),
        "all":       sorted(directly | indirect),
        "risk":      risk,
        "score":     round(score, 1),
        "layer_map": {m: get_layer(m) for m in directly | indirect},
        "unchanged_but_warn": _warn_unchanged(directly, indirect),
    }

def _warn_unchanged(directly: set[str], indirect: set[str]) -> list[str]:
    warnings = []
    if "types.ts" in directly:
        suspects = [m for m in KANI_DEPS
                    if m not in directly and m not in indirect and m not in ("index.html",)]
        if suspects:
            warnings.append(f"types.ts changed — also verify: {', '.join(suspects[:4])}")
    if "constants.ts" in directly and "App.tsx" not in directly:
        warnings.append("constants.ts changed — verify App.tsx renders new data correctly")
    return warnings

def print_ripple_effect(blast: dict, changed_paths: list[str]):
    section("RIPPLE EFFECT  —  Cross-Layer Impact Map", ">>")
    score_str = f"(score: {blast['score']})"
    print(f"\n  Overall Risk: {risk_badge(blast['risk'])}  {col(score_str, 'dim')}")
    print(f"  Files changed: {len(changed_paths)}")

    print(f"\n  {col('Layer propagation:', 'bold')}")
    layer_buckets: dict[str, list[str]] = {}
    for mod, lid in blast["layer_map"].items():
        layer_buckets.setdefault(lid, []).append(mod)

    for lid in ["L1_UI", "L2_TYPES", "L3_DATA", "L4_SERVICES", "L5_CONFIG", "UNKNOWN"]:
        mods = layer_buckets.get(lid, [])
        if not mods:
            continue
        label = LAYER_LABELS.get(lid, lid)
        print(f"\n  {col(label, 'bold')}")
        for mod in mods:
            is_direct = mod in blast["directly"]
            tag  = col("[DIRECT]", "red")  if is_direct else col("[Impact]", "yellow")
            crit = col(" [CRITICAL]", "red") if mod in CRITICAL_FILES else ""
            print(f"    {tag}  {mod}{crit}")

    if blast.get("unchanged_but_warn"):
        print(f"\n  {col('Cross-layer warnings:', 'bold')}")
        for w in blast["unchanged_but_warn"]:
            warn(w)

    if blast["directly"] and blast["indirect"]:
        print(f"\n  {col('Propagation path:', 'bold')}")
        for mod in blast["directly"][:3]:
            dependents = [m for m, deps in KANI_DEPS.items()
                          if os.path.basename(mod) in {os.path.basename(d) for d in deps}]
            if dependents:
                print(f"    {col(mod,'cyan')} -> {' -> '.join(dependents[:4])}")


# ─────────────────────────────────────────────────────────────────
# PILLAR 4 — Failure Insight Reporter
# ─────────────────────────────────────────────────────────────────

def generate_recommendations(commit_data: dict,
                              jira_results: list[dict],
                              blast: dict,
                              changed_paths: list[str]) -> list[tuple[str, str, str]]:
    """Return sorted (priority, icon, message) recommendations."""
    recs: list[tuple[str, str, str]] = []

    for item in commit_data.get("commits", []):
        h = item["health"]
        for b in h.get("breaking", []):
            if "credential" in b["pattern"].lower():
                recs.append(("CRITICAL", "[SEC]",
                              f"SECURITY: {b['pattern']} — {b['guidance']}"))
            else:
                recs.append(("HIGH", "[!]",
                              f"Breaking change in {item['commit'].get('hash','?')}: "
                              f"{b['pattern']} — {b['guidance']}"))
        for issue in h.get("issues", []):
            recs.append(("HIGH" if "SECURITY" in issue else "MEDIUM", "[warn]", issue))

    for r in jira_results:
        t = r["ticket"]
        if r["missing"] and r["is_closed"]:
            recs.append(("CRITICAL", "[JIRA]",
                         f"{t['id']} '{t['title'][:50]}' CLOSED but missing: "
                         f"{', '.join(f for f,_ in r['missing'][:3])} — prod risk!"))
        elif r["missing"]:
            recs.append(("HIGH", "[JIRA]",
                         f"{t['id']} incomplete ({r['completeness_pct']}%): "
                         f"missing {', '.join(f for f,_ in r['missing'][:3])}"))
        if not r["linked_commits"] and t.get("status", "To Do") not in ("To Do",):
            recs.append(("MEDIUM", "[link]",
                         f"{t['id']} has no linked commits — add ID to commit messages"))

    if blast.get("risk") in ("HIGH", "CRITICAL"):
        recs.append(("HIGH", "[!]",
                     f"HIGH RISK blast radius (score {blast.get('score')}) — "
                     f"run full regression suite before merging"))
    for w in blast.get("unchanged_but_warn", []):
        recs.append(("MEDIUM", "[warn]", w))

    bn = {os.path.basename(p) for p in changed_paths}
    if "types.ts" in bn:
        recs.append(("HIGH", "[TS]",
                     "types.ts changed — check ALL importing files for compile errors"))
    if "App.tsx" in bn:
        recs.append(("MEDIUM", "[UI]",
                     "App.tsx changed — test all routes: Home, Products, Cart, Orders, Admin"))
    if "geminiService.ts" in bn:
        recs.append(("MEDIUM", "[AI]",
                     "geminiService.ts changed — test Gemini chatbot end-to-end"))
    if "package.json" in bn:
        recs.append(("MEDIUM", "[PKG]",
                     "package.json changed — run `npm install` and `npm run build`"))

    if not recs:
        recs.append(("LOW", "[OK]", "No critical issues detected — good to merge"))

    recs.append(("LOW", "[test]",
                 "Test checklist: Product listing -> Add to cart -> Checkout -> Orders page"))

    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    recs.sort(key=lambda x: order.get(x[0], 9))
    return recs

def print_failure_insight(commit_data: dict, jira_results: list[dict],
                          blast: dict, changed_paths: list[str]):
    section("FAILURE INSIGHT  &  CORRECTIVE ACTIONS", ">>")
    recs = generate_recommendations(commit_data, jira_results, blast, changed_paths)

    last_priority = None
    for priority, icon, msg in recs:
        if priority != last_priority:
            print(f"\n  {col(priority, 'bold' if priority in ('CRITICAL','HIGH') else 'dim')}")
            last_priority = priority
        c_fn = ("red"    if priority == "CRITICAL" else
                "yellow" if priority == "HIGH" else
                "cyan"   if priority == "MEDIUM" else "dim")
        print(f"  {icon}  {col(msg, c_fn)}")


# ─────────────────────────────────────────────────────────────────
# Jira change tracker (between runs)
# ─────────────────────────────────────────────────────────────────

def analyze_jira_changes(last_state: dict) -> dict:
    tickets  = load_jira_tickets()
    last_map = {t["id"]: t for t in last_state.get("jira_tickets", [])}

    new_t, status_c, comment_a, desc_u = [], [], [], []
    for t in tickets:
        tid = t["id"]
        if tid not in last_map:
            new_t.append(t)
        else:
            prev = last_map[tid]
            if t.get("status") != prev.get("status"):
                status_c.append({"id": tid, "title": t["title"],
                                  "from": prev.get("status"), "to": t.get("status")})
            if t.get("description") != prev.get("description"):
                desc_u.append(t)
            if len(t.get("comments", [])) > len(prev.get("comments", [])):
                comment_a.append({"id": tid, "title": t["title"],
                                   "new": t["comments"][len(prev.get("comments", [])):]})

    return {"new": new_t, "status": status_c, "comments": comment_a,
            "desc": desc_u, "all": tickets,
            "changed": bool(new_t or status_c or comment_a or desc_u)}

def print_jira_summary(jd: dict):
    section("JIRA TICKET TRACKER  (change detection)", ">>")
    if not jd["all"]:
        warn("No tickets in jira_state.json")
        return
    if not jd["changed"]:
        ok("No Jira changes since last run")

    for t in jd.get("new", []):
        print(f"\n  {col('NEW', 'green')} {col(t['id'],'cyan')} — {t['title']}")
        print(f"    {priority_col(t.get('priority','?'))}  {t.get('status','?')}")
    for sc in jd.get("status", []):
        print(f"\n  {col('STATUS CHANGE', 'yellow')} {col(sc['id'],'cyan')} — {sc['title']}")
        print(f"    {col(sc['from'],'red')} -> {col(sc['to'],'green')}")
    for ca in jd.get("comments", []):
        print(f"\n  {col('NEW COMMENT', 'blue')} {col(ca['id'],'cyan')} — {ca['title']}")
        for cm in ca["new"][:2]:
            print(f"    {cm.get('author','?')}: {cm.get('body','')[:100]}")

    print(f"\n  {'ID':<10} {'Status':<14} {'Priority':<12} Title")
    print(col("  " + "-" * 62, "dim"))
    for t in jd["all"]:
        print(f"  {col(t['id'],'cyan'):<19} {t.get('status','?'):<14} "
              f"{priority_col(t.get('priority','?')):<21} {t.get('title','')[:40]}")


# ─────────────────────────────────────────────────────────────────
# Ollama AI deep analysis
# ─────────────────────────────────────────────────────────────────

def ollama_alive() -> bool:
    try:
        import urllib.request
        r = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
        return r.status == 200
    except Exception:
        return False

def run_ai_analysis(diff_text: str, jira_results: list[dict],
                    commit_data: dict, blast: dict, model: str = DEFAULT_MODEL):
    section("AI DEEP ANALYSIS  (Ollama)", ">>")
    if not ollama_alive():
        warn("Ollama not running — skipping.  Start with: ollama serve")
        return

    jira_ctx = ""
    for r in jira_results[:4]:
        t = r["ticket"]
        missing_str = ", ".join(f for f, _ in r["missing"][:3]) or "none"
        jira_ctx += (f"  {t['id']} [{t['status']}] {t['title']}\n"
                     f"    Missing changes: {missing_str}\n")

    recent_commits = "\n".join(
        f"  {i['commit'].get('hash','?')} (grade {i['health']['grade']}) — "
        f"{i['commit'].get('message','?')[:80]}"
        for i in commit_data.get("commits", [])[:3]
    ) or "(none)"

    prompt = f"""You are a senior engineer reviewing the Kani-Store e-commerce project.
Stack: React + TypeScript (App.tsx, types.ts, constants.ts, services/geminiService.ts).

RECENT COMMITS:
{recent_commits}

JIRA TICKETS & COMPLETENESS:
{jira_ctx or '(none)'}

BLAST RADIUS:
Risk: {blast.get('risk','?')}  Score: {blast.get('score',0)}
Directly changed: {', '.join(blast.get('directly',[])[:6]) or 'none'}
Indirectly impacted: {', '.join(blast.get('indirect',[])[:6]) or 'none'}

DIFF EXCERPT (latest commit):
{diff_text[:2500] or '(no uncommitted changes)'}

Provide a concise engineering review with EXACTLY these four sections:

ROOT CAUSE ANALYSIS:
  (What is the core issue / intent of these changes?)

BREAKING CHANGE RISK:
  (Specific risks introduced and which files will fail)

MISSING IMPLEMENTATIONS:
  (Which Jira tickets are NOT fully implemented and what exactly is missing)

CORRECTIVE ACTIONS (numbered 1-5):
  1. Most urgent fix
  2. Next fix
  ...

Keep it concise and engineering-specific. No general advice.
"""

    try:
        import urllib.request as ur
        payload = json.dumps({
            "model": model, "prompt": prompt,
            "stream": True, "options": {"temperature": 0.2, "num_predict": 900},
        }).encode()
        req = ur.Request(OLLAMA_URL, data=payload,
                         headers={"Content-Type": "application/json"}, method="POST")
        print()
        with ur.urlopen(req, timeout=150) as resp:
            for raw in resp:
                line = raw.decode("utf-8").strip()
                if line:
                    try:
                        chunk = json.loads(line)
                        print(chunk.get("response", ""), end="", flush=True)
                        if chunk.get("done"):
                            break
                    except Exception:
                        pass
        print("\n")
    except Exception as e:
        warn(f"Ollama failed: {e}")


# ─────────────────────────────────────────────────────────────────
# Output saver
# ─────────────────────────────────────────────────────────────────

def save_output(content: str):
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTPUTS_DIR, f"kani_analysis_{ts}.txt")
    ansi = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    with open(path, "w", encoding="utf-8") as f:
        f.write(ansi.sub("", content))
    ok(f"Report saved -> {path}")

def print_banner():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(col("""
  +──────────────────────────────────────────────────────────────+
  |         Kani-Store  Smart Engineering Agent                  |
  |                                                              |
  |  Pillar 1: Commit Analysis + Health Scoring                  |
  |  Pillar 2: Jira Completeness Checker                         |
  |  Pillar 3: Cross-Layer Ripple Effect Engine                  |
  |  Pillar 4: Failure Insight + Corrective Actions              |
  +──────────────────────────────────────────────────────────────+""", "cyan"))
    print(col(f"\n  [{now}]  Project root: {PROJECT_ROOT}", "dim"))
    print()


# ─────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────

def run_analysis(args):
    buf       = io.StringIO()
    orig_write = sys.stdout.write

    def tee(text):
        orig_write(text)
        buf.write(text)
    sys.stdout.write = tee  # type: ignore[method-assign]

    try:
        print_banner()
        last_state = load_last_state()
        tickets    = load_jira_tickets()

        real_commits = get_real_commits(15)
        sim_commits  = _load_json(GITHUB_STATE_FILE).get("commits", [])
        all_commits  = real_commits if real_commits else sim_commits

        uncommitted_files = get_uncommitted_files()
        uncommitted_diff  = get_uncommitted_diff()
        all_changed_paths = [f["path"] for f in uncommitted_files]

        if all_commits:
            latest_h = (all_commits[0].get("full_hash") or
                        all_commits[0].get("hash", ""))
            latest_files = (get_commit_files(latest_h) if real_commits
                            else all_commits[0].get("changed_files", []))
            all_changed_paths += [f["path"] for f in latest_files]

        # Pillar 1 — Commit Analysis
        if not args.jira:
            commit_data = analyze_commits(getattr(args, "commit", None), tickets)
            print_commit_analysis(commit_data)
        else:
            commit_data = {"commits": [], "has_real_git": bool(real_commits)}

        # Pillar 2 — Jira Completeness
        if not args.github:
            jira_changes = analyze_jira_changes(last_state)
            print_jira_summary(jira_changes)
            jira_results = analyze_jira_completeness(all_commits)
            print_jira_completeness(jira_results)
        else:
            jira_results = []

        # Pillar 3 — Ripple Effect
        if not args.jira:
            blast = resolve_blast_radius(all_changed_paths)
            print_ripple_effect(blast, all_changed_paths)
        else:
            blast = {"risk": "LOW", "score": 0, "directly": [], "indirect": [],
                     "all": [], "layer_map": {}, "unchanged_but_warn": []}

        # Pillar 4 — Failure Insight
        if not args.jira and not args.github:
            print_failure_insight(commit_data, jira_results, blast, all_changed_paths)

        # Optional AI analysis
        if args.ai:
            diff_text = uncommitted_diff or (
                get_commit_diff(
                    all_commits[0].get("full_hash") or all_commits[0].get("hash", "")
                ) if all_commits else "")
            run_ai_analysis(diff_text, jira_results, commit_data, blast,
                            model=getattr(args, "model", DEFAULT_MODEL))

        save_state({
            "jira_tickets":     tickets,
            "last_commit_hash": (all_commits[0].get("full_hash") or
                                 all_commits[0].get("hash", "")) if all_commits else "",
            "last_run":         datetime.now().isoformat(),
        })

        print(f"\n{col('  ' + '='*60, 'dim')}")
        ok(f"Analysis complete at {datetime.now().strftime('%H:%M:%S')}")

    finally:
        sys.stdout.write = orig_write  # type: ignore[method-assign]

    save_output(buf.getvalue())


# ─────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Kani-Store Smart Engineering Agent — 4-pillar code reviewer",
    )
    p.add_argument("--jira",    action="store_true", help="Jira-only mode")
    p.add_argument("--github",  action="store_true", help="GitHub/commit-only mode")
    p.add_argument("--code",    action="store_true", help="Code diff analysis only")
    p.add_argument("--ai",      action="store_true", help="Enable Ollama AI deep analysis")
    p.add_argument("--commit",  metavar="HASH",      help="Analyze a specific commit hash")
    p.add_argument("--watch",   action="store_true", help="Watch mode — re-run on file changes")
    p.add_argument("--model",   default=DEFAULT_MODEL,
                   help=f"Ollama model to use (default: {DEFAULT_MODEL})")
    return p.parse_args()


def main():
    args = parse_args()

    if args.watch:
        info("Watch mode enabled — re-running on file changes (Ctrl+C to stop)")
        last_hashes = {
            JIRA_STATE_FILE:   file_hash(JIRA_STATE_FILE),
            GITHUB_STATE_FILE: file_hash(GITHUB_STATE_FILE),
        }
        try:
            run_analysis(args)
            while True:
                time.sleep(4)
                new_hashes = {
                    JIRA_STATE_FILE:   file_hash(JIRA_STATE_FILE),
                    GITHUB_STATE_FILE: file_hash(GITHUB_STATE_FILE),
                }
                if new_hashes != last_hashes:
                    print(f"\n{col('  *** Change detected — re-running ***', 'yellow')}\n")
                    run_analysis(args)
                    last_hashes = new_hashes
        except KeyboardInterrupt:
            print("\n  Watch mode stopped.")
    else:
        run_analysis(args)


if __name__ == "__main__":
    main()
