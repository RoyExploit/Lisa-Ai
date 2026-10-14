@echo off
setlocal EnableExtensions EnableDelayedExpansion

title Lisa AI - Launcher
cd /d "%~dp0"

color 0E

echo ==========================================================================
echo   _     ___  ____    _      _    ___
echo  ^| ^|   ^|_ _/ ___^|  / \    / \  ^|_ _^|
echo  ^| ^|    ^| ^|\___ \ / _ \  / _ \  ^| ^|
echo  ^| ^|___ ^| ^| ___) / ___ \/ ___ \ ^| ^|
echo  ^|_____^|___^|____/_/   \_\_/   \_\___^|
echo.
echo                 LISA AI  -  Autonomous Desktop Intelligence
echo              Self-Evolving Cognitive Engine - Voice Assistant
echo         [Skill Forge  //  Crucible Sandbox  //  180 FPS HoloCore]
echo.
echo ==========================================================================
echo.
echo Launching automated bootstrap sequence...

powershell.exe -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1"

if %errorlevel% neq 0 (
  echo ERROR: Bootstrap failed.
  pause
  exit /b %errorlevel%
)
exit /b 0