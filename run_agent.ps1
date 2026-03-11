#Requires -Version 5.1
<#
.SYNOPSIS
    Blast Radius Agent — PowerShell Launcher (Windows)

.DESCRIPTION
    Orchestrates the agentic blast-radius analysis pipeline.
    Accepts any file/directory, connects to real or pseudo Jira and GitHub,
    and runs a local AI model (Ollama) to produce a detailed impact report.

.PARAMETER File
    Path to a file, directory, or git repo to analyze.

.PARAMETER Pseudo
    Use mock Jira & GitHub data. No credentials required. Great for demos.

.PARAMETER PseudoJira
    Fake Jira ticket ID to simulate when --Pseudo is set (e.g. DEMO-42).

.PARAMETER PseudoGithub
    Fake GitHub repo when --Pseudo is set (e.g. my-org/my-app).

.PARAMETER PseudoPr
    Fake PR number for pseudo GitHub (default: 1).

.PARAMETER Jira
    Real Jira ticket key, e.g. PROJ-1234.

.PARAMETER JiraUrl
    Real Jira base URL, e.g. https://yourcompany.atlassian.net.

.PARAMETER JiraEmail
    Your Jira email for authentication.

.PARAMETER JiraToken
    Your Jira API token.

.PARAMETER Github
    Real GitHub repo in owner/repo format, e.g. microsoft/vscode.

.PARAMETER Pr
    Pull Request number (requires -Github).

.PARAMETER Token
    GitHub Personal Access Token (for private repos / higher rate limits).

.PARAMETER Model
    Ollama model name (default: mistral). Options: codellama, deepseek-coder, etc.

.PARAMETER Rag
    Enable RAG (embedding) chunking. Auto-enabled for repos with >200 files.

.PARAMETER TopK
    Number of RAG chunks to retrieve (default: 6).

.EXAMPLE
    # Demo / pseudo mode
    .\run_agent.ps1 -File "C:\projects\my-app" -Pseudo

.EXAMPLE
    # Pseudo with specific ticket and PR
    .\run_agent.ps1 -File "C:\projects\my-app" -Pseudo `
        -PseudoJira "DEMO-42" -PseudoGithub "my-org/my-app" -PseudoPr 3

.EXAMPLE
    # Real Jira + local files
    .\run_agent.ps1 -File "C:\projects\my-app" `
        -Jira "PROJ-1234" `
        -JiraUrl "https://myco.atlassian.net" `
        -JiraEmail "me@myco.com" `
        -JiraToken "YOUR_JIRA_TOKEN"

.EXAMPLE
    # Real GitHub PR
    .\run_agent.ps1 -File "C:\projects\my-app" `
        -Github "owner/repo" -Pr 42 -Token "ghp_XXXXXX"

.EXAMPLE
    # Large repo with RAG
    .\run_agent.ps1 -File "C:\large\monorepo" -Pseudo -Rag -TopK 8 -Model "codellama"

.EXAMPLE
    # Single file
    .\run_agent.ps1 -File "C:\projects\my-app\src\auth.py" -Pseudo
#>

[CmdletBinding()]
param(
    [string] $File,
    [switch] $Pseudo,
    [string] $PseudoJira   = "",
    [string] $PseudoGithub = "",
    [int]    $PseudoPr     = 1,
    [string] $Jira         = "",
    [string] $JiraUrl      = "",
    [string] $JiraEmail    = "",
    [string] $JiraToken    = "",
    [string] $Github       = "",
    [int]    $Pr           = 0,
    [string] $Token        = "",
    [string] $Model        = "",
    [switch] $Rag,
    [int]    $TopK         = 6
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ─── Helpers ──────────────────────────────────────────────────────
function Write-Ok   ([string]$msg) { Write-Host "  " -NoNewline; Write-Host "v" -ForegroundColor Green  -NoNewline; Write-Host " $msg" }
function Write-Info ([string]$msg) { Write-Host "  " -NoNewline; Write-Host "." -ForegroundColor Cyan   -NoNewline; Write-Host " $msg" }
function Write-Warn ([string]$msg) { Write-Host "  " -NoNewline; Write-Host "!" -ForegroundColor Yellow -NoNewline; Write-Host " $msg" }
function Write-Die  ([string]$msg) {
    Write-Host "  " -NoNewline
    Write-Host "X ERROR: " -ForegroundColor Red -NoNewline
    Write-Host $msg
    exit 1
}

# ─── Banner ───────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║     🤖  Blast Radius Agent  —  PowerShell Launcher       ║" -ForegroundColor Cyan
Write-Host "  ╚══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ─── Script directory ─────────────────────────────────────────────
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# ─── Validate inputs ──────────────────────────────────────────────
if (-not $File -and -not $Github -and -not $Jira -and -not $PseudoJira) {
    Write-Die "Provide at least --File, --Github, --Jira, or --PseudoJira.`n    For a demo: .\run_agent.ps1 -File . -Pseudo"
}

if ($File) {
    $File = (Resolve-Path -Path $File -ErrorAction SilentlyContinue)?.Path
    if (-not $File -or -not (Test-Path $File)) {
        Write-Die "Path not found: $File"
    }
    Write-Ok "Source path : $File"
}

# ─── Python detection ─────────────────────────────────────────────
$PythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3\.(1[0-9]|[2-9]\d)") {
            $PythonCmd = $cmd
            break
        }
    } catch { }
}
if (-not $PythonCmd) {
    Write-Die "Python 3.10+ not found. Download from https://python.org"
}
$pyVer = & $PythonCmd --version 2>&1
Write-Ok "Python      : $pyVer"

