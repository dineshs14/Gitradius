"""
AI Blast Radius Analysis Agent
================================
A local AI agent that analyzes code changes and predicts
the possible impact (blast radius) on other modules.

Supports FOUR input modes:
  1. Local text files    → python agent.py
  2. GitHub Pull Request → python agent.py --github owner/repo --pr 42
  3. Local Git repo      → python agent.py --repo ./my-project
  4. Jira ticket context → python agent.py --jira PROJ-1234 --jira-url https://...

Uses Ollama (local LLM) via its HTTP API for AI inference.
"""

import argparse
import json
import sys
import os
import requests
import textwrap
import time

import subprocess
import tempfile
import shutil

from github_handler import GitHubHandler
from git_watcher import GitWatcher
from jira_handler import JiraHandler
import repo_chunker

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "mistral"  # Options: mistral, codellama, deepseek-coder

INPUT_FILES = {
    "ticket":         "ticket.txt",
    "logs":           "logs.txt",
    "code_before":    "code_before.txt",
    "code_after":     "code_after.txt",
    "repo_structure": "repo_structure.txt",
}

PROMPT_TEMPLATE_FILE = "prompt.txt"

# ──────────────────────────────────────────────
# File I/O helpers
# ──────────────────────────────────────────────

def get_base_dir() -> str:
    """Return the directory where agent.py lives."""
    return os.path.dirname(os.path.abspath(__file__))


def read_file(filepath: str) -> str:
    """Read and return the contents of a text file."""
    full_path = os.path.join(get_base_dir(), filepath)
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Required input file not found: {full_path}")
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read().strip()


def load_input_files() -> dict[str, str]:
    """Load all required input files into a dictionary."""
    inputs: dict[str, str] = {}
    missing: list[str] = []

    for key, filename in INPUT_FILES.items():
        try:
            inputs[key] = read_file(filename)
        except FileNotFoundError:
            missing.append(filename)

    if missing:
        print_error(
            "Missing input files",
            f"The following files are required but were not found:\n"
            + "\n".join(f"  • {f}" for f in missing)
            + f"\n\nMake sure they exist in: {get_base_dir()}"
        )
        sys.exit(1)

    # Add a default "what_changed" for local file mode
    if "what_changed" not in inputs:
        inputs["what_changed"] = "(Loaded from local text files — see code diff below for details)"

    return inputs


# ──────────────────────────────────────────────
# Prompt construction
# ──────────────────────────────────────────────

def build_prompt(inputs: dict[str, str]) -> str:
    """
    Load the prompt template and inject input data.
    The template uses {placeholder} syntax for each input key.
    """
    try:
        template = read_file(PROMPT_TEMPLATE_FILE)
    except FileNotFoundError:
        print_error(
            "Prompt template missing",
            f"Could not find '{PROMPT_TEMPLATE_FILE}' in {get_base_dir()}.\n"
            "This file defines how the AI model should analyze the inputs."
        )
        sys.exit(1)

    # Replace placeholders with actual input content
    prompt = template
    for key, content in inputs.items():
        placeholder = "{" + key + "}"
        prompt = prompt.replace(placeholder, content)

    return prompt


# ──────────────────────────────────────────────
# Ollama integration (AI Inference)
# ──────────────────────────────────────────────

def check_ollama_connection() -> bool:
    """Verify that the Ollama server is reachable."""
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        return resp.status_code == 200
    except requests.ConnectionError:
        return False


def get_available_models() -> list[str]:
    """Fetch the list of models currently pulled in Ollama."""
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        pass
    return []


def select_model() -> str:
    """
    Determine which model to use.
    Priority: DEFAULT_MODEL (if available) > first available model.
    """
    available = get_available_models()

    if not available:
        print_error(
            "No models found",
            "Ollama is running but has no models pulled.\n"
            "Pull a model first:\n\n"
            "  ollama pull mistral\n"
            "  ollama pull codellama\n"
            "  ollama pull deepseek-coder\n"
        )
        sys.exit(1)

    # Use default if available
    for model in available:
        if model.startswith(DEFAULT_MODEL):
            return model

    # Fallback to first available
    return available[0]


