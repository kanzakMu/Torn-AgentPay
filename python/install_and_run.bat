@echo off
setlocal

set SCRIPT_DIR=%~dp0
powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%install_and_run.ps1" %*
exit /b %ERRORLEVEL%
