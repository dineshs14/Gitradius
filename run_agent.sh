#!/usr/bin/env bash
# =====================================================================
# Blast Radius Agent — Shell Launcher
# =====================================================================
#
# Usage examples:
#
#   # Demo / pseudo mode (no credentials needed)
#   bash run_agent.sh --file /path/to/project --pseudo
#
#   # Pseudo + specific fake Jira ticket and GitHub PR
#   bash run_agent.sh --file /path/to/project --pseudo \
#       --pseudo-jira DEMO-42 --pseudo-github my-org/my-app --pseudo-pr 7
#
#   # Real Jira + local file/directory analysis
#   bash run_agent.sh --file /path/to/project \
#       --jira PROJ-1234 \
#       --jira-url https://yourcompany.atlassian.net \
#       --jira-email you@company.com \
#       --jira-token YOUR_JIRA_API_TOKEN
#
#   # Real GitHub Pull Request
#   bash run_agent.sh --file /path/to/project \
#       --github owner/repo \
#       --pr 99 \
#       --token ghp_XXXXXXXXXXXX
#
#   # Full: real Jira + real GitHub PR + RAG for big repos
#   bash run_agent.sh --file /large/monorepo \
#       --jira PROJ-1234 --jira-url https://co.atlassian.net \
#       --jira-email me@co.com --jira-token <jira-token> \
#       --github owner/repo --pr 42 --token <github-token> \
#       --rag --top-k 8 --model codellama
#
#   # Single file analysis
#   bash run_agent.sh --file /path/to/changed_file.py --pseudo
#
# =====================================================================

set -euo pipefail

# ─── Colour helpers ──────────────────────────────────────────────
RED='\033[91m'; GREEN='\033[92m'; YELLOW='\033[93m'
CYAN='\033[96m'; BOLD='\033[1m'; RESET='\033[0m'

ok()   { echo -e "  ${GREEN}✓${RESET} $*"; }
info() { echo -e "  ${CYAN}•${RESET} $*"; }
warn() { echo -e "  ${YELLOW}⚠${RESET} $*"; }
die()  { echo -e "  ${RED}✖ ERROR${RESET}: $*" >&2; exit 1; }

# ─── Banner ───────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}${BOLD}  ╔══════════════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}${BOLD}  ║         🤖  Blast Radius Agent  —  Shell Launcher        ║${RESET}"
echo -e "${CYAN}${BOLD}  ╚══════════════════════════════════════════════════════════╝${RESET}"
echo ""

# ─── Defaults ─────────────────────────────────────────────────────
FILE_PATH=""
PSEUDO=false
PSEUDO_JIRA=""
PSEUDO_GITHUB=""
PSEUDO_PR=1
JIRA_TICKET=""
JIRA_URL=""
JIRA_EMAIL=""
JIRA_TOKEN=""
GITHUB_REPO=""
GITHUB_PR=""
GITHUB_TOKEN=""
MODEL=""
RAG=false
TOP_K=6
EXTRA_ARGS=()

# ─── Argument parsing ─────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --file)           FILE_PATH="$2";      shift 2 ;;
        --pseudo)         PSEUDO=true;         shift   ;;
        --pseudo-jira)    PSEUDO_JIRA="$2";    shift 2 ;;
        --pseudo-github)  PSEUDO_GITHUB="$2";  shift 2 ;;
        --pseudo-pr)      PSEUDO_PR="$2";      shift 2 ;;
        --jira)           JIRA_TICKET="$2";    shift 2 ;;
        --jira-url)       JIRA_URL="$2";       shift 2 ;;
        --jira-email)     JIRA_EMAIL="$2";     shift 2 ;;
        --jira-token)     JIRA_TOKEN="$2";     shift 2 ;;
        --github)         GITHUB_REPO="$2";    shift 2 ;;
        --pr)             GITHUB_PR="$2";      shift 2 ;;
        --token)          GITHUB_TOKEN="$2";   shift 2 ;;
        --model)          MODEL="$2";          shift 2 ;;
        --rag)            RAG=true;            shift   ;;
        --top-k)          TOP_K="$2";          shift 2 ;;
        --help|-h)
            sed -n '2,50p' "$0" | grep '^#' | sed 's/^# \?//'
            exit 0 ;;
        *)
            die "Unknown argument: $1  (run with --help for usage)"
    esac
