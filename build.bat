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

endlocal