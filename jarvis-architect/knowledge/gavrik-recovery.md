# Восстановление Гаврика (@mayroden_bot)

> Если Гаврик молчит в Telegram — читай этот файл.

## Актуальный деплой (проверено 2026-07-14)

Реально работающий бот — сервис **`gavrik.service`**, запускает `/root/gavrik/bot.py`.
Это **НЕ git-репозиторий на сервере** — файлы копируются вручную (scp) с локальной
машины (`C:\Users\HP\gavrik`, репо `github.com/Oleg5603/gavrik`). На сервере в
`/root/gavrik/` иногда остаются ручные бэкапы вида `handlers.py.bak-YYYYMMDDHHMMSS`
от прошлых правок на проде — это нормально, не мусор для удаления не глядя.

`telegram-bot.service` (директория `/root/telegram-bot`, единственная НАСТОЯЩАЯ git-копия
на сервере) — это **старый неактивный сервис** (`inactive dead`), больше не тот бот,
которым пользуется Олег. Инструкции ниже по нему устарели, оставлены для истории —
если увидишь оба сервиса, ориентируйся на `gavrik.service`.

## Быстрая диагностика (SSH на сервер)

```bash
ssh -i C:\Users\HP\.ssh\id_ed25519 root@159.194.200.172
systemctl status gavrik.service
journalctl -u gavrik.service --no-pager -n 20
```

## Где лежит токен Гаврика

**Главный источник правды (локально):**
```
C:\Users\HP\gavrik\.env
BOT_TOKEN=<см. .env, не хранить значение здесь>
```

**На сервере:**
```
/root/gavrik/.env → BOT_TOKEN
```

**Если токен не работает (Telegram вернул 401):**
→ Зайди @BotFather → /mybots → @mayroden_bot → API Token → обнови и в локальном,
и в серверном `.env`, затем `systemctl restart gavrik.service`.

## Обновление кода на сервере (нет git — деплой руками)

```bash
scp -i C:\Users\HP\.ssh\id_ed25519 \
  C:\Users\HP\gavrik\handlers.py C:\Users\HP\gavrik\projects_registry.py \
  root@159.194.200.172:/root/gavrik/
ssh -i C:\Users\HP\.ssh\id_ed25519 root@159.194.200.172 "systemctl restart gavrik.service"
```

## Частые причины падения и решения

### 1. Бот запускается но не отвечает / конфликт с другим инстансом
Telegram даёт только один активный `getUpdates`-поллинг на токен. Если видишь в логах
`Conflict: terminated by other getUpdates request` — где-то параллельно запущен второй
процесс с тем же токеном (например, старый `telegram-bot.service` или ручной запуск).
```bash
systemctl status telegram-bot   # проверить, не ожил ли старый сервис
ps aux | grep bot.py            # проверить, нет ли второго python-процесса
journalctl -u gavrik.service -f # смотреть живой лог
```

### 2. KeyError по переменной окружения — нет значения в .env
```bash
echo 'ИМЯ_ПЕРЕМЕННОЙ=значение' >> /root/gavrik/.env
systemctl restart gavrik.service
```

## Перезапуск

```bash
systemctl restart gavrik.service
systemctl status gavrik.service
```

## Проверка что всё хорошо

```bash
# Статус должен быть: Active: active (running)
systemctl status gavrik.service --no-pager

# Проверка токена через API
curl -s "https://api.telegram.org/bot$(grep BOT_TOKEN /root/gavrik/.env | cut -d= -f2)/getMe"
```
