@echo off
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0install_agent_package.ps1" %*
exit /b %errorlevel%
