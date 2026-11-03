# FY4B Windows 安装生命周期测试（回归测试，已入库：tests/test_windows_install.ps1）
# 用法：powershell -NoProfile -ExecutionPolicy Bypass -File tests\test_windows_install.ps1
$ErrorActionPreference = 'Continue'
# 仓库根目录 = 本文件所在目录的上一级（避免依赖当前工作目录）
$RepoRoot = Split-Path -Parent $PSScriptRoot
$script:fail = 0
$script:pass = 0

function Check([string]$name, [bool]$cond, [string]$detail = '') {
    if ($cond) { $script:pass++; Write-Output "[PASS] $name" }
    else       { $script:fail++; Write-Output "[FAIL] $name  -- $detail" }
}
function Section([string]$t) { Write-Output ''; Write-Output ('===== ' + $t + ' =====') }
function Get-FyProcs { @(Get-Process -Name 'fy4b-wp' -ErrorAction SilentlyContinue) }
function Get-AutoVal {
    (Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' `
        -Name 'fy4b-wp' -ErrorAction SilentlyContinue).'fy4b-wp'
}
function Invoke-RemoveAutostart([string]$exe) {
    $p = Start-Process -FilePath $exe -ArgumentList '--remove-autostart' `
        -PassThru -Wait -NoNewWindow
    return $p.ExitCode
}

$DistExe    = Join-Path $RepoRoot 'dist\fy4b-wp.exe'
$InstallDir = Join-Path $env:LOCALAPPDATA 'Programs\fy4b'
$InstallExe = Join-Path $InstallDir 'fy4b-wp.exe'
$DataDir    = Join-Path $env:LOCALAPPDATA 'fy4b'
$DataBak    = Join-Path $env:LOCALAPPDATA 'fy4b_test_backup'
$TmpDir     = Join-Path $env:TEMP 'fy4b'
$RunKey     = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'

Section '0. baseline'
Write-Output ("  running processes : " + (Get-FyProcs).Count)
Write-Output ("  autostart value    : " + (Get-AutoVal))
Write-Output ("  data dir exists    : " + (Test-Path $DataDir))

Section '1. uninstall WHILE running (maintenance args skip the lock)'
# 先确保有实例在跑，否则本节测不到“运行中”的场景
if ((Get-FyProcs).Count -eq 0) {
    Start-Process -FilePath $DistExe -WindowStyle Hidden | Out-Null
    Start-Sleep -Seconds 20
    Write-Output ("  (started instance, now " + (Get-FyProcs).Count + " process(es))")
}
$before = Get-AutoVal
$nBefore = (Get-FyProcs).Count
$rc = Invoke-RemoveAutostart $DistExe
$after = Get-AutoVal
$nAfter = (Get-FyProcs).Count
Write-Output ("  exit code = $rc ; autostart '$before' -> '$after'")
Check 'running instance: --remove-autostart exit 0' ($rc -eq 0) "rc=$rc"
Check 'running instance: autostart entry removed' `
    ([string]::IsNullOrEmpty($after)) "got: $after"
Check 'running instance: daemon NOT killed by maintenance cmd' `
    ($nAfter -ge $nBefore) "before=$nBefore after=$nAfter"

Section '2. stop all, then remove autostart (correct order)'
taskkill /IM fy4b-wp.exe /F | Out-Null
Start-Sleep -Seconds 3
Check 'all fy4b-wp processes stopped' ((Get-FyProcs).Count -eq 0) ((Get-FyProcs).Count)
$rc = Invoke-RemoveAutostart $DistExe
Check '--remove-autostart exit 0' ($rc -eq 0) "rc=$rc"
Check 'autostart entry removed' ([string]::IsNullOrEmpty((Get-AutoVal))) ((Get-AutoVal))

Section '3. simulate fresh machine (move data dir aside)'
if (Test-Path $DataBak) { Remove-Item $DataBak -Recurse -Force }
if (Test-Path $DataDir) { Move-Item $DataDir $DataBak }
Check 'data dir removed for fresh-install test' (-not (Test-Path $DataDir))

Section '4. install: copy exe to stable per-user location'
if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item $DistExe $InstallExe
Check 'exe copied to install dir' (Test-Path $InstallExe) $InstallExe
Write-Output ("  install path: $InstallExe")

Section '5. first run'
$beforeWall = (Get-ItemProperty 'HKCU:\Control Panel\Desktop').Wallpaper
$p = Start-Process -FilePath $InstallExe -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 25
$procs = Get-FyProcs
Check 'process is running' ($procs.Count -ge 1) $procs.Count
$auto = Get-AutoVal
Check 'autostart registered' (-not [string]::IsNullOrEmpty($auto)) ''
Check 'autostart points to INSTALL path' ($auto -eq ('"' + $InstallExe + '"')) "got: $auto"
Check 'data dir recreated' (Test-Path (Join-Path $DataDir 'timeline'))
Check 'log file created' (Test-Path (Join-Path $DataDir 'cache\fy4b.log'))
$wp = (Get-ItemProperty 'HKCU:\Control Panel\Desktop').Wallpaper
Check 'wallpaper points into timeline' ($wp -like '*fy4b\timeline\*.jpg') "got: $wp"
Check 'wallpaper file exists' (Test-Path $wp) $wp
$leftover = if (Test-Path $TmpDir) { @(Get-ChildItem $TmpDir).Count } else { 0 }
Check 'temp download dir empty' ($leftover -eq 0) $leftover

Section '6. single-instance lock'
$n0 = (Get-FyProcs).Count
$p2 = Start-Process -FilePath $InstallExe -PassThru -Wait
Start-Sleep -Seconds 2
$n1 = (Get-FyProcs).Count
Check 'second instance exits with code 1' ($p2.ExitCode -eq 1) ("rc=" + $p2.ExitCode)
Check 'no extra process left behind' ($n1 -eq $n0) "before=$n0 after=$n1"

Section '7. uninstall (correct order)'
taskkill /IM fy4b-wp.exe /F | Out-Null
Start-Sleep -Seconds 3
Check 'processes stopped' ((Get-FyProcs).Count -eq 0) ((Get-FyProcs).Count)
$rc = Invoke-RemoveAutostart $InstallExe
Check 'remove-autostart exit 0' ($rc -eq 0) "rc=$rc"
Check 'autostart entry gone' ([string]::IsNullOrEmpty((Get-AutoVal))) ((Get-AutoVal))
Remove-Item $InstallDir -Recurse -Force
Check 'install dir removed' (-not (Test-Path $InstallDir))
Check 'data dir LEFT BEHIND (needs manual cleanup)' (Test-Path $DataDir) ''

Section '8. reinstall and leave running (restore data)'
if (Test-Path $DataBak) {
    if (Test-Path $DataDir) { Remove-Item $DataDir -Recurse -Force }
    Move-Item $DataBak $DataDir
    Write-Output '  data dir restored from backup'
}
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item $DistExe $InstallExe
$p = Start-Process -FilePath $InstallExe -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 20
Check 'reinstall: process running' ((Get-FyProcs).Count -ge 1) ((Get-FyProcs).Count)
$auto = Get-AutoVal
Check 'reinstall: autostart registered' ($auto -eq ('"' + $InstallExe + '"')) "got: $auto"
$wp = (Get-ItemProperty 'HKCU:\Control Panel\Desktop').Wallpaper
Check 'reinstall: wallpaper valid' (Test-Path $wp) $wp

Section 'RESULT'
Write-Output ("PASS $script:pass / FAIL $script:fail")
if ($script:fail -gt 0) { exit 1 } else { exit 0 }