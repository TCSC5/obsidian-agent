param(
  [switch]$Apply,
  [switch]$ArchiveDebugBats
)

$root   = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$stamp  = Get-Date -Format "yyyyMMdd_HHmmss"

function Log($s){ $script:log.Add($s) | Out-Null }
function EnsureDir($p){ if(-not (Test-Path $p)){ New-Item -ItemType Directory -Path $p | Out-Null } }

# backup outside repo
$parentDir  = Split-Path $root -Parent
$backupsDir = Join-Path $parentDir "_obsidian-agent_backups"
EnsureDir $backupsDir
$backupZip  = Join-Path $backupsDir ("obsidian-agent_" + $stamp + ".zip")

try {
  Add-Type -AssemblyName "System.IO.Compression.FileSystem"
  [System.IO.Compression.ZipFile]::CreateFromDirectory($root, $backupZip)
} catch {
  Write-Warning ("Backup failed: " + $_.Exception.Message)
}

# prepare archive dirs
$archiveRoot     = Join-Path $root "_archive"
$archLaunchDebug = Join-Path $archiveRoot "launchers_debug"
EnsureDir $archiveRoot
EnsureDir $archLaunchDebug

# scan
$log = New-Object System.Collections.Generic.List[string]
Log "# Cleanup Report  ($stamp)`n"

$pycache = Get-ChildItem -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
$pyc     = Get-ChildItem -Recurse -File -Include *.pyc,*.pyo -ErrorAction SilentlyContinue

$bat = Get-ChildItem -File -Recurse -Include *.bat | Where-Object { $_.FullName -notmatch "\\venv\\" }
$debugBats = $bat | Where-Object {
    $n = $_.BaseName.ToLower()
    ($n -like "*verbose*") -or
    ($n -like "*debug*")   -or
    ($n -like "*diag*")    -or
    ($n -like "*check*")
}

Log "## Debug/Diagnostic .bat files"
if($debugBats.Count -eq 0){ Log "_None_`n" } else {
  foreach($b in $debugBats){ Log ("- " + $b.FullName) }
}

# actions
$changes = New-Object System.Collections.Generic.List[string]
if($Apply){
  foreach($d in $pycache){ Remove-Item $d.FullName -Recurse -Force; $changes.Add("removed dir: " + $d.FullName) | Out-Null }
  foreach($f in $pyc){ Remove-Item $f.FullName -Force; $changes.Add("removed file: " + $f.FullName) | Out-Null }
  if($ArchiveDebugBats){
    foreach($b in $debugBats){
      $dest = Join-Path $archLaunchDebug $b.Name
      Move-Item -LiteralPath $b.FullName -Destination $dest -Force
      $changes.Add("archived debug launcher: " + $b.FullName) | Out-Null
    }
  }
}

# write report
$reportPath = Join-Path $root "CleanupReport.md"
$log.Add("## Changes") | Out-Null
if ($changes.Count -eq 0) {
    $log.Add("_None (dry-run or no actions requested)_") | Out-Null
} else {
    $changes | ForEach-Object { $log.Add("- " + $_) }
}
$log -join "`r`n" | Set-Content -Encoding UTF8 $reportPath

Write-Host ""
Write-Host ("Report: " + $reportPath)
Write-Host ("Backup: " + $backupZip)
if ($Apply) {
    if ($ArchiveDebugBats) {
        Write-Host "Applied: cache purge + archived debug launchers"
    } else {
        Write-Host "Applied: cache purge only"
    }
} else {
    Write-Host "DRY RUN: re-run with -Apply (optional: -ArchiveDebugBats)"
}
