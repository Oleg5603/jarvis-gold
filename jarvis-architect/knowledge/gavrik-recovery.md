# Восстановление Гаврика (@mayroden_bot)

> Если Гаврик молчит в Telegram — читай этот файл.

## Быстрая диагностика (SSH на сервер)

```bash
ssh -i C:\Users\HP\.ssh\id_ed25519 root@159.194.200.172
systemctl status telegram-bot
journalctl -u telegram-bot --no-pager -n 20
```

## Где лежит токен Гаврика

**Главный источник правды:**
```
C:\Users\HP\Documents\Project\jarvis-architect\bot\.env
BOT_TOKEN=<см. .env, не хранить значение здесь>
```

**Копии токена (должны совпадать):**
- `C:\Users\HP\jarvis-gold\.env` → TELEGRAM_BOT_TOKEN
- На сервере: `/root/telegram-bot/.env` → TELEGRAM_BOT_TOKEN

**Если токен не работает (Telegram вернул 401):**
→ Зайди @BotFather → /mybots → @mayroden_bot → API Token → обнови во всех трёх файлах

## Частые причины падения и решения

### 1. ModuleNotFoundError (gold_news, trading, leads)
Модули уехали в подпапки, симлинки слетели.
```bash
ln -sf /root/telegram-bot/forex/gold_news.py /root/telegram-bot/gold_news.py
ln -sf /root/telegram-bot/forex/trading.py /root/telegram-bot/trading.py
ln -sf /root/telegram-bot/psychotherapist/leads.py /root/telegram-bot/leads.py
systemctl restart telegram-bot
```

### 2. KeyError: 'TELEGRAM_BOT_TOKEN' — нет токена в .env
```bash
echo 'TELEGRAM_BOT_TOKEN=<взять из основного .env, см. выше>' >> /root/telegram-bot/.env
systemctl restart telegram-bot
```

### 3. Бот запускается но не отвечает
```bash
journalctl -u telegram-bot -f   # смотреть живой лог
```

## Перезапуск

```bash
systemctl restart telegram-bot
systemctl status telegram-bot
```

## Проверка что всё хорошо

```bash
# Статус должен быть: Active: active (running)
systemctl status telegram-bot --no-pager

# Проверка токена через API
curl -s "https://api.telegram.org/bot$(grep TELEGRAM_BOT_TOKEN /root/telegram-bot/.env | cut -d= -f2)/getMe"
```
