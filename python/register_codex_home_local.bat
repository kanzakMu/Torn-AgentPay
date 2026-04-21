@echo off
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0register_codex_home_local.ps1" %*
exit /b %errorlevel%
