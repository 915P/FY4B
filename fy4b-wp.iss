; ============================================================
; FY4B Wallpaper Windows 安装脚本（Inno Setup 6）
;
; 编译顺序（务必先出 exe，build.bat 会清空 dist/）：
;   1. build.bat                 -> dist\fy4b-wp.exe
;   2. ISCC.exe fy4b-wp.iss      -> dist\fy4b-wp-setup.exe
;
; 静默安装：fy4b-wp-setup.exe /VERYSILENT /NORESTART
; 静默卸载：{app}\unins000.exe /VERYSILENT /NORESTART
; ============================================================

#define MyAppName "FY4B 云图壁纸"
#define MyAppVersion "2026.11.02"
#define MyAppPublisher "915P"
#define MyAppURL "https://github.com/915P/FY4B"
#define MyAppExeName "fy4b-wp.exe"

[Setup]
; 同一 AppId 才能覆盖安装/正确卸载旧版
AppId={{5E1A9C64-3F2D-4B8A-9C71-2D6E4F8A1B30}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
VersionInfoVersion={#MyAppVersion}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoDescription=FY-4B 卫星云图壁纸程序
VersionInfoProductName={#MyAppName}
VersionInfoCompany={#MyAppPublisher}

; 按用户安装，不需要管理员权限（对应 {localappdata}，与程序自身数据目录同级）
DefaultDirName={localappdata}\Programs\fy4b
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=fy4b-wp-setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\fy4b-wp.exe
UninstallDisplayName={#MyAppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
LZMANumBlockThreads=4

; 32/64 位系统通用（按用户安装，无架构差异）
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "开机自动启动（登录后每 15 分钟自动更新壁纸）"; GroupDescription: "启动方式:"

[Files]
Source: "dist\fy4b-wp.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; \
    WorkingDir: "{app}"; Comment: "下载 FY-4B 卫星云图并设置为桌面壁纸"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; \
    WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
; 开机自启（与程序自身写入的 HKCU Run 值名保持一致：fy4b-wp）
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "fy4b-wp"; ValueData: """{app}\{#MyAppExeName}"""; \
    Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; \
    Description: "{cm:LaunchProgram,{#MyAppName}}"; \
    Flags: nowait postinstall skipifsilent

[UninstallRun]
; 卸载前先结束进程，否则 exe 被占用无法删除
Filename: "{sys}\taskkill.exe"; Parameters: "/IM fy4b-wp.exe /F"; \
    RunOnceId: "KillFy4b"; Flags: runhidden waituntilterminated
; 再移除开机自启（程序运行中也能执行），避免残留指向已删 exe 的僵尸项
Filename: "{app}\{#MyAppExeName}"; Parameters: "--remove-autostart"; \
    RunOnceId: "RemoveAutostart"; Flags: runhidden waituntilterminated

[UninstallDelete]
; 只清理安装目录里可能残留的文件；用户数据（%LOCALAPPDATA%\fy4b 壁纸时间轴与日志）保留
Type: filesandordirs; Name: "{app}"