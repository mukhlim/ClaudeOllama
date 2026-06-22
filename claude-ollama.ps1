#Requires -Version 5.1
<#
.SYNOPSIS
    Jalankan Claude Code dengan backend Ollama Cloud via PowerShell.
    Handle kasus logout / onboarding ulang.

.DESCRIPTION
    Script ini akan:
    1. Force skip onboarding Anthropic (tulis ~/.claude.json)
    2. Set environment variables ANTHROPIC_BASE_URL dan ANTHROPIC_AUTH_TOKEN
    3. Jalankan Claude Code

.CARA PAKAI
    1. Pastikan config.json sudah berisi OLLAMA_API_KEY yang valid.
    2. Buka PowerShell di folder ini.
    3. Jalankan: .\claude-ollama.ps1
       (atau klik kanan → Run with PowerShell)
#>

$ErrorActionPreference = "Stop"

# ── 1. Load API Key dari config.json ─────────────────────────────────────────
$configPath = Join-Path $PSScriptRoot "config.json"

if (-not (Test-Path $configPath)) {
    Write-Host "[ERROR] File config.json tidak ditemukan di: $configPath" -ForegroundColor Red
    Write-Host "   Buat file config.json dengan isi:"
    Write-Host '   { "OLLAMA_API_KEY": "sk-xxxx" }'
    exit 1
}

try {
    $config = Get-Content $configPath -Raw | ConvertFrom-Json
} catch {
    Write-Host "[ERROR] Gagal membaca config.json: $_" -ForegroundColor Red
    exit 1
}

$apiKey = $config.OLLAMA_API_KEY
if (-not $apiKey -or $apiKey -match "xxxxxxxx") {
    Write-Host "[ERROR] OLLAMA_API_KEY belum diisi di config.json!" -ForegroundColor Red
    Write-Host "   Edit file config.json dan ganti placeholder dengan API Key asli."
    exit 1
}

# ── 2. Force skip onboarding (handle kasus logout) ──────────────────────────
$claudeConfigPath = Join-Path $HOME ".claude.json"
$claudeConfig = @{}

if (Test-Path $claudeConfigPath) {
    try {
        $claudeConfig = Get-Content $claudeConfigPath -Raw | ConvertFrom-Json -AsHashtable
        if ($null -eq $claudeConfig) { $claudeConfig = @{} }
    } catch {
        $claudeConfig = @{}  # kalau corrupt, overwrite aja
    }
}

# Force set flag onboarding
$claudeConfig["hasCompletedOnboarding"] = $true

# Tulis balik
$claudeConfig | ConvertTo-Json -Depth 10 | Set-Content $claudeConfigPath -Encoding UTF8
Write-Host "[OK] Onboarding flag ditulis ke $claudeConfigPath" -ForegroundColor Green

# ── 3. Set Environment Variables (session only) ─────────────────────────────
$env:ANTHROPIC_BASE_URL    = "https://ollama.com"
$env:ANTHROPIC_AUTH_TOKEN  = $apiKey
$env:ANTHROPIC_API_KEY     = ""

# Map slot model Anthropic -> model Ollama Cloud
# Claude Code UI tetap menampilkan nama Anthropic, tapi backend pakai Ollama Cloud
$env:ANTHROPIC_MODEL                = "glm-5.2:cloud"
$env:ANTHROPIC_DEFAULT_OPUS_MODEL   = "glm-5.2:cloud"
$env:ANTHROPIC_DEFAULT_SONNET_MODEL = "minimax-m3:cloud"
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL  = "kimi-k2.7-code:cloud"
$env:CLAUDE_CODE_SUBAGENT_MODEL     = "minimax-m3:cloud"

# Override context & output tokens agar Claude Code tau capability model
$env:CLAUDE_CODE_MAX_CONTEXT_TOKENS = "262144"
$env:CLAUDE_CODE_MAX_OUTPUT_TOKENS  = "131072"

# Hapus ENABLE_TOOL_SEARCH kalau pernah di-set global (biar bersih)
if ($env:ENABLE_TOOL_SEARCH) {
    Remove-Item Env:\ENABLE_TOOL_SEARCH -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host ">>> Menjalankan Claude Code dengan backend Ollama Cloud..." -ForegroundColor Cyan
Write-Host "   Base URL : $($env:ANTHROPIC_BASE_URL)" -ForegroundColor DarkGray
Write-Host "   API Key  : $($apiKey.Substring(0,6))...$($apiKey.Substring($apiKey.Length-4))" -ForegroundColor DarkGray
Write-Host ""
Write-Host "[Model Mapping]" -ForegroundColor DarkGray
Write-Host "   Model               : $($env:ANTHROPIC_MODEL)"
Write-Host "   Opus                : $($env:ANTHROPIC_DEFAULT_OPUS_MODEL) (-> glm-5.2:cloud)"
Write-Host "   Sonnet              : $($env:ANTHROPIC_DEFAULT_SONNET_MODEL) (-> minimax-m3:cloud)"
Write-Host "   Haiku               : $($env:ANTHROPIC_DEFAULT_HAIKU_MODEL) (-> kimi-k2.7-code:cloud)"
Write-Host "   Subagent            : $($env:CLAUDE_CODE_SUBAGENT_MODEL)"
Write-Host ""
Write-Host "[Context / Output]" -ForegroundColor DarkGray
Write-Host "   Max Context Tokens  : $($env:CLAUDE_CODE_MAX_CONTEXT_TOKENS)"
Write-Host "   Max Output Tokens   : $($env:CLAUDE_CODE_MAX_OUTPUT_TOKENS)"
Write-Host ""
Write-Host "[Tips]" -ForegroundColor Yellow
Write-Host "   - Ketik /status setelah Claude nyala untuk cek model aktif."
Write-Host "   - Tekan Alt+T untuk toggle Thinking mode."
Write-Host "   - Kalau masih diminta login, tekan Ctrl+C dan jalankan script ini lagi."
Write-Host ("-" * 60) -ForegroundColor DarkGray

# ── 4. Jalankan Claude Code ─────────────────────────────────────────────────
try {
    # Cek apakah claude tersedia
    $claudeCmd = Get-Command "claude" -ErrorAction SilentlyContinue
    if (-not $claudeCmd) {
        Write-Host ""
        Write-Host "[ERROR] 'claude' tidak ditemukan di PATH." -ForegroundColor Red
        Write-Host "   Pastikan Claude Code sudah terinstall:" -ForegroundColor Red
        Write-Host "   npm install -g @anthropic-ai/claude-code" -ForegroundColor Yellow
        exit 1
    }

    # Jalankan claude dengan env vars yang sudah di-set
    & claude
} catch {
    Write-Host ""
    Write-Host "[ERROR] Error menjalankan claude: $_" -ForegroundColor Red
    exit 1
}
