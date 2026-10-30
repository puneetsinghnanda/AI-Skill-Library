@echo off
rem tsl-hook.cmd <event>: Windows launcher for the truminds plugin hooks (SDD-05 s.5.2, s.5.4).
rem Same contract as bin/tsl-hook (POSIX sh): find tsl, check its version equals the plugin version,
rem pipe stdin to `tsl hook <event>`, and apply the SDD-05 s.5.4 failure rules (fail closed in a run for
rem pre-tool and pre-mcp, fail open otherwise). The logic after the PowerShell marker line runs in Windows
rem PowerShell 5.1+, which every supported Windows build ships; cmd.exe has no usable timeout or JSON parser.
rem Claude Code normally runs hook commands through Git Bash on Windows, which uses bin/tsl-hook; this file
rem is the fallback when the command is resolved by cmd.exe.
setlocal EnableExtensions DisableDelayedExpansion
set "TSL_HOOK_EVENT=%~1"
set "TSL_HOOK_SELF=%~f0"
if not defined CLAUDE_PLUGIN_ROOT set "CLAUDE_PLUGIN_ROOT=%~dp0.."
powershell.exe -NoLogo -NoProfile -NonInteractive -Command "$t=[IO.File]::ReadAllText($env:TSL_HOOK_SELF); $i=$t.IndexOf('#PS'+'-BEGIN'); Invoke-Expression $t.Substring($i)"
exit /b %ERRORLEVEL%

#PS-BEGIN
$ErrorActionPreference = 'Stop'
$HookEvent = $env:TSL_HOOK_EVENT
$Valid = @('session-start', 'pre-tool', 'pre-mcp', 'post-write', 'session-end')
if ($Valid -notcontains $HookEvent) { [Console]::Error.WriteLine("tsl-hook: unknown event '$HookEvent'"); exit 1 }

$PluginRoot = $env:CLAUDE_PLUGIN_ROOT
$TrumindsDir = Join-Path $env:USERPROFILE '.truminds'
$HookLog = Join-Path $TrumindsDir 'logs\hook.log'
$Budget = @{ 'session-start' = 12; 'session-end' = 12; 'pre-tool' = 8; 'pre-mcp' = 8; 'post-write' = 85 }[$HookEvent]
$Override = 0
if ([int]::TryParse("$env:TSL_HOOK_BUDGET_S", [ref]$Override) -and $Override -ge 1 -and $Override -lt $Budget) { $Budget = $Override }