def query_ollama(prompt: str, model: str) -> str:
    """
    Send the prompt to Ollama and return the full response text.
    Streams the response for real-time feedback.
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {
            "temperature": 0.3,       # Lower = more deterministic
            "num_predict": 2048,       # Max tokens in response
        },
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, stream=True, timeout=120)
        response.raise_for_status()
    except requests.ConnectionError:
        print_error(
            "Connection failed",
            "Cannot connect to Ollama at http://localhost:11434\n"
            "Make sure Ollama is running:\n\n"
            "  ollama serve\n"
        )
        sys.exit(1)
    except requests.Timeout:
        print_error("Request timed out", "The Ollama server took too long to respond.")
        sys.exit(1)
    except requests.HTTPError as e:
        print_error("HTTP error from Ollama", str(e))
        sys.exit(1)

    # Stream and collect response tokens
    full_response = []
    for line in response.iter_lines():
        if line:
            try:
                chunk = json.loads(line)
                token = chunk.get("response", "")
                full_response.append(token)
                print(token, end="", flush=True)  # Real-time streaming
                if chunk.get("done", False):
                    break
            except json.JSONDecodeError:
                continue

    print()  # Final newline after streaming
    return "".join(full_response)


# ──────────────────────────────────────────────
# Output formatting
# ──────────────────────────────────────────────

COLORS = {
    "reset":   "\033[0m",
    "bold":    "\033[1m",
    "red":     "\033[91m",
    "green":   "\033[92m",
    "yellow":  "\033[93m",
    "blue":    "\033[94m",
    "magenta": "\033[95m",
    "cyan":    "\033[96m",
    "dim":     "\033[2m",
}


def colorize(text: str, color: str) -> str:
    """Wrap text with ANSI color codes."""
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def print_banner():
    """Print the startup banner."""
    banner = r"""
    ╔══════════════════════════════════════════════════════╗
    ║       🔍  AI Blast Radius Analysis Agent  🔍        ║
    ║                                                      ║
    ║   Analyze code changes • Predict impact • Local AI   ║
    ║                                                      ║
    ║   Modes: Local Files | Git Repo | GitHub PR | Jira   ║
    ╚══════════════════════════════════════════════════════╝
    """
    print(colorize(banner, "cyan"))


def print_section(title: str, icon: str = "▸"):
    """Print a formatted section header."""
    print(f"\n{colorize(f'  {icon} {title}', 'bold')}")
    print(colorize("  " + "─" * 50, "dim"))


def print_error(title: str, message: str):
    """Print formatted error message."""
    print(f"\n{colorize('  ✖ ERROR: ' + title, 'red')}")
    print(colorize("  " + "─" * 50, "dim"))
    for line in message.split("\n"):
        print(f"    {line}")
    print()


def print_status(message: str, icon: str = "•"):
    """Print a status message."""
    print(f"  {colorize(icon, 'green')} {message}")


def print_analysis_result(result: str):
    """Print the final analysis result with formatting."""
    print("\n")
    print(colorize("  ╔══════════════════════════════════════════════════════╗", "magenta"))
    print(colorize("  ║              📊  ANALYSIS RESULT                    ║", "magenta"))
    print(colorize("  ╚══════════════════════════════════════════════════════╝", "magenta"))
    print()

    # Color-code risk levels in output
    result = result.replace("HIGH", colorize("HIGH", "red"))
    result = result.replace("MEDIUM", colorize("MEDIUM", "yellow"))
    result = result.replace("LOW", colorize("LOW", "green"))

    # Indent and print each line
    for line in result.split("\n"):
        print(f"  {line}")

    print()
    print(colorize("  ════════════════════════════════════════════════════════", "dim"))


# ──────────────────────────────────────────────
# Save result to file
# ──────────────────────────────────────────────

def save_result(result: str, source: str):
    """Save the analysis output to a timestamped file."""
    output_dir = os.path.join(get_base_dir(), "outputs")
    os.makedirs(output_dir, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"analysis_{timestamp}.txt"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("AI Blast Radius Analysis Result\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Source: {source}\n")
        f.write("=" * 60 + "\n\n")
        f.write(result)

    print_status(f"Result saved to: {colorize(filepath, 'cyan')}", "💾")


# ──────────────────────────────────────────────
# CLI Argument Parsing
# ──────────────────────────────────────────────

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="AI Blast Radius Analysis Agent — Analyze code changes with local AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              Local files:     python agent.py
              Git repo:        python agent.py --repo ./my-project
              Git + Jira:      python agent.py --repo ./my-project --jira PROJ-1234
              GitHub PR:       python agent.py --github owner/repo --pr 42
              GitHub + Jira:   python agent.py --github owner/repo --pr 42 --jira PROJ-1234
        """)
    )

    # Input source: Local git repo
    parser.add_argument(
        "--repo", metavar="PATH",
        help="Path to a local Git repo. Triggers blast radius analysis on detected changes."
    )
    parser.add_argument(
        "--base", metavar="REF", default=None,
        help="Git ref to diff against (commit SHA, branch, tag). Default: uncommitted changes."
    )

    # Input source: GitHub PR
    parser.add_argument(
        "--github", metavar="OWNER/REPO",
        help="GitHub repository (e.g. microsoft/vscode). Enables GitHub mode."
    )
    parser.add_argument(
        "--pr", type=int, metavar="NUMBER",
        help="Pull Request number to analyze (requires --github)."
    )
    parser.add_argument(
        "--issue", type=int, metavar="NUMBER",
        help="GitHub Issue number to use as ticket context (optional, with --github)."
    )
    parser.add_argument(
        "--analyze-repo", action="store_true",
        help="Clone and chunk the entire GitHub repo to resolve an issue instead of analyzing a PR."
    )
    parser.add_argument(
        "--token", metavar="TOKEN",
        help="GitHub Personal Access Token for private repos / higher rate limits."
    )

    # Input source: Jira ticket
    parser.add_argument(
        "--jira", metavar="TICKET-ID",
        help="Jira ticket key (e.g. PROJ-1234). Fetches ticket as context."
    )
    parser.add_argument(
        "--jira-url", metavar="URL",
        help="Jira instance URL (e.g. https://yourcompany.atlassian.net)."
    )
    parser.add_argument(
        "--jira-email", metavar="EMAIL",
        help="Jira email for authentication."
    )
    parser.add_argument(
        "--jira-token", metavar="TOKEN",
        help="Jira API token for authentication."
    )

    # General options
    parser.add_argument(
        "--model", metavar="NAME", default=None,
        help=f"Ollama model to use (default: {DEFAULT_MODEL})."
    )
    parser.add_argument(
        "--logs-file", metavar="FILE", default=None,
        help="Path to a local logs file to include."
    )

    args = parser.parse_args()

    # Validations
    if args.pr and not args.github:
        parser.error("--pr requires --github to specify the repository.")
    if args.github and not args.pr and not args.analyze_repo:
        parser.error("--github requires either --pr or --analyze-repo.")
    if args.jira and not args.jira_url:
        parser.error("--jira requires --jira-url to specify your Jira instance URL.")

    return args


# ──────────────────────────────────────────────
# Input loading: Git Repo mode (THE TRIGGER)
# ──────────────────────────────────────────────

def load_git_inputs(args) -> dict[str, str]:
    """
    Scan a local git repo for changes and extract inputs.
    This is the TRIGGER — clone a repo, make changes, run the agent.
    """
    print_section("Scanning local Git repository", "🔍")

    try:
        watcher = GitWatcher(args.repo)
    except ValueError as e:
        print_error("Invalid Git repo", str(e))
        sys.exit(1)

    # Check for changes
    if not args.base and not watcher.has_changes():
        print_error(
            "No changes detected",
            f"No uncommitted changes found in: {args.repo}\n\n"
            "To trigger blast radius analysis:\n"
            "  1. Make some code changes in the repo\n"
            "  2. Re-run: python agent.py --repo ./my-project\n\n"
            "Or diff against a specific commit:\n"
            "  python agent.py --repo ./my-project --base abc1234"
        )
        sys.exit(1)

    # Extract changes
    changes = watcher.get_changes(base_ref=args.base)

    inputs = {
        "code_before": changes["code_before"],
        "code_after": changes["code_after"],
        "repo_structure": changes["repo_structure"],
        "what_changed": changes["what_changed"],
        "logs": "(No runtime logs — analyzing code diff for potential issues)",
    }

    # Show summary of what was detected
    print_status(f"Changed files: {len(changes['changed_files'])}")
    for f in changes["changed_files"][:10]:
        status_icon = {"modified": "✏️", "added": "➕", "deleted": "🗑️"}.get(f["status"], "📄")
        print_status(f"  {status_icon} {f['path']} ({f['status']})")
    if len(changes["changed_files"]) > 10:
        print_status(f"  ... and {len(changes['changed_files']) - 10} more")

    return inputs


