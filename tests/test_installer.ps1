# FY4B Inno Setup 安装包测试（回归测试，已入库：tests/test_installer.ps1）
# 本版需求：不创建任何快捷方式，装完静默后台自动运行
# 用法：powershell -NoProfile -ExecutionPolicy Bypass -File tests\test_installer.ps1
$ErrorActionPreference = 'Continue'
# 仓库根目录 = 本文件所在目录的上一级（避免依赖当前工作目录）
$RepoRoot = Split-Path -Parent $PSScriptRoot
$script:pass = 0
$script:fail = 0

function Check([string]$name, [bool]$cond, [string]$detail = '') {
    $elapsed = if ($script:secT) { [math]::Round(((Get-Date) - $script:secT).TotalSeconds, 1) } else { 0 }
    if ($cond) { $script:pass++; Write-Output ("[PASS] +" + $elapsed + "s  " + $name) }
    else       { $script:fail++; Write-Output ("[FAIL] +" + $elapsed + "s  " + $name + "  -- " + $detail) }
}
function Section([string]$t) {
    $script:secT = Get-Date
    Write-Output ''
    Write-Output ('===== ' + $t + ' ===== ' + (Get-Date -Format 'HH:mm:ss'))
}
# 注意：Start-Process -Wait 等的是整个进程树，而安装器会启动常驻的 fy4b-wp.exe，
# 用 -Wait 会永远卡住；这里改成只等目标进程自身退出
function Invoke-AndExit([string]$file, [string[]]$argList, [int]$timeoutSec = 120) {
    $p = Start-Process -FilePath $file -ArgumentList $argList -PassThru
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    while (-not $p.HasExited -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 400 }
    if (-not $p.HasExited) {
        try { $p.Kill() } catch {}
        return -999
    }
    return $p.ExitCode
}
function Get-FyProcs { @(Get-Process -Name 'fy4b-wp' -ErrorAction SilentlyContinue) }
function Get-AutoVal {
    (Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' `
        -Name 'fy4b-wp' -ErrorAction SilentlyContinue).'fy4b-wp'
}
function Get-UninstallKey {
    Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{5E1A9C64-3F2D-4B8A-9C71-2D6E4F8A1B30}_is1' -ErrorAction SilentlyContinue
}
$SetupExe   = Join-Path $RepoRoot 'dist\fy4b-wp-setup.exe'
$InstallDir = Join-Path $env:LOCALAPPDATA 'Programs\fy4b'
$InstallExe = Join-Path $InstallDir 'fy4b-wp.exe'
$Unins      = Join-Path $InstallDir 'unins000.exe'
$DesktopLnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'FY4B 云图壁纸.lnk'
$MenuLnk    = Join-Path ([Environment]::GetFolderPath('Programs')) 'FY4B 云图壁纸.lnk'
$DataDir    = Join-Path $env:LOCALAPPDATA 'fy4b'
$TmpDir     = Join-Path $env:TEMP 'fy4b'

Section '0. preconditions'
Check 'setup.exe exists' (Test-Path $SetupExe) $SetupExe
Write-Output ("  setup size: " + [math]::Round((Get-Item $SetupExe).Length / 1MB, 2) + " MB")
if (Get-FyProcs) { taskkill /IM fy4b-wp.exe /F | Out-Null; Start-Sleep 3 }
if (Test-Path $Unins) {
    $rcOld = Invoke-AndExit $Unins @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART')
    Write-Output ("  旧安装卸载 exit = " + $rcOld)
    Start-Sleep 3
}
Check 'clean slate: no process' ((Get-FyProcs).Count -eq 0) ((Get-FyProcs).Count)
Check 'clean slate: no autostart' ([string]::IsNullOrEmpty((Get-AutoVal))) ((Get-AutoVal))
Check 'clean slate: no install dir' (-not (Test-Path $InstallDir)) $InstallDir

Section '1. silent install'
$rcSetup = Invoke-AndExit $SetupExe @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART')
Check 'setup exit 0' ($rcSetup -eq 0) ("rc=$rcSetup")
Check 'exe installed' (Test-Path $InstallExe) $InstallExe
Check 'uninstaller installed' (Test-Path $Unins) $Unins
Check 'NO Start Menu shortcut' (-not (Test-Path $MenuLnk)) $MenuLnk
Check 'NO Desktop shortcut' (-not (Test-Path $DesktopLnk)) $DesktopLnk
$auto = Get-AutoVal
Check 'autostart registered unconditionally' ($auto -eq ('"' + $InstallExe + '"')) "got: $auto"
$uk = Get-UninstallKey
Check 'registered in "Apps & features"' ($null -ne $uk) ''
if ($uk) {
    Check 'display name' ($uk.DisplayName -eq 'FY4B 云图壁纸') ("got: " + $uk.DisplayName)
    Check 'display icon' ($uk.DisplayIcon.Trim('"') -eq $InstallExe) ("got: " + $uk.DisplayIcon)
}
Start-Sleep -Seconds 5
Check 'auto-started by installer (no manual launch)' ((Get-FyProcs).Count -ge 1) ((Get-FyProcs).Count)

Section '2. background job works'
Start-Sleep -Seconds 25
Check 'process still running' ((Get-FyProcs).Count -ge 1) ((Get-FyProcs).Count)
$wp = (Get-ItemProperty 'HKCU:\Control Panel\Desktop').Wallpaper
Check 'wallpaper set' (Test-Path $wp) $wp
$leftover = if (Test-Path $TmpDir) { @(Get-ChildItem $TmpDir).Count } else { 0 }
Check 'temp download dir empty' ($leftover -eq 0) "$leftover"

Section '3. silent uninstall WHILE running'
$rcUn = Invoke-AndExit $Unins @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART')
Start-Sleep -Seconds 5
Check 'uninstaller exit 0' ($rcUn -eq 0) ("rc=$rcUn")
Check 'process killed by uninstaller' ((Get-FyProcs).Count -eq 0) ((Get-FyProcs).Count)
Check 'autostart entry removed' ([string]::IsNullOrEmpty((Get-AutoVal))) ((Get-AutoVal))
Check 'install dir removed' (-not (Test-Path $InstallDir)) $InstallDir
Check 'NO shortcut left behind (menu)' (-not (Test-Path $MenuLnk)) $MenuLnk
Check 'NO shortcut left behind (desktop)' (-not (Test-Path $DesktopLnk)) $DesktopLnk
Check 'uninstall key removed' ($null -eq (Get-UninstallKey)) ''
Check 'data dir REMOVED (no leftovers)' (-not (Test-Path $DataDir)) $DataDir
Check 'temp download dir REMOVED' (-not (Test-Path $TmpDir)) $TmpDir
$wp2 = (Get-ItemProperty 'HKCU:\Control Panel\Desktop').Wallpaper
Check 'wallpaper restored to an existing image' (Test-Path $wp2) $wp2
$st2 = Get-ItemProperty 'HKCU:\Control Panel\Desktop'
Check 'our WallpaperStyle=6 removed or wallpaper not ours' `
    ($st2.WallpaperStyle -ne '6' -or $wp2 -like '*\fy4b\timeline\*') `
    "style=$($st2.WallpaperStyle) wp=$wp2"

Section '4. reinstall and leave running (final state)'
$rcRe = Invoke-AndExit $SetupExe @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART')
Check 'reinstall exit 0' ($rcRe -eq 0) ("rc=$rcRe")
Check 'exe installed again' (Test-Path $InstallExe) $InstallExe
Check 'autostart registered again' ((Get-AutoVal) -eq ('"' + $InstallExe + '"')) ((Get-AutoVal))
Check 'still NO shortcuts' ((-not (Test-Path $MenuLnk)) -and (-not (Test-Path $DesktopLnk))) ''
Start-Sleep -Seconds 30
Check 'running after reinstall' ((Get-FyProcs).Count -ge 1) ((Get-FyProcs).Count)
$wp = (Get-ItemProperty 'HKCU:\Control Panel\Desktop').Wallpaper
Check 'wallpaper valid' (Test-Path $wp) $wp

Section 'RESULT'
Write-Output ("PASS $script:pass / FAIL $script:fail")
if ($script:fail -gt 0) { exit 1 } else { exit 0 }