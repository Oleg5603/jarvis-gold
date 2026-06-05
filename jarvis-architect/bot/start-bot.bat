@echo off
chcp 65001 >nul
title Gavrila-Jarvis Bot
cd /d %~dp0
echo Starting bot...
node index.js
echo.
echo === BOT STOPPED ===
pause
