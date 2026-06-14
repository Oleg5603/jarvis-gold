#!/bin/bash
LOG=/root/telegram-bot/watchdog.log
TS=2026-06-14 18:36:54

if ! systemctl is-active --quiet telegram-bot; then
    echo [] Гаврик упал — перезапускаю... >> 
    ln -sf /root/telegram-bot/forex/gold_news.py /root/telegram-bot/gold_news.py
    ln -sf /root/telegram-bot/forex/trading.py /root/telegram-bot/trading.py
    ln -sf /root/telegram-bot/psychotherapist/leads.py /root/telegram-bot/leads.py
    grep -q TELEGRAM_BOT_TOKEN /root/telegram-bot/.env || echo 'TELEGRAM_BOT_TOKEN=7960862830:AAGfQmQHOjN8B7HyspS3m4Pzg3rpzW5juSw' >> /root/telegram-bot/.env
    systemctl restart telegram-bot
    sleep 5
    if systemctl is-active --quiet telegram-bot; then
        echo [] Восстановлен успешно >> 
    else
        echo [] ОШИБКА восстановления: >> 
        journalctl -u telegram-bot --no-pager -n 5 >> 
    fi
fi

tail -200  > .tmp 2>/dev/null && mv .tmp  2>/dev/null
