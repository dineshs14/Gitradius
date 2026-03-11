# 🔍 AI Blast Radius Analysis Agent

A local AI-powered agent that analyzes code changes and predicts the
**blast radius** — which modules are impacted and how risky the change is.

> **Powered by Ollama (Local AI)** — No cloud APIs needed. Runs 100% offline.

---

## 🎯 4 Ways to Trigger Analysis

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
ollama pull mistral
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run It

**Easiest: Clone a repo, make a change, trigger analysis:**
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

**Analyze a GitHub PR:**
```bash
python agent.py --github facebook/react --pr 28000
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
├── agent.py              # Main CLI agent (orchestrates everything)
├── git_watcher.py        # Git change detection (THE TRIGGER)
├── github_handler.py     # GitHub PR integration
├── jira_handler.py       # Jira ticket integration
├── prompt.txt            # AI prompt template (editable)
├── ticket.txt            # Example: bug ticket
├── logs.txt              # Example: error logs
├── code_before.txt       # Example: original code
├── code_after.txt        # Example: modified code
├── repo_structure.txt    # Example: repo layout
├── requirements.txt      # Python dependencies
├── README.md             # This file
└── outputs/              # Auto-saved analysis results
    └── analysis_*.txt
```

---

## ⚙️ All CLI Options

| Flag | Description |
|------|-------------|
| `--repo PATH` | Local Git repo path (triggers auto-detection) |
| `--base REF` | Git ref to diff against (default: uncommitted changes) |
| `--github OWNER/REPO` | GitHub repository for PR mode |
| `--pr NUMBER` | Pull Request number |
| `--issue NUMBER` | GitHub Issue number (optional context) |
| `--token TOKEN` | GitHub Personal Access Token |
| `--jira TICKET-ID` | Jira ticket key (e.g. PROJ-1234) |
| `--jira-url URL` | Jira instance URL |
| `--jira-email EMAIL` | Jira email for auth |
| `--jira-token TOKEN` | Jira API token for auth |
| `--model NAME` | Ollama model override (default: mistral) |
| `--logs-file FILE` | Local error log file to include |

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

---

## 📜 License

MIT — Use freely for learning, prototyping, and experimentation.
