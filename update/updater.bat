@echo off
REM NovaForge 自更新脚本
REM 用法: updater.bat <新exe完整路径> <当前exe完整路径>
setlocal
set NEW=%~1
set TARGET=%~2

timeout /t 3 /nobreak >nul
taskkill /f /im NovaForge.exe >nul 2>&1
timeout /t 1 /nobreak >nul
move /y "%NEW%" "%TARGET%" >nul 2>&1
if errorlevel 1 copy /y "%NEW%" "%TARGET%" >nul 2>&1
start "" "%TARGET%"
del "%~f0" >nul 2>&1
exit /b 0
