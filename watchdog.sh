#!/bin/bash
LOG=/root/telegram-bot/watchdog.log
TS=$(date "+%Y-%m-%d %H:%M:%S")

if ! systemctl is-active --quiet telegram-bot; then
    echo "[$TS] Gavrik down - restarting" >> $LOG
    ln -sf /root/telegram-bot/forex/gold_news.py /root/telegram-bot/gold_news.py
    ln -sf /root/telegram-bot/forex/trading.py /root/telegram-bot/trading.py
    ln -sf /root/telegram-bot/psychotherapist/leads.py /root/telegram-bot/leads.py
    grep -q TELEGRAM_BOT_TOKEN /root/telegram-bot/.env || echo "TELEGRAM_BOT_TOKEN=7960862830:AAGfQmQHOjN8B7HyspS3m4Pzg3rpzW5juSw" >> /root/telegram-bot/.env
    systemctl restart telegram-bot
    sleep 5
    if systemctl is-active --quiet telegram-bot; then
        echo "[$TS] Restored OK" >> $LOG
    else
        echo "[$TS] FAILED:" >> $LOG
        journalctl -u telegram-bot --no-pager -n 5 >> $LOG
    fi
fi
[ -f $LOG ] && tail -200 $LOG > $LOG.tmp 2>/dev/null && mv $LOG.tmp $LOG 2>/dev/null
exit 0
