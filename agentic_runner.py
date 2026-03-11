"""
Agentic Blast Radius Runner
=============================
Fully autonomous agent that analyzes code blast radius using a
ReAct (Reason → Act → Observe) loop backed by a local Ollama LLM.

Capabilities:
  • Accepts ANY file path — single file, directory, or git repo
  • Detects binary vs text automatically; handles ALL text file types
  • Handles large repos by streaming + embedding-based RAG chunking
  • Connects to real OR pseudo (mock) Jira and GitHub
  • Agentic loop: the LLM decides which tools to call next
  • Produces a detailed blast-radius report in outputs/

Entry points:
  python agentic_runner.py --file /path/to/project [options]
  bash   run_agent.sh  --file /path/to/project [options]   (Linux/macOS/WSL)
  pwsh   run_agent.ps1 --File /path/to/project [options]   (Windows PowerShell)

Quick start (pseudo mode — no credentials needed):
  python agentic_runner.py --file . --pseudo
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from dataclasses import dataclass, field
from typing import Any

import requests

# ──────────────────────────────────────────────────────────────────
# Optional local imports (graceful fallback if missing)
# ──────────────────────────────────────────────────────────────────
try:
    from pseudo_setup import PseudoJira, PseudoGitHub
    _PSEUDO_AVAILABLE = True
except ImportError:
    _PSEUDO_AVAILABLE = False

try:
    import repo_chunker
    _CHUNKER_AVAILABLE = True
except ImportError:
    _CHUNKER_AVAILABLE = False

# ──────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_EMBED = "http://localhost:11434/api/embeddings"
DEFAULT_MODEL = "mistral"

# File types we actively read (everything else gets binary-checked at read time)
ALWAYS_SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tiff",
    ".svg",               # (treatable as text but usually not useful as code)
    ".pdf", ".docx", ".xlsx", ".pptx",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".rar", ".7z",
    ".mp3", ".mp4", ".wav", ".ogg", ".avi", ".mov",
    ".exe", ".dll", ".so", ".dylib", ".class", ".pyc", ".pyo",
    ".woff", ".woff2", ".ttf", ".eot",
    ".db", ".sqlite", ".sqlite3",
    ".lock",              # package-lock.json / Gemfile.lock ARE text, handled below
}

# ──────────────────────────────────────────────────────────────────
# ANSI colours
# ──────────────────────────────────────────────────────────────────

C = {
    "reset":   "\033[0m",
    "bold":    "\033[1m",
    "dim":     "\033[2m",
    "red":     "\033[91m",
    "green":   "\033[92m",
    "yellow":  "\033[93m",
    "blue":    "\033[94m",
    "magenta": "\033[95m",
    "cyan":    "\033[96m",
}

def col(text: str, c: str) -> str:
    return f"{C.get(c,'')}{text}{C['reset']}"

def banner():
    print(col(textwrap.dedent(r"""
    ╔══════════════════════════════════════════════════════════════╗
    ║   🤖  Agentic Blast Radius Runner  —  ReAct + Local AI  🤖  ║
    ║                                                              ║
    ║   Any file type • Big repos • Pseudo Jira/GitHub • Agentic  ║
    ╚══════════════════════════════════════════════════════════════╝
    """), "cyan"))

def sec(title: str, icon: str = "▸"):
    print(f"\n{col(f'  {icon} {title}', 'bold')}")
    print(col("  " + "─" * 54, "dim"))

def ok(msg: str):    print(f"  {col('✓', 'green')} {msg}")
def info(msg: str):  print(f"  {col('•', 'cyan')} {msg}")
def warn(msg: str):  print(f"  {col('⚠', 'yellow')} {msg}")
def err(msg: str):   print(f"  {col('✖', 'red')} {msg}")

# ──────────────────────────────────────────────────────────────────
# Universal file scanner
# ──────────────────────────────────────────────────────────────────

def _is_binary(path: str) -> bool:
    """Detect binary files without external libs — checks for null bytes."""
    try:
        with open(path, "rb") as fh:
            chunk = fh.read(8192)
        return b"\x00" in chunk
    except OSError:
        return True


def scan_any_path(path: str, max_file_kb: int = 512) -> dict[str, str]:
    """
    Recursively scan a path (file or directory) for readable text content.
    Returns {relative_path: content}.
    Handles any text file type; skips known binary extensions and binary-detected files.
    Large files are truncated to max_file_kb KB to protect context-window limits.
    """
    path = os.path.abspath(path)
    results: dict[str, str] = {}

    targets: list[str] = []
    if os.path.isfile(path):
        targets = [path]
        base = os.path.dirname(path)
    else:
        base = path
        for root, dirs, files in os.walk(path):
            # Skip hidden dirs and common noise dirs
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".")
                and d not in {"node_modules", "__pycache__", ".git", "dist",
                               "build", ".venv", "venv", "env", ".mypy_cache",
                               ".pytest_cache", "coverage", ".tox"}
            ]
            for fname in files:
                targets.append(os.path.join(root, fname))

    skipped_binary = 0
    for filepath in targets:
        ext = os.path.splitext(filepath)[1].lower()

        # Always-skip extensions (media, archives, compiled artefacts)
        # But allow .lock files (they are plain text)
        if ext in ALWAYS_SKIP_EXTENSIONS and ext != ".lock":
            skipped_binary += 1
            continue

        # Binary-content check
        if _is_binary(filepath):
            skipped_binary += 1
            continue

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except OSError:
            continue

        if not content.strip():
            continue

        # Truncate very large files
        max_bytes = max_file_kb * 1024
        if len(content) > max_bytes:
            content = content[:max_bytes] + f"\n\n... [TRUNCATED — file exceeds {max_file_kb} KB] ..."

        rel = os.path.relpath(filepath, base)
        results[rel] = content

    if skipped_binary:
        info(f"Skipped {skipped_binary} binary/media file(s)")

    return results


def build_repo_structure(files: dict[str, str]) -> str:
    """Format the file list as a tree-like structure."""
    lines = sorted(files.keys())
    return "\n".join(lines)


def build_code_view(files: dict[str, str], max_total_chars: int = 40_000) -> str:
    """
    Combine file contents into a single string for the LLM.
    Trims to max_total_chars total to avoid blowing the context window.
    """
    parts: list[str] = []
    total = 0
    for rel, content in sorted(files.items()):
        header = f"\n{'='*60}\nFILE: {rel}\n{'='*60}\n"
        snippet = header + content
        if total + len(snippet) > max_total_chars:
            parts.append(f"\n... [remaining files omitted — context window limit reached] ...")
            break
        parts.append(snippet)
        total += len(snippet)
    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────────
# Ollama helpers
# ──────────────────────────────────────────────────────────────────

def ollama_alive() -> bool:
    try:
        return requests.get("http://localhost:11434/api/tags", timeout=5).status_code == 200
    except Exception:
        return False


def list_models() -> list[str]:
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        data = resp.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def pick_model(preferred: str | None) -> str:
    available = list_models()
    if not available:
        err("Ollama has no models pulled. Run: ollama pull mistral")
        sys.exit(1)
    if preferred:
        for m in available:
            if m.startswith(preferred):
                return m
        warn(f"Model '{preferred}' not found. Available: {available}")
    for m in available:
        if m.startswith(DEFAULT_MODEL):
            return m
    return available[0]


def query_model(prompt: str, model: str, stream: bool = True) -> str:
    """Send prompt to Ollama; stream tokens to stdout and return full text."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": stream,
        "options": {"temperature": 0.2, "num_predict": 3072},
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, stream=stream, timeout=180)
        resp.raise_for_status()
    except requests.ConnectionError:
        err("Cannot reach Ollama at http://localhost:11434")
        sys.exit(1)
    except requests.Timeout:
        err("Ollama timed out.")
        sys.exit(1)

    tokens: list[str] = []
    if stream:
        for line in resp.iter_lines():
            if line:
                try:
                    chunk = json.loads(line)
                    t = chunk.get("response", "")
                    tokens.append(t)
                    print(t, end="", flush=True)
                    if chunk.get("done"):
                        break
                except json.JSONDecodeError:
                    pass
        print()
    else:
        tokens.append(resp.json().get("response", ""))
    return "".join(tokens)


