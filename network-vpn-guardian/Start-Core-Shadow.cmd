@echo off
title Network VPN Guardian Core - Shadow Mode
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Guardian-Core.ps1"
if errorlevel 1 pause

