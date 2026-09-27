@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Guardian.ps1" -SelfTest
pause