def embed(text: str, model: str) -> list[float]:
    try:
        resp = requests.post(OLLAMA_EMBED, json={"model": model, "prompt": text}, timeout=60)
        return resp.json().get("embedding", [])
    except Exception:
        return []


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot  = sum(x * y for x, y in zip(a, b))
    na   = math.sqrt(sum(x * x for x in a))
    nb   = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


# ──────────────────────────────────────────────────────────────────
# RAG chunker for large repos
# ──────────────────────────────────────────────────────────────────

def rag_find_relevant(query: str, files: dict[str, str], model: str, top_k: int = 6) -> list[dict]:
    """
    Split all files into overlapping chunks, embed them, rank by cosine similarity
    with the query embedding.  Returns top_k chunks as dicts {path, text, score}.
    """
    CHUNK_SIZE  = 2500
    CHUNK_OVERLAP = 400

    chunks: list[dict] = []
    for rel, content in files.items():
        start = 0
        i = 0
        while start < len(content):
            end  = start + CHUNK_SIZE
            text = f"File: {rel}\n---\n{content[start:end]}"
            chunks.append({"path": rel, "text": text, "idx": i})
            start += CHUNK_SIZE - CHUNK_OVERLAP
            i += 1

    info(f"RAG: {len(files)} files → {len(chunks)} chunks")

    q_embed = embed(query, model)
    if not q_embed:
        warn("Could not embed query; returning first chunks without ranking.")
        return chunks[:top_k]

    for n, c in enumerate(chunks):
        if n % 100 == 0 and n > 0:
            info(f"  Embedded {n}/{len(chunks)} chunks …")
        c["score"] = cosine(q_embed, embed(c["text"], model))

    chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
    top = chunks[:top_k]

    for i, c in enumerate(top):
        ok(f"  {i+1}. {c['path']}  (score {c.get('score',0):.4f})")

    return top