# ─── Activate virtual environment if present ──────────────────────
$VenvActivate = Join-Path $ScriptDir ".venv\Scripts\Activate.ps1"
$VenvActivate2 = Join-Path $ScriptDir "venv\Scripts\Activate.ps1"
if (Test-Path $VenvActivate) {
    & $VenvActivate
    Write-Ok "venv        : activated (.venv)"
} elseif (Test-Path $VenvActivate2) {
    & $VenvActivate2
    Write-Ok "venv        : activated (venv)"
} else {
    Write-Warn "No .venv found. Using system Python. Consider: python -m venv .venv"
}

# ─── Dependency check ─────────────────────────────────────────────
$reqCheck = & $PythonCmd -c "import requests" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Warn "'requests' not installed. Installing..."
    & $PythonCmd -m pip install -q requests
}

# ─── Ollama check ─────────────────────────────────────────────────
Write-Info "Checking Ollama..."
try {
    $ollamaResp = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 5 -ErrorAction Stop
    Write-Ok "Ollama      : running"
} catch {
    Write-Die "Ollama is not running.`n    Install  : https://ollama.com`n    Start    : ollama serve`n    Pull     : ollama pull mistral"
}

# ─── Build Python argument list ───────────────────────────────────
$PyArgs = @()

if ($File)          { $PyArgs += "--file";         $PyArgs += $File }
if ($Pseudo)        { $PyArgs += "--pseudo" }
if ($PseudoJira)    { $PyArgs += "--pseudo-jira";  $PyArgs += $PseudoJira }
if ($PseudoGithub)  { $PyArgs += "--pseudo-github"; $PyArgs += $PseudoGithub }
if ($PseudoGithub -and $PseudoPr -gt 0) {
                      $PyArgs += "--pseudo-pr";    $PyArgs += $PseudoPr }
if ($Jira)          { $PyArgs += "--jira";         $PyArgs += $Jira }
if ($JiraUrl)       { $PyArgs += "--jira-url";     $PyArgs += $JiraUrl }
if ($JiraEmail)     { $PyArgs += "--jira-email";   $PyArgs += $JiraEmail }
if ($JiraToken)     { $PyArgs += "--jira-token";   $PyArgs += $JiraToken }
if ($Github)        { $PyArgs += "--github";       $PyArgs += $Github }
if ($Pr -gt 0)      { $PyArgs += "--pr";           $PyArgs += $Pr }
if ($Token)         { $PyArgs += "--token";        $PyArgs += $Token }
if ($Model)         { $PyArgs += "--model";        $PyArgs += $Model }
if ($Rag)           { $PyArgs += "--rag" }
if ($TopK -ne 6)    { $PyArgs += "--top-k";        $PyArgs += $TopK }

# ─── Run ──────────────────────────────────────────────────────────
Write-Host ""
Write-Info "Launching agentic_runner.py ..."
Write-Host ""

Push-Location $ScriptDir
try {
    & $PythonCmd agentic_runner.py @PyArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Die "agentic_runner.py exited with code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

Write-Host ""
Write-Ok "Done. Check the outputs/ folder for the saved report."
