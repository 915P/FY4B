@echo off
chcp 65001 >nul
setlocal

rem ---------- 配置 ----------
set APP_NAME=fy4b-wp

rem ---------- 清理旧构建 ----------
rem 必须清场，否则会复用旧的 spec/Analysis 缓存，打出缺依赖的包
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "%APP_NAME%.spec" del /q "%APP_NAME%.spec"

echo ==^> 编译单文件 exe ...
pyinstaller --onefile --noconsole --name %APP_NAME% FY4B.py
if not exist "dist\%APP_NAME%.exe" (
    echo 错误：编译失败，未找到 dist\%APP_NAME%.exe
    exit /b 1
)

echo ==^> 完成！生成的 exe：
dir "dist\%APP_NAME%.exe"

rem ---------- 可选：用 Inno Setup 打带图形向导的安装包 ----------
rem 变量名里带括号，必须在顶层展开，不能放进 if (...) 块里
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC="

if defined ISCC (
    echo ==^> 编译安装程序 setup.exe ...
    "%ISCC%" fy4b-wp.iss
    if not exist "dist\%APP_NAME%-setup.exe" (
        echo 错误：安装包编译失败，未找到 dist\%APP_NAME%-setup.exe
        exit /b 1
    )
    echo ==^> 生成的安装包：
    dir "dist\%APP_NAME%-setup.exe"
) else (
    echo 未检测到 Inno Setup，跳过安装包（仅产出单文件 exe）
)

endlocal