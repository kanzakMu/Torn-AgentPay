@echo off
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0install_skill.ps1" %*
exit /b %ERRORLEVEL%
