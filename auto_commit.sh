#!/bin/bash
# Auto commit & push — runs every 30 min and after 7 min idle

cd /root/telegram-bot || exit 1

# Проверяем есть ли изменения
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    exit 0
fi

git add -A
git commit -m "auto: сохранение $(date '+%Y-%m-%d %H:%M')"
git push origin "$(git branch --show-current)" 2>&1
