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

[Files]
Source: "dist\fy4b-wp.exe"; DestDir: "{app}"; Flags: ignoreversion

; 刻意不写 [Icons] / [Tasks]：不创建桌面与开始菜单快捷方式，
; 也不给用户勾选项，装完直接在后台静默运行

[Registry]
; 开机自启（与程序自身写入的 HKCU Run 值名保持一致：fy4b-wp）
; 无任务选项，始终注册；卸载时自动删除该值
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "fy4b-wp"; ValueData: """{app}\{#MyAppExeName}"""; \
    Flags: uninsdeletevalue

[Run]
; 安装一结束就在后台启动（无勾选框，静默安装同样生效）
Filename: "{app}\{#MyAppExeName}"; Flags: nowait runhidden

[UninstallRun]
; 卸载前先结束进程，否则 exe 被占用无法删除
Filename: "{sys}\taskkill.exe"; Parameters: "/IM fy4b-wp.exe /F"; \
    RunOnceId: "KillFy4b"; Flags: runhidden waituntilterminated
; 再移除开机自启（程序运行中也能执行），避免残留指向已删 exe 的僵尸项
Filename: "{app}\{#MyAppExeName}"; Parameters: "--remove-autostart"; \
    RunOnceId: "RemoveAutostart"; Flags: runhidden waituntilterminated

[UninstallDelete]
; 彻底清理，不留残余：安装目录 + 数据目录（壁纸时间轴 + 日志）
; 顺序说明：[UninstallRun] 会先执行（结束进程、移除自启），
; 之后才删除这些文件，所以不会遇到文件被占用
; （临时下载目录 %TEMP%\fy4b 在下面的 [Code] 里按实际 TEMP 环境变量删）
Type: filesandordirs; Name: "{app}"
Type: filesandordirs; Name: "{localappdata}\fy4b"

[Code]
// 卸载收尾：清理临时下载目录，并把壁纸换回系统默认、还原我们写过的样式值，
// 避免卸载后桌面壁纸指向已被删除的图片（重启会变黑屏）
function SystemParametersInfoW(uiAction: Integer; uiParam: Integer;
  pvParam: String; fWinIni: Integer): Integer;
  external 'SystemParametersInfoW@user32.dll stdcall';

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  CurrentWallpaper, Fallback, TempDir: String;
begin
  if CurUninstallStep <> usPostUninstall then
    Exit;

  // 清掉临时下载目录（用真实 TEMP，兼容用户重定向 TEMP 的情况）
  TempDir := GetEnv('TEMP');
  if TempDir <> '' then
    DelTree(TempDir + '\fy4b', True, True, True);

  CurrentWallpaper := '';
  RegQueryStringValue(HKCU, 'Control Panel\Desktop', 'Wallpaper', CurrentWallpaper);

  // 只在当前壁纸确实已经不存在（= 我们刚删掉的那张）时才动桌面设置；
  // 用户中途换过壁纸就不要打扰他
  if (CurrentWallpaper <> '') and (not FileExists(CurrentWallpaper)) then
  begin
    Fallback := ExpandConstant('{win}\Web\Wallpaper\Windows\img0.jpg');
    if not FileExists(Fallback) then
      Fallback := ExpandConstant('{win}\Web\Wallpaper\img0.jpg');
    if not FileExists(Fallback) then
      Fallback := ExpandConstant('{win}\Web\Screen\img102.jpg');
    if FileExists(Fallback) then
    begin
      RegWriteStringValue(HKCU, 'Control Panel\Desktop', 'Wallpaper', Fallback);
      // SPI_SETDESKWALLPAPER = 0x0014，SPIF_UPDATEINIFILE|SPIF_SENDCHANGE = 3
      SystemParametersInfoW($0014, 0, Fallback, 3);
      // 还原成系统默认样式（去掉我们写入的 Fit=6）
      RegDeleteValue(HKCU, 'Control Panel\Desktop', 'WallpaperStyle');
      RegDeleteValue(HKCU, 'Control Panel\Desktop', 'TileWallpaper');
    end;
  end;
end;