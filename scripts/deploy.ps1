param(
  [Parameter(Mandatory=$true)][string]$Host,
  [Parameter(Mandatory=$true)][string]$User,
  [string]$RemoteBase = '/docker/openclaw-q6e8/data/.openclaw',
  [int]$Port = 22
)

$ErrorActionPreference = 'Stop'

$files = @(
  'openclaw.json',
  'cron/jobs.json',
  'README.md',
  'state/ledger.jsonl',
  'state/README.md',
  'workspace/AGENTS.md',
  'workspace-kirjutaja/AGENTS.md',
  'workspace-postiluure/SOUL.md',
  'workspace-postiluure/AGENTS.md',
  'workspace-postiluure/TOOLS.md',
  'workspace-täiendaja/SOUL.md',
  'workspace-täiendaja/AGENTS.md',
  'workspace-täiendaja/TOOLS.md',
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
  "$RemoteBase/workspace-täiendaja",
  "$RemoteBase/workspace-toimetaja",
  "$RemoteBase/workspace-veebivalvur"
)

foreach ($d in $dirs) {
  ssh -p $Port "$User@$Host" "mkdir -p $d"
}

foreach ($f in $files) {
  if (-not (Test-Path $f)) { throw "Missing file: $f" }
  scp -P $Port $f "$User@$Host`:$RemoteBase/$f"
}

ssh -p $Port "$User@$Host" "docker restart openclaw-q6e8-openclaw-1"
Write-Host 'Deploy complete.'