# ──────────────────────────────────────────────────────────────────
# Agent memory & tool registry
# ──────────────────────────────────────────────────────────────────

@dataclass
class AgentMemory:
    """Rolling context buffer for the agent's observations."""
    entries: list[str] = field(default_factory=list)
    max_entries: int = 30

    def add(self, role: str, content: str):
        self.entries.append(f"[{role.upper()}] {content}")
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]

    def as_text(self) -> str:
        return "\n".join(self.entries)


TOOL_DESCRIPTIONS = {
    "scan_files":       "Scan a file or directory for all readable text content.",
    "get_jira":         "Fetch a Jira ticket (real or pseudo).",
    "get_github_pr":    "Fetch a GitHub Pull Request diff (real or pseudo).",
    "search_repo_rag":  "Use RAG (embedding search) to find relevant code chunks for a query in the scanned files.",
    "query_model":      "Ask the local AI model a question and get an answer.",
    "finalize":         "Compile all gathered context and produce the final blast-radius report.",
}


# ──────────────────────────────────────────────────────────────────
# Agentic Blast Radius Agent
# ──────────────────────────────────────────────────────────────────

class BlastRadiusAgent:
    """
    ReAct (Reason → Act → Observe) agent that orchestrates blast-radius analysis.

    The agent loop:
      1. PLAN  — LLM creates a sequence of tool calls given the task description
      2. ACT   — Execute each tool; observe the result
      3. REASON — LLM reflects on observations, may add new steps
      4. REPORT — LLM writes the final blast-radius report
    """

    MAX_ITERATIONS = 12

    def __init__(self, config: dict[str, Any]):
        self.config   = config
        self.model    = config["model"]
        self.pseudo   = config.get("pseudo", False)
        self.file_path = config.get("file_path")
        self.jira_id   = config.get("jira")
        self.jira_url  = config.get("jira_url")
        self.jira_email = config.get("jira_email")
        self.jira_token = config.get("jira_token")
        self.github_repo  = config.get("github_repo")
        self.github_pr    = config.get("github_pr")
        self.github_token = config.get("github_token")
        self.use_rag      = config.get("rag", False)
        self.top_k        = config.get("top_k", 6)

        self.memory  = AgentMemory()
        self.files: dict[str, str] = {}   # scanned file contents
        self.context: dict[str, str] = {} # accumulated analysis context

    # ── public entry ──────────────────────────────────────────────

    def run(self) -> str:
        """Execute the full agentic pipeline and return the final report."""
        sec("Starting Agentic Blast Radius Analysis", "🤖")

        task_desc = self._build_task_description()
        info(f"Task: {task_desc}")
        self.memory.add("task", task_desc)

        # Phase 1: Plan
        sec("Planning tool call sequence", "🗺")
        plan = self._plan(task_desc)
        info("Agent plan:")
        for i, step in enumerate(plan, 1):
            print(f"    {i}. {step}")
        self.memory.add("plan", "\n".join(plan))

        # Phase 2: Execute plan steps
        sec("Executing plan steps", "⚙")
        for iteration, step in enumerate(plan):
            if iteration >= self.MAX_ITERATIONS:
                warn(f"Reached max iterations ({self.MAX_ITERATIONS}). Proceeding to report.")
                break
            ok(f"Step {iteration+1}: {step}")
            observation = self._dispatch(step)
            self.memory.add("observation", f"[Step: {step}]\n{observation[:800]}")

        # Phase 3: Let the agent reason if additional tools are needed
        sec("Agent reflection pass", "🧠")
        reflection = self._reflect()
        self.memory.add("reflection", reflection[:600])
        info(f"Reflection: {reflection[:200]}…")

        # Phase 4: Final report
        sec("Generating final blast-radius report", "📊")
        print(col("\n  Streaming AI response…\n", "dim"))
        print(col("  " + "─" * 54, "dim"))
        report = self._final_report()

        # Save
        self._save(report)
        return report

    # ── planning ──────────────────────────────────────────────────

    def _build_task_description(self) -> str:
        parts = ["Analyze the blast radius of the following code changes."]
        if self.file_path:
            parts.append(f"Source path: {self.file_path}")
        if self.jira_id:
            parts.append(f"Jira ticket: {self.jira_id}")
        if self.github_repo and self.github_pr:
            parts.append(f"GitHub PR: {self.github_repo}#{self.github_pr}")
        if self.pseudo:
            parts.append("(Running in pseudo/demo mode — no real credentials required)")
        return " ".join(parts)

    def _plan(self, task: str) -> list[str]:
        """Ask the LLM to produce an ordered list of tool calls."""
        tools_list = "\n".join(f"  - {k}: {v}" for k, v in TOOL_DESCRIPTIONS.items())
        prompt = textwrap.dedent(f"""\
            You are a blast-radius analysis agent. Your available tools are:
            {tools_list}

            Task: {task}

            Produce a numbered list of tool calls to gather all necessary context
            before writing the final report. Each line must be ONE tool name from
            the list above (no extra text, no JSON). Example:
            1. scan_files
            2. get_jira
            3. search_repo_rag
            4. finalize

            Plan:
        """)
        raw = query_model(prompt, self.model, stream=False)
        steps: list[str] = []
        for line in raw.splitlines():
            line = line.strip().lstrip("0123456789. )-")
            tool = line.split()[0].lower() if line.split() else ""
            if tool in TOOL_DESCRIPTIONS:
                steps.append(tool)
        # Always end with finalize
        if "finalize" not in steps:
            steps.append("finalize")
        # Ensure we have at least a minimal plan
        if len(steps) <= 1:
            steps = self._default_plan()
        return steps

    def _default_plan(self) -> list[str]:
        plan = []
        if self.file_path:
            plan.append("scan_files")
        if self.jira_id:
            plan.append("get_jira")
        if self.github_repo and self.github_pr:
            plan.append("get_github_pr")
        if self.use_rag and self.file_path:
            plan.append("search_repo_rag")
        plan.append("finalize")
        return plan

    # ── tool dispatch ─────────────────────────────────────────────

    def _dispatch(self, tool: str) -> str:
        dispatch_map = {
            "scan_files":      self._tool_scan_files,
            "get_jira":        self._tool_get_jira,
            "get_github_pr":   self._tool_get_github_pr,
            "search_repo_rag": self._tool_rag,
            "query_model":     self._tool_query_model,
            "finalize":        lambda: "(finalize — handled separately)",
        }
        fn = dispatch_map.get(tool)
        if fn is None:
            return f"Unknown tool: {tool}"
        try:
            return fn()
        except Exception as exc:
            warn(f"Tool '{tool}' raised: {exc}")
            return f"ERROR in {tool}: {exc}"

    def _tool_scan_files(self) -> str:
        if not self.file_path:
            return "No --file path provided."
        info(f"Scanning: {self.file_path}")
        self.files = scan_any_path(self.file_path)
        ok(f"Found {len(self.files)} readable file(s)")
        for fn in list(self.files)[:8]:
            print(f"    {col('·', 'dim')} {fn}")
        if len(self.files) > 8:
            print(f"    {col('·', 'dim')} … and {len(self.files)-8} more")
        self.context["repo_structure"] = build_repo_structure(self.files)
        big_repo = len(self.files) > 200
        if big_repo:
            warn(f"Large repo ({len(self.files)} files). RAG will be used automatically.")
            self.use_rag = True
        summary = (
            f"Scanned {len(self.files)} files. "
            f"{'RAG enabled for large repo.' if big_repo else ''}"
        )
        self.context["code_snapshot"] = build_code_view(self.files)
        return summary

    def _tool_get_jira(self) -> str:
        if not self.jira_id:
            return "No --jira ticket ID provided."
        if self.pseudo:
            if not _PSEUDO_AVAILABLE:
                return "pseudo_setup.py not found."
            pj = PseudoJira()
            ticket_text = pj.format_ticket_for_agent(self.jira_id)
            ok(f"Loaded pseudo Jira ticket: {self.jira_id}")
        else:
            # Real Jira
            try:
                from jira_handler import JiraHandler
                jh = JiraHandler(self.jira_url, self.jira_email, self.jira_token)
                ticket_text = jh.format_ticket_for_agent(self.jira_id)
                ok(f"Loaded real Jira ticket: {self.jira_id}")
            except Exception as exc:
                return f"Jira fetch failed: {exc}"
        self.context["ticket"] = ticket_text
        return f"Jira context loaded ({len(ticket_text)} chars)."

    def _tool_get_github_pr(self) -> str:
        if not self.github_repo:
            return "No --github repo provided."
        if self.pseudo:
            if not _PSEUDO_AVAILABLE:
                return "pseudo_setup.py not found."
            pg = PseudoGitHub()
            pr_data = pg.fetch_pr_data(self.github_repo, self.github_pr or 1)
            ok(f"Loaded pseudo GitHub PR #{self.github_pr or 1} for {self.github_repo}")
        else:
            try:
                from github_handler import GitHubHandler
                gh = GitHubHandler(token=self.github_token)
                pr_data = gh.fetch_pr_data(self.github_repo, self.github_pr)
                ok(f"Loaded real GitHub PR #{self.github_pr}")
            except Exception as exc:
                return f"GitHub fetch failed: {exc}"
        self.context.update({
            "what_changed":    pr_data.get("what_changed", ""),
            "code_before":     pr_data.get("code_before", ""),
            "code_after":      pr_data.get("code_after", ""),
            "repo_structure":  pr_data.get("repo_structure", ""),
        })
        if "ticket" not in self.context:
            self.context["ticket"] = pr_data.get("ticket", "")
        return f"GitHub PR context loaded — {len(pr_data.get('full_diff',''))} chars of diff."

    def _tool_rag(self) -> str:
        if not self.files:
            return "No files scanned yet. Run scan_files first."
        query = (
            self.context.get("ticket", "")
            or self.context.get("what_changed", "")
            or "code changes blast radius analysis"
        )
        info(f"RAG search over {len(self.files)} files …")
        top_chunks = rag_find_relevant(query, self.files, self.model, top_k=self.top_k)
        chunks_text = "\n\n".join(c["text"] for c in top_chunks)
        self.context["rag_chunks"] = chunks_text
        return f"RAG complete — {len(top_chunks)} relevant chunks retrieved."

    def _tool_query_model(self) -> str:
        q = self.context.get("ticket", "Analyze the code changes for blast radius.")
        resp = query_model(q, self.model, stream=False)
        self.context["intermediate_analysis"] = resp
        return resp[:400]

    # ── reflection ────────────────────────────────────────────────

    def _reflect(self) -> str:
        prompt = textwrap.dedent(f"""\
            You are a blast-radius analysis agent.
            Here is a summary of observations so far:
            {self.memory.as_text()}

            Briefly summarise (2-3 sentences) what you have learned and whether
            there are any gaps in the context before writing the final report.
        """)
        return query_model(prompt, self.model, stream=False)

    # ── final report ──────────────────────────────────────────────

    def _final_report(self) -> str:
        ticket       = self.context.get("ticket", "(no ticket provided)")
        what_changed = self.context.get("what_changed", "(auto-detected from file scan)")
        code_before  = self.context.get("code_before", "(see file snapshot below)")
        code_after   = self.context.get("code_after",  "(see file snapshot below)")
        repo_struct  = self.context.get("repo_structure", "")
        rag_chunks   = self.context.get("rag_chunks", "")
        snapshot     = self.context.get("code_snapshot", "")

        code_section = rag_chunks if rag_chunks else (
            f"BEFORE:\n{code_before}\n\nAFTER:\n{code_after}\n\nFILE SNAPSHOT:\n{snapshot}"
        )

        prompt = textwrap.dedent(f"""\
            You are an expert software engineer performing a blast-radius analysis.

            ── TICKET / ISSUE ──────────────────────────────────────────────
            {ticket}

            ── WHAT CHANGED ────────────────────────────────────────────────
            {what_changed}

            ── REPOSITORY STRUCTURE ────────────────────────────────────────
            {repo_struct[:3000] if repo_struct else '(not available)'}

            ── CODE CONTEXT ────────────────────────────────────────────────
            {code_section[:18000]}

            ── AGENT OBSERVATIONS ──────────────────────────────────────────
            {self.memory.as_text()[:2000]}

            ── INSTRUCTIONS ────────────────────────────────────────────────
            Produce a detailed blast-radius analysis with the following sections:

            1. SUMMARY OF CHANGES
               What was changed and why.

            2. DIRECTLY IMPACTED COMPONENTS (HIGH risk)
               Files / modules that call or are called by the changed code.

            3. INDIRECTLY IMPACTED COMPONENTS (MEDIUM risk)
               Transitive dependents that may behave differently.

            4. LOW RISK AREAS
               Modules confirmed to be unaffected.

            5. RISK ASSESSMENT
               Overall risk level: LOW / MEDIUM / HIGH / CRITICAL.
               Justification with specific file/function references.

            6. RECOMMENDED ACTIONS
               PRs to raise, tests to add, reviews needed, rollout strategy.

            Use concrete file names and function names where available.
            Be concise but thorough.
        """)
        return query_model(prompt, self.model, stream=True)

    # ── save output ───────────────────────────────────────────────

    def _save(self, report: str):
        out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
        os.makedirs(out_dir, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        fp = os.path.join(out_dir, f"agentic_analysis_{ts}.txt")
        with open(fp, "w", encoding="utf-8") as fh:
            fh.write("Agentic Blast Radius Analysis\n")
            fh.write(f"Generated : {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            fh.write(f"Model     : {self.model}\n")
            fh.write(f"Source    : {self.config.get('file_path','N/A')}\n")
            fh.write("=" * 62 + "\n\n")
            fh.write(report)
        ok(f"Report saved → {col(fp, 'cyan')}")

    def _print_report(self, report: str):
        print()
        print(col("  ╔══════════════════════════════════════════════════════════╗", "magenta"))
        print(col("  ║              📊  BLAST RADIUS ANALYSIS  REPORT          ║", "magenta"))
        print(col("  ╚══════════════════════════════════════════════════════════╝", "magenta"))
        for line in report.split("\n"):
            line = line.replace("HIGH",     col("HIGH",     "red"))
            line = line.replace("CRITICAL", col("CRITICAL", "red"))
            line = line.replace("MEDIUM",   col("MEDIUM",   "yellow"))
            line = line.replace("LOW",      col("LOW",      "green"))
            print(f"  {line}")


# ──────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Agentic Blast Radius Runner — Analyze any codebase with local AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              # Pseudo mode (no credentials)
              python agentic_runner.py --file ./my-project --pseudo

              # Real Jira + local files
              python agentic_runner.py --file ./my-project \\
                --jira PROJ-42 --jira-url https://co.atlassian.net \\
                --jira-email me@co.com --jira-token <token>

              # Real GitHub PR
              python agentic_runner.py --file ./my-project \\
                --github owner/repo --pr 99 --token ghp_xxx

              # Big repo with RAG
              python agentic_runner.py --file /large/monorepo --pseudo --rag
        """),
    )

    # Source
    p.add_argument("--file",  metavar="PATH",
                   help="Path to a file, directory, or git repo to analyze.")

    # Pseudo mode
    p.add_argument("--pseudo", action="store_true",
                   help="Use fake Jira & GitHub data (no credentials needed). Great for demos.")

    # Jira (real)
    p.add_argument("--jira",        metavar="TICKET-ID",
                   help="Jira ticket key, e.g. PROJ-1234")
    p.add_argument("--jira-url",    metavar="URL",
                   help="Jira base URL, e.g. https://yourco.atlassian.net")
    p.add_argument("--jira-email",  metavar="EMAIL")
    p.add_argument("--jira-token",  metavar="TOKEN")

    # GitHub (real)
    p.add_argument("--github",  metavar="OWNER/REPO")
    p.add_argument("--pr",      type=int, metavar="NUMBER")
    p.add_argument("--token",   metavar="TOKEN",
                   help="GitHub Personal Access Token")

    # Pseudo overrides for Jira/GitHub IDs (when --pseudo is set)
    p.add_argument("--pseudo-jira",   metavar="TICKET-ID",
                   help="Pseudo Jira ticket ID to simulate (e.g. DEMO-42)")
    p.add_argument("--pseudo-github", metavar="REPO",
                   help="Pseudo GitHub repo to simulate (e.g. my-org/my-app)")
    p.add_argument("--pseudo-pr",     type=int, default=1,
                   help="Pseudo PR number (default: 1)")

    # Model
    p.add_argument("--model", metavar="NAME", default=None,
                   help=f"Ollama model name (default: {DEFAULT_MODEL})")

    # RAG
    p.add_argument("--rag", action="store_true",
                   help="Force RAG chunking even for small repos.")
    p.add_argument("--top-k", type=int, default=6,
                   help="Number of RAG chunks to retrieve (default: 6)")

    args = p.parse_args()

    # Normalise pseudo mode shortcuts
    if args.pseudo:
        if args.pseudo_jira and not args.jira:
            args.jira = args.pseudo_jira
        if args.pseudo_github and not args.github:
            args.github = args.pseudo_github
            args.pr = args.pseudo_pr

    return args


# ──────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────

def main():
    args = parse_args()
    banner()

    # Check Ollama
    sec("Checking local AI (Ollama)", "🔌")
    if not ollama_alive():
        err(
            "Ollama is not running.\n"
            "    Install: https://ollama.com\n"
            "    Start:   ollama serve\n"
            "    Pull:    ollama pull mistral"
        )
        sys.exit(1)
    ok("Ollama is running")

    model = pick_model(args.model)
    ok(f"Using model: {col(model, 'cyan')}")

    # Build config
    config: dict[str, Any] = {
        "model":        model,
        "pseudo":       args.pseudo,
        "file_path":    os.path.abspath(args.file) if args.file else None,
        "jira":         args.jira,
        "jira_url":     args.jira_url,
        "jira_email":   args.jira_email,
        "jira_token":   args.jira_token,
        "github_repo":  args.github,
        "github_pr":    args.pr,
        "github_token": args.token,
        "rag":          args.rag,
        "top_k":        args.top_k,
    }

    info(f"File path : {config['file_path'] or '(none)'}")
    info(f"Jira      : {config['jira'] or '(none)'}")
    info(f"GitHub    : {(str(config['github_repo'])+'#'+str(config['github_pr'])) if config['github_repo'] else '(none)'}")
    info(f"Pseudo    : {config['pseudo']}")
    info(f"RAG       : {config['rag']}")

    # Validate: need at least something to analyze
    if not config["file_path"] and not config["github_repo"] and not config["jira"]:
        err(
            "Nothing to analyze. Provide at least one of:\n"
            "    --file <path>\n"
            "    --github owner/repo --pr <number>\n"
            "    --jira TICKET-ID\n"
            "    Add --pseudo for demo mode without credentials."
        )
        sys.exit(1)

    agent = BlastRadiusAgent(config)
    report = agent.run()
    agent._print_report(report)


if __name__ == "__main__":
    main()
