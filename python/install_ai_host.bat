@echo off
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0install_ai_host.ps1" %*
exit /b %ERRORLEVEL%
