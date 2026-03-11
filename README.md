# 🤖 Agentic Blast Radius Analysis Agent

A **fully autonomous, local AI agent** that analyses code changes and predicts the
**blast radius** — which modules are impacted and how risky the change is.

> **Powered by Ollama (Local AI)** — No cloud APIs needed. Runs 100% offline.

---

## ✨ What's New — Agentic Mode

| Feature | Details |
|---|---|
| 🤖 **ReAct Agentic Loop** | LLM plans its own tool calls, executes, reflects, then writes the report |
| 📁 **Any File Type** | Python, JS, Go, Rust, SQL, YAML, Markdown, shell scripts, configs — auto-detected |
| 🏗 **Big Repo Support** | Repos with 200+ files automatically switch to RAG (embedding search) |
| 🎭 **Pseudo / Demo Mode** | Realistic mock Jira tickets + GitHub PRs — zero credentials needed |
| 🐚 **Shell Launchers** | `run_agent.sh` (Bash/WSL) and `run_agent.ps1` (PowerShell) |
| 🎫 **Real or Pseudo Jira** | Works with live Atlassian API or built-in mock data |
| 🐙 **Real or Pseudo GitHub** | Works with real GitHub PRs or built-in demo diffs |

---

## 🎯 Trigger Modes

### New Agentic Runner (`agentic_runner.py`)

| Mode | Command |
|------|---|
| 🎭 Demo (no credentials) | `python agentic_runner.py --file ./project --pseudo` |
| 📁 Any file/dir | `python agentic_runner.py --file ./my-project --pseudo` |
| 🎫 Real Jira | `python agentic_runner.py --file ./my-project --jira PROJ-1 --jira-url https://...` |
| 🐙 Real GitHub PR | `python agentic_runner.py --file . --github owner/repo --pr 42 --token ghp_xxx` |
| 🏗 Big repo + RAG | `python agentic_runner.py --file /large/monorepo --pseudo --rag` |

### Classic Runner (`agent.py`)

| Mode | Command | Use Case |
|------|---------|----------|
| 📂 **Local Files** | `python agent.py` | Paste code into text files manually |
| 🔍 **Git Repo** | `python agent.py --repo ./my-project` | Clone a repo, make changes, auto-detect |
| 🐙 **GitHub PR** | `python agent.py --github owner/repo --pr 42` | Analyze any Pull Request |
| 🎫 **+ Jira** | `python agent.py --repo ./my-project --jira PROJ-1234` | Add Jira ticket context to any mode |

---

## 🚀 Quick Start

### 1. Install Ollama + Pull a Model
```bash
# Install from https://ollama.com, then:
ollama serve          # start the server
ollama pull mistral   # or: codellama, deepseek-coder, llama3
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3a. Agentic Runner — Demo Mode (recommended first run)

**Windows PowerShell:**
```powershell
.\run_agent.ps1 -File "." -Pseudo
```

**Linux / macOS / WSL / Git Bash:**
```bash
bash run_agent.sh --file . --pseudo
```

**Or call Python directly:**
```bash
python agentic_runner.py --file . --pseudo
```

### 3b. Classic Runner — Git Repo Mode
```bash
git clone https://github.com/some/project.git
cd project
# ... make some code changes ...
python agent.py --repo .
```

**With Jira ticket context:**
```bash
python agent.py --repo . --jira PROJ-1234 --jira-url https://yourcompany.atlassian.net
```

---

## 🔍 Git Repo Trigger (Clone → Change → Analyze)

This is the **core feature**. Clone any repo, make changes, and the agent
auto-detects what changed and triggers blast radius analysis.

```bash
# Step 1: Clone a repo
git clone https://github.com/your-org/your-app.git
cd your-app

# Step 2: Make changes (edit files, fix bugs, add features)
# ... edit some files ...

# Step 3: Trigger blast radius analysis
python agent.py --repo .

# Or diff against a specific commit/branch:
python agent.py --repo . --base main
python agent.py --repo . --base abc1234
```

**What it detects automatically:**
- All modified, added, and deleted files
- Code before vs code after (from git diff)
- Full repository structure
- Recent commit history for context

---

## 🎫 Jira Integration

Fetch real ticket details from Jira to give the AI better context.
Works with **any input mode** (files, git, GitHub).

```bash
# Git repo + Jira ticket
python agent.py --repo ./my-project --jira PROJ-1234 \
  --jira-url https://yourcompany.atlassian.net \
  --jira-email you@company.com \
  --jira-token your-jira-api-token

# GitHub PR + Jira ticket
python agent.py --github owner/repo --pr 42 --jira PROJ-1234 \
  --jira-url https://yourcompany.atlassian.net

# Local files + Jira ticket
python agent.py --jira PROJ-1234 --jira-url https://yourcompany.atlassian.net
```

**Getting a Jira API Token:**
1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Use with `--jira-token`

**What it fetches from Jira:**
- Ticket title, description, priority, status
- Assignee, reporter, labels, components
- Ticket comments (used as supplementary context)

---

## 📊 What the AI Tells You

The output includes 6 clear sections:

```
What Was Done:
  → Short, specific description of what the code change does

Root Cause:
  → Why it broke (or what risk the change introduces)

Impacted Modules:
  → Every file affected, with one-line explanation per file

Risk Level:
  → LOW / MEDIUM / HIGH with justification

Suggested Fix:
  → Copy-paste-ready code fix

Explanation:
  → Step-by-step reasoning of how the impact spreads
```

---

## 📁 Project Structure

```
blast_radius_agent/
│
│  ── Agentic pipeline (new) ──
├── agentic_runner.py     # 🤖 ReAct agentic orchestrator (main entry point)
├── pseudo_setup.py       # 🎭 Mock Jira + GitHub — zero credentials needed
├── run_agent.sh          # 🐚 Bash launcher  (Linux / macOS / WSL / Git Bash)
├── run_agent.ps1         # 🪟 PowerShell launcher (Windows)
│
│  ── Classic pipeline ──
├── agent.py              # Classic CLI agent
├── git_watcher.py        # Git change detection
├── github_handler.py     # Real GitHub PR integration
├── jira_handler.py       # Real Jira ticket integration
├── repo_chunker.py       # Universal file scanner + RAG chunker
│
│  ── Config / templates ──
├── prompt.txt            # AI prompt template (editable)
├── ticket.txt            # Example: bug ticket (local-files mode)
├── logs.txt              # Example: error logs
├── code_before.txt       # Example: original code
├── code_after.txt        # Example: modified code
├── repo_structure.txt    # Example: repo layout
├── requirements.txt      # Python dependencies
├── README.md             # This file
│
└── outputs/              # Auto-saved analysis reports
    └── agentic_analysis_*.txt
    └── analysis_*.txt
```

---

## ⚙️ All CLI Options

### `agentic_runner.py` (new)

| Flag | Description |
|------|-------------|
| `--file PATH` | File, directory, or git repo to scan (any file type) |
| `--pseudo` | Demo mode — no credentials needed |
| `--pseudo-jira TICKET` | Fake Jira ticket ID (e.g. `DEMO-42`) |
| `--pseudo-github REPO` | Fake GitHub repo (e.g. `my-org/my-app`) |
| `--pseudo-pr NUMBER` | Fake PR number (default: 1) |
| `--jira TICKET-ID` | Real Jira ticket key |
| `--jira-url URL` | Real Jira instance URL |
| `--jira-email EMAIL` | Jira email for auth |
| `--jira-token TOKEN` | Jira API token |
| `--github OWNER/REPO` | Real GitHub repository |
| `--pr NUMBER` | Pull Request number |
| `--token TOKEN` | GitHub Personal Access Token |
| `--model NAME` | Ollama model override (default: mistral) |
| `--rag` | Force RAG chunking (auto-enabled for 200+ file repos) |
| `--top-k N` | Number of RAG chunks to retrieve (default: 6) |

### `agent.py` (classic)

| Flag | Description |
|------|-------------|
| `--repo PATH` | Local Git repo path (triggers auto-detection) |
| `--base REF` | Git ref to diff against (default: uncommitted changes) |
| `--github OWNER/REPO` | GitHub repository for PR mode |
| `--pr NUMBER` | Pull Request number |
| `--issue NUMBER` | GitHub Issue number (optional context) |
| `--analyze-repo` | Clone + chunk entire GitHub repo via RAG |
| `--token TOKEN` | GitHub Personal Access Token |
| `--jira TICKET-ID` | Jira ticket key (e.g. PROJ-1234) |
| `--jira-url URL` | Jira instance URL |
| `--jira-email EMAIL` | Jira email for auth |
| `--jira-token TOKEN` | Jira API token for auth |
| `--model NAME` | Ollama model override (default: mistral) |
| `--logs-file FILE` | Local error log file to include |

---

## 🎭 Pseudo / Demo Mode

Run the full agentic pipeline with **zero credentials** — great for demos,
development, and first-time testing.

```powershell
# Windows
.\run_agent.ps1 -File "C:\your\project" -Pseudo
.\run_agent.ps1 -File "C:\your\project" -Pseudo -PseudoJira "DEMO-42" -PseudoGithub "org/repo"
```

```bash
# Linux / macOS / WSL
bash run_agent.sh --file /your/project --pseudo
bash run_agent.sh --file /your/project --pseudo --pseudo-jira DEMO-42 --pseudo-github org/repo
```

`pseudo_setup.py` ships with **5 realistic ticket types** (memory leak, XSS, DB timeout,
OAuth PKCE, CI migration) and matching multi-language diffs (Python, JavaScript, SQL, Go, YAML).

---

## 🏗 Large Repository Support

For repos with **200+ files**, the agent automatically enables RAG (Retrieval-Augmented
Generation):

1. Scan all text files (binary files skipped by content detection)
2. Chunk files into overlapping segments
3. Embed chunks and the Jira/ticket query via Ollama
4. Retrieve top-K most relevant chunks by cosine similarity
5. Feed only the relevant code into the prompt

```bash
# Force RAG even for small repos
python agentic_runner.py --file /large/monorepo --pseudo --rag --top-k 8
```

**File types handled automatically:**
`.py` `.js` `.ts` `.jsx` `.tsx` `.go` `.rs` `.java` `.kt` `.rb` `.php` `.cs` `.cpp`
`.c` `.h` `.sh` `.bash` `.zsh` `.ps1` `.sql` `.yaml` `.yml` `.json` `.toml` `.ini`
`.env` `.md` `.rst` `.txt` `.xml` `.html` `.css` `.scss` `.dockerfile` and more.

---

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| `Ollama not running` | Run: `ollama serve` |
| `No models found` | Run: `ollama pull mistral` |
| `Not a git repository` | Make sure `--repo` points to a folder with `.git` |
| `No changes detected` | Make some code changes first, then re-run |
| `Jira 401` | Check your email and API token |
| `GitHub 403` | Use `--token` to avoid rate limits |
| PowerShell execution policy | Run: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `pseudo_setup not found` | Make sure `pseudo_setup.py` is in the same folder as `agentic_runner.py` |

---

## 📜 License

MIT — Use freely for learning, prototyping, and experimentation.
