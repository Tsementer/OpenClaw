param(
  [Parameter(Mandatory=$true)][string]$Host,
  [Parameter(Mandatory=$true)][string]$User,
  [string]$RemoteBase = '/docker/openclaw-q6e8/data/.openclaw',
  [string]$NexosApiKey = $env:NEXOS_API_KEY,
  [string]$OpenClawToken = $env:OPENCLAW_TOKEN,
  [int]$Port = 22
)

$ErrorActionPreference = 'Stop'

$files = @(
  'cron/jobs.json',
  'README.md',
  'state/ledger.jsonl',
  'state/README.md',
  'workspace/AGENTS.md',
  'workspace-kirjutaja/AGENTS.md',
  'workspace-postiluure/SOUL.md',
  'workspace-postiluure/AGENTS.md',
  'workspace-postiluure/TOOLS.md',
  'workspace-taiendaja/SOUL.md',
  'workspace-taiendaja/AGENTS.md',
  'workspace-taiendaja/TOOLS.md',
  'workspace-toimetaja/SOUL.md',
  'workspace-toimetaja/AGENTS.md',
  'workspace-toimetaja/TOOLS.md',
  'workspace-veebivalvur/SOUL.md',
  'workspace-veebivalvur/AGENTS.md',
  'workspace-veebivalvur/TOOLS.md',
  'workspace-veebivalvur/sources.json'
)

$dirs = @(
  "$RemoteBase/cron",
  "$RemoteBase/state",
  "$RemoteBase/workspace",
  "$RemoteBase/workspace-kirjutaja",
  "$RemoteBase/workspace-postiluure",
  "$RemoteBase/workspace-taiendaja",
  "$RemoteBase/workspace-toimetaja",
  "$RemoteBase/workspace-veebivalvur"
)

foreach ($d in $dirs) {
  ssh -p $Port "$User@$Host" "mkdir -p $d"
}

if ([string]::IsNullOrWhiteSpace($NexosApiKey)) {
  throw 'Missing Nexos API key. Set -NexosApiKey or NEXOS_API_KEY before deploy.'
}

if ([string]::IsNullOrWhiteSpace($OpenClawToken)) {
  throw 'Missing OpenClaw token. Set -OpenClawToken or OPENCLAW_TOKEN before deploy.'
}

$renderedConfigPath = [System.IO.Path]::GetTempFileName()
try {
  $config = Get-Content 'openclaw.json' -Raw | ConvertFrom-Json
  $config.models.providers.nexos.apiKey = $NexosApiKey
  $config.notify.telegram.token = $OpenClawToken
  $config.gateway.auth.token = $OpenClawToken
  $config.gateway.api.token = $OpenClawToken

  $config | ConvertTo-Json -Depth 100 | Set-Content -Path $renderedConfigPath -NoNewline
  scp -P $Port $renderedConfigPath "$User@$Host`:$RemoteBase/openclaw.json"
}
finally {
  if (Test-Path $renderedConfigPath) {
    Remove-Item $renderedConfigPath -Force
  }
}

foreach ($f in $files) {
  if (-not (Test-Path $f)) { throw "Missing file: $f" }
  scp -P $Port $f "$User@$Host`:$RemoteBase/$f"
}

ssh -p $Port "$User@$Host" "docker restart openclaw-q6e8-openclaw-1"
Write-Host 'Deploy complete.'