# ──────────────────────────────────────────────
# Input loading: GitHub mode
# ──────────────────────────────────────────────

def load_github_inputs(args) -> dict[str, str]:
    """Fetch all input data from a GitHub Pull Request."""
    print_section("Fetching data from GitHub", "🐙")

    handler = GitHubHandler(token=args.token)
    inputs = handler.fetch_pr_data(args.github, args.pr)

    # Add "what_changed" summary for GitHub mode
    inputs["what_changed"] = f"GitHub Pull Request #{args.pr} in {args.github}"

    # If a separate issue is linked, use it as the ticket instead
    if args.issue:
        print_status(f"Fetching linked issue #{args.issue}...")
        issue = handler.fetch_issue(args.github, args.issue)
        inputs["ticket"] = (
            f"Title: {issue['title']}\n"
            f"State: {issue['state']}\n"
            f"Labels: {', '.join(issue['labels'])}\n"
            f"\nDescription:\n{issue['body']}"
        )

    print_status("All GitHub data loaded successfully")
    return inputs


# ──────────────────────────────────────────────
# Input loading: GitHub Repo mode (Chunking)
# ──────────────────────────────────────────────

def load_github_repo_inputs(args, model: str) -> dict[str, str]:
    """Clone a full GitHub repo, chunk it, and find relevant context for the issue."""
    print_section(f"Analyzing Full Repository: {args.github}", "📦")

    # 1. Determine what the problem/query is (issue or jira)
    query_text = ""
    if args.issue:
        handler = GitHubHandler(token=args.token)
        print_status(f"Fetching issue #{args.issue} as query...")
        issue = handler.fetch_issue(args.github, args.issue)
        query_text = (
            f"Title: {issue['title']}\n"
            f"Description:\n{issue['body']}"
        )
    elif args.jira:
        handler = JiraHandler(args.jira_url, args.jira_email, args.jira_token)
        print_status(f"Fetching Jira ticket {args.jira} as query...")
        query_text = handler.format_ticket_for_agent(args.jira)
    else:
        print_error("No query provided", "You must provide an --issue or --jira ticket when using --analyze-repo so the agent knows what problem to solve.")
        sys.exit(1)

    print_status(f"Issue context loaded ({len(query_text)} chars).")

    # 2. Clone the repository
    repo_url = f"https://github.mab.com/{args.github}.git".replace(".mab.com", "") # To avoid fake domains parsing normally, just using standard format
    repo_url = f"https://github.com/{args.github}.git" # Using public github
    temp_dir = tempfile.mkdtemp(prefix="blast_repo_")
    print_status(f"Cloning {repo_url} into {temp_dir}...")
    try:
        subprocess.run(["git", "clone", "--depth", "1", repo_url, temp_dir], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print_status("Clone successful.")
    except subprocess.CalledProcessError:
        print_error("Clone failed", f"Could not clone {repo_url}")
        shutil.rmtree(temp_dir, ignore_errors=True)
        sys.exit(1)

    # 3. Chunk and find relevant files via Ollama embeddings
    # If the user passed token limits or such, we can adjust top_k.
    print_status("Finding relevant code chunks...")
    top_chunks = repo_chunker.find_relevant_chunks(query_text, temp_dir, model=model, top_k=5)

    chunk_texts = []
    for snippet in top_chunks:
        chunk_texts.append(f"--- \n{snippet['text']}\n---")
    
    combined_code = "\n".join(chunk_texts)
    
    # 4. Cleanup
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except:
        pass

    return {
        "what_changed": f"Analyzing Full Codebase {args.github} for issue",
        "ticket": query_text,
        "logs": "(None)",
        "code_before": combined_code,
        "code_after": "(This is a codebase analysis task, not a diff. The chunks above represent the current state of the code relevant to the ticket.)",
        "repo_structure": "(Files relevant to issue are retrieved via vector search)"
    }


# ──────────────────────────────────────────────
# Jira ticket overlay
# ──────────────────────────────────────────────

def overlay_jira_ticket(inputs: dict[str, str], args) -> dict[str, str]:
    """
    Fetch a Jira ticket and use it as the ticket context.
    Works with ANY input mode (files, git, github).
    """
    print_section("Fetching Jira ticket", "🎫")

    handler = JiraHandler(
        base_url=args.jira_url,
        email=args.jira_email,
        api_token=args.jira_token,
    )

    print_status(f"Fetching {args.jira} from {args.jira_url}...")
    ticket_text = handler.format_ticket_for_agent(args.jira)
    inputs["ticket"] = ticket_text
    print_status(f"Jira ticket {colorize(args.jira, 'cyan')} loaded as context")

    return inputs


# ──────────────────────────────────────────────
# Overlay: local logs file
# ──────────────────────────────────────────────

def overlay_logs_file(inputs: dict[str, str], logs_file: str) -> dict[str, str]:
    """Load a local logs file and use it as the logs context."""
    try:
        logs_path = os.path.abspath(logs_file)
        with open(logs_path, "r", encoding="utf-8") as f:
            inputs["logs"] = f.read().strip()
        print_status(f"Logs loaded from: {logs_path}")
    except FileNotFoundError:
        print_error("Logs file not found", f"Could not find: {logs_file}")
    return inputs


# ──────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────

def main():
    """Run the Blast Radius Analysis Agent."""
    args = parse_args()
    print_banner()

    # Determine input mode
    if args.repo:
        mode = "git"
        mode_label = f"Git Repo → {os.path.abspath(args.repo)}"
        mode_icon = "🔍"
    elif args.github and args.analyze_repo:
        mode = "github_repo"
        mode_label = f"Full GitHub Repo → {args.github}"
        mode_icon = "📦"
    elif args.github:
        mode = "github_pr"
        mode_label = f"GitHub PR → {args.github}#{args.pr}"
        mode_icon = "🐙"
    else:
        mode = "local"
        mode_label = "Local Text Files"
        mode_icon = "📂"

    print_status(f"Mode: {colorize(mode_label, 'cyan')}", mode_icon)
    if args.jira:
        print_status(f"Jira: {colorize(args.jira, 'cyan')}", "🎫")

    # Step 1: Check Ollama connectivity
    print_section("Checking Ollama connection", "🔌")
    if not check_ollama_connection():
        print_error(
            "Ollama not running",
            "Could not connect to Ollama at http://localhost:11434\n\n"
            "Start Ollama first:\n"
            "  1. Install Ollama from https://ollama.com\n"
            "  2. Run: ollama serve\n"
            "  3. Pull a model: ollama pull mistral\n"
            "  4. Re-run this agent: python agent.py"
        )
        sys.exit(1)
    print_status("Ollama is running")

    # Step 2: Select model
    if args.model:
        model = args.model
    else:
        model = select_model()
    print_status(f"Using model: {colorize(model, 'cyan')}")

    # Step 3: Load inputs based on mode
    if mode == "git":
        inputs = load_git_inputs(args)
        if "ticket" not in inputs:
            inputs["ticket"] = "(No ticket provided — analyze based on code changes only)"
    elif mode == "github_repo":
        inputs = load_github_repo_inputs(args, model)
    elif mode == "github_pr":
        inputs = load_github_inputs(args)
    else:
        print_section("Loading input files", "📂")
        inputs = load_input_files()
        for key, filename in INPUT_FILES.items():
            size = len(inputs[key])
            print_status(f"{filename:<22} ({size:,} chars)")

    # Step 3b: Overlay Jira ticket if provided (works with ANY mode)
    if args.jira:
        inputs = overlay_jira_ticket(inputs, args)

    # Step 3c: Overlay local logs file if provided
    if args.logs_file:
        inputs = overlay_logs_file(inputs, args.logs_file)

    # Step 4: Build prompt
    print_section("Constructing analysis prompt", "🧠")
    prompt = build_prompt(inputs)
    print_status(f"Prompt size: {len(prompt):,} characters")

    # Step 5: Query Ollama (AI Inference)
    print_section("Analyzing with AI model", "🤖")
    print(colorize("  Streaming AI response...\n", "dim"))
    print(colorize("  " + "─" * 50, "dim"))
    print()

    result = query_ollama(prompt, model)

    # Step 6: Display formatted result
    print_analysis_result(result)

    # Step 7: Save result
    source_desc = mode_label
    if args.jira:
        source_desc += f" + Jira {args.jira}"
    save_result(result, source_desc)

    print_status(f"Analysis complete ✓\n", "🎯")


if __name__ == "__main__":
    main()
