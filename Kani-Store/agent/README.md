# Kani-Store Local AI Engineering Agent

A **zero-API-key** local agent that monitors your Kani-Store project for:
- 🎫 Jira ticket updates (file-based prototype)
- 🐙 GitHub commit activity (reads real git log **or** simulated data)
- ⚡ Code change impact analysis (real git diff + Kani dependency graph)
- 💡 Smart recommendations based on risk level
- 🤖 Optional Ollama AI deep analysis (no cloud required)

---

## Quick Start

```bash
# From this directory
cd E:\JOB COPilot\Kani-Store\agent

# Full analysis
python kani_agent.py

# Only Jira updates
python kani_agent.py --jira

# Only GitHub commits
python kani_agent.py --github

# Only code impact
python kani_agent.py --code

# Full + AI deep analysis (requires Ollama)
python kani_agent.py --ai

# Watch mode (re-runs every 60 seconds)
python kani_agent.py --watch
```

---

## How It Works

```
kani_agent.py
├── Jira Tracker     ← reads jira_state.json, diffs with .last_state.json
├── GitHub Monitor   ← reads 'git log' (real) or github_state.json (simulated)
├── Code Analyzer    ← 'git status' + 'git diff' → Kani dependency graph
├── Recommendations  ← aggregates all 3 results into actionable steps
└── Ollama AI        ← sends diff + context to local LLM (optional)
```

### Kani-Store Dependency Graph

The agent knows your project structure:

```
App.tsx  ←────── types.ts ──────── (root)
App.tsx  ←────── constants.ts ──── (root)
App.tsx  ←────── services/geminiService.ts
App.tsx  ←────── components/Icons.tsx
index.tsx ←───── App.tsx
```

**Critical files** (HIGH risk if changed): `App.tsx`, `types.ts`, `constants.ts`, `services/geminiService.ts`

---

## Simulate Jira Changes

Edit `jira_state.json` to add/update tickets. On next run, the agent detects:
- New tickets (not in `.last_state.json`)
- Status changes (Open → In Progress → Done)
- New comments added to tickets
- Description updates

**Ticket format:**
```json
{
  "id": "KS-107",
  "title": "My new ticket",
  "status": "Open",
  "priority": "High",
  "comments": []
}
```

Priority values: `Critical`, `Blocker`, `High`, `Medium`, `Low`
Status values: `Open`, `In Progress`, `In Review`, `Done`, `Closed`

---

## Simulate GitHub Changes

Edit `github_state.json` to add commits. The agent also reads **real `git log`** 
automatically — so any actual commits you make will appear here.

---

## Enable AI Analysis (Optional)

```bash
# Install Ollama
https://ollama.ai

# Start Ollama
ollama serve

# Pull a model (mistral is fast and good)
ollama pull mistral

# Run with AI
python kani_agent.py --ai
```

The AI receives: your diff, Jira tickets, and latest commit context, then returns
a structured analysis with risk level and next steps.

---

## Output Files

Each run saves a timestamped report in `outputs/`:
```
outputs/
  kani_analysis_20250115_143022.txt
  kani_analysis_20250115_160511.txt
```

---

## Files

| File | Purpose |
|------|---------|
| `kani_agent.py` | Main agent script |
| `jira_state.json` | Simulated Jira tickets (edit this!) |
| `github_state.json` | Simulated GitHub commits (fallback) |
| `.last_state.json` | Auto-generated: tracks last run state |
| `outputs/` | Auto-generated: saved analysis reports |