$Utf8 = New-Object System.Text.UTF8Encoding($false)
$InText = [Console]::In.ReadToEnd()
$Tmp = Join-Path ([IO.Path]::GetTempPath()) ('tsl-hook-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $Tmp | Out-Null
$InFile = Join-Path $Tmp 'in'; $OutFile = Join-Path $Tmp 'out'; $ErrFile = Join-Path $Tmp 'err'
[IO.File]::WriteAllText($InFile, $InText, $Utf8)
$Hook = $null
try { $Hook = $InText | ConvertFrom-Json } catch { $Hook = $null }

function Write-HookLog([string]$Decision, [string]$Code, [string]$Detail) {
  try {
    New-Item -ItemType Directory -Force -Path (Split-Path $HookLog) | Out-Null
    $ts = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
    Add-Content -Path $HookLog -Value "$ts tsl-hook event=$HookEvent decision=$Decision code=$Code detail=$Detail" -Encoding UTF8
  } catch { }
}

function Get-PluginVersion {
  try { return (Get-Content -Raw (Join-Path $PluginRoot '.claude-plugin\plugin.json') | ConvertFrom-Json).version } catch { return 'unknown' }
}

function Find-Tsl {
  $c = Get-Command tsl -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($c) { return $c.Source }
  foreach ($p in @((Join-Path $env:USERPROFILE '.local\bin\tsl.exe'), (Join-Path $env:USERPROFILE '.local\bin\tsl.cmd'))) {
    if (Test-Path $p) { return $p }
  }
  return $null
}

# Runs exe with $InFile on stdin; returns @{ Code; TimedOut }.
function Invoke-Bounded([string]$Exe, [string[]]$Arguments, [int]$Seconds) {
  $p = Start-Process -FilePath $Exe -ArgumentList $Arguments -NoNewWindow -PassThru `
       -RedirectStandardInput $InFile -RedirectStandardOutput $OutFile -RedirectStandardError $ErrFile
  if (-not $p.WaitForExit($Seconds * 1000)) {
    try { $p.Kill() } catch { }
    return @{ Code = 124; TimedOut = $true }
  }
  return @{ Code = $p.ExitCode; TimedOut = $false }
}

function Test-LockIn([string]$Root) {
  $d = Join-Path $Root 'runs\active'
  return (Test-Path $d) -and @(Get-ChildItem -Path $d -Filter '*.lock' -File -ErrorAction SilentlyContinue).Count -gt 0
}

function Test-RunActive {
  $sid = if ($Hook) { [string]$Hook.session_id } else { '' }
  if ($sid -match '^[A-Za-z0-9_.-]+$') {
    $idx = Join-Path $TrumindsDir "sessions\$sid.json"
    if (Test-Path $idx) {
      try {
        $s = Get-Content -Raw $idx | ConvertFrom-Json
        if ($s.companion -and $s.lock -and (Test-Path (Join-Path $s.companion $s.lock))) { return $true }
      } catch { }
    }
  }
  $dir = if ($Hook -and $Hook.cwd -and (Test-Path $Hook.cwd)) { [string]$Hook.cwd } else { (Get-Location).Path }
  while ($dir) {
    if (Test-Path (Join-Path $dir 'tsl.yaml')) { return (Test-LockIn $dir) }
    $parent = Split-Path $dir -Parent
    if (-not $parent -or $parent -eq $dir) { break }
    $dir = $parent
  }
  return $false
}

# No published package: tsl and the plugin both come from the library clone.
function Get-InstallHint([string]$V) { 'update tsl and the plugin from your AI-Skill-Library clone: git pull; uv tool install --python 3.12 --reinstall --no-cache ./tsl (TSL_ORG_FILE set, see the pilot guide); claude plugin marketplace update truminds-skill-library; claude plugin update truminds@truminds-skill-library' }

function Out-Json($Obj) { [Console]::Out.WriteLine(($Obj | ConvertTo-Json -Compress -Depth 5)) }

function Exit-Fail([string]$Kind, [string]$Detail) {
  switch ($HookEvent) {
    { $_ -in 'pre-tool', 'pre-mcp' } {
      if (Test-RunActive) {
        Write-HookLog 'deny' 'E-HOOK-01' "${Kind}: $Detail"
        Out-Json @{ hookSpecificOutput = @{ hookEventName = 'PreToolUse'; permissionDecision = 'deny';
          permissionDecisionReason = "E-HOOK-01 Truminds run is active and the policy hook cannot run ($Detail). Writes stay blocked until this is fixed." } }
      } else {
        Write-HookLog 'allow' 'E-HOOK-01' "$Kind (no active run): $Detail"
      }
    }
    'post-write' {
      Write-HookLog 'allow' 'E-HOOK-01' "$Kind (fail open): $Detail"
      Out-Json @{ systemMessage = "Truminds: artifact checks did not run ($Detail). Your file was kept. Fix tsl, then re-run the step's checks." }
    }
    default {
      if ($Kind -in 'missing', 'version') {
        Write-HookLog 'warn' 'E-VER-01' "${Kind}: $Detail"
        Out-Json @{ systemMessage = "Truminds: $Detail" }
      } else {
        Write-HookLog 'ignore' 'E-HOOK-01' "${Kind}: $Detail"
      }
    }
  }
  Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue
  exit 0
}

$PV = Get-PluginVersion
$Tsl = Find-Tsl
if (-not $Tsl) { Exit-Fail 'missing' "tsl is not installed. Install tsl ${PV}: $(Get-InstallHint $PV)" }

$r = Invoke-Bounded $Tsl @('--version') 5
if ($r.TimedOut) { Exit-Fail 'timeout' 'tsl --version did not answer within 5 s' }
if ($r.Code -ne 0) { Exit-Fail 'crash' "tsl --version exited with status $($r.Code)" }
$TV = ''
$m = [regex]::Match([IO.File]::ReadAllText($OutFile), '^tsl\s+([0-9A-Za-z.+-]+)', 'Multiline')
if ($m.Success) { $TV = $m.Groups[1].Value }
if (-not $TV) { Exit-Fail 'version' "tsl did not report a version. Install tsl ${PV}: $(Get-InstallHint $PV)" }
if ($TV -ne $PV) { Exit-Fail 'version' "tsl $TV does not match plugin $PV (E-VER-01). Install tsl ${PV}: $(Get-InstallHint $PV)" }

$r = Invoke-Bounded $Tsl @('hook', $HookEvent) $Budget
if ($r.TimedOut) { Exit-Fail 'timeout' "tsl hook $HookEvent timed out after $Budget s" }
if ($r.Code -ne 0) { Exit-Fail 'crash' "tsl hook $HookEvent exited with status $($r.Code)" }
[Console]::Error.Write([IO.File]::ReadAllText($ErrFile))
[Console]::Out.Write([IO.File]::ReadAllText($OutFile))
Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue
exit 0