done

# ─── Resolve script directory ─────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─── Validate file path ───────────────────────────────────────────
if [[ -z "$FILE_PATH" && -z "$GITHUB_REPO" && -z "$JIRA_TICKET" && -z "$PSEUDO_JIRA" ]]; then
    die "You must supply at least --file, --github, --jira, or --pseudo-jira.\n    Run:  bash run_agent.sh --help"
fi

if [[ -n "$FILE_PATH" ]]; then
    FILE_PATH="$(realpath "$FILE_PATH" 2>/dev/null || echo "$FILE_PATH")"
    [[ -e "$FILE_PATH" ]] || die "Path not found: $FILE_PATH"
    ok "Source path : $FILE_PATH"
fi

# ─── Python detection ─────────────────────────────────────────────
PYTHON=""
for cmd in python3 python python3.12 python3.11 python3.10; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done
[[ -n "$PYTHON" ]] || die "Python not found. Install Python 3.10+ first."
ok "Python      : $($PYTHON --version)"

# ─── Virtual environment (activate if present) ────────────────────
if [[ -f "$SCRIPT_DIR/.venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/.venv/bin/activate"
    ok "venv        : activated (.venv)"
elif [[ -f "$SCRIPT_DIR/venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/venv/bin/activate"
    ok "venv        : activated (venv)"
else
    warn "No .venv found. Using system Python. Consider: python -m venv .venv"
fi

# ─── Dependency check ─────────────────────────────────────────────
if ! "$PYTHON" -c "import requests" &>/dev/null; then
    warn "'requests' not found. Installing …"
    "$PYTHON" -m pip install -q requests
fi

# ─── Ollama check ─────────────────────────────────────────────────
info "Checking Ollama …"
if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
    ok "Ollama      : running"
else
    die "Ollama is not running.\n    Install : https://ollama.com\n    Start   : ollama serve\n    Pull    : ollama pull mistral"
fi

# ─── Build Python argument list ───────────────────────────────────
PY_ARGS=()

[[ -n "$FILE_PATH"    ]] && PY_ARGS+=("--file"        "$FILE_PATH")
[[ "$PSEUDO" == true  ]] && PY_ARGS+=("--pseudo")
[[ -n "$PSEUDO_JIRA"  ]] && PY_ARGS+=("--pseudo-jira"   "$PSEUDO_JIRA")
[[ -n "$PSEUDO_GITHUB"]] && PY_ARGS+=("--pseudo-github" "$PSEUDO_GITHUB")
[[ "$PSEUDO_PR" -gt 0 ]] && [[ -n "$PSEUDO_GITHUB" ]] && PY_ARGS+=("--pseudo-pr" "$PSEUDO_PR")
[[ -n "$JIRA_TICKET"  ]] && PY_ARGS+=("--jira"        "$JIRA_TICKET")
[[ -n "$JIRA_URL"     ]] && PY_ARGS+=("--jira-url"    "$JIRA_URL")
[[ -n "$JIRA_EMAIL"   ]] && PY_ARGS+=("--jira-email"  "$JIRA_EMAIL")
[[ -n "$JIRA_TOKEN"   ]] && PY_ARGS+=("--jira-token"  "$JIRA_TOKEN")
[[ -n "$GITHUB_REPO"  ]] && PY_ARGS+=("--github"      "$GITHUB_REPO")
[[ -n "$GITHUB_PR"    ]] && PY_ARGS+=("--pr"          "$GITHUB_PR")
[[ -n "$GITHUB_TOKEN" ]] && PY_ARGS+=("--token"       "$GITHUB_TOKEN")
[[ -n "$MODEL"        ]] && PY_ARGS+=("--model"       "$MODEL")
[[ "$RAG" == true     ]] && PY_ARGS+=("--rag")
[[ "$TOP_K" -ne 6     ]] && PY_ARGS+=("--top-k"       "$TOP_K")

# ─── Run ──────────────────────────────────────────────────────────
echo ""
info "Launching agentic_runner.py …"
echo ""

cd "$SCRIPT_DIR"
"$PYTHON" agentic_runner.py "${PY_ARGS[@]}"

echo ""
ok "Done. Check outputs/ for the saved report."
