---
name: server-management
description: Помощь клиенту с доступом к DigitalOcean VPS, управлением сервисами и аварийным входом
---

# Управление сервером DigitalOcean

Полная инструкция для клиента: ~/workspace/SERVER-ACCESS.md
Если клиент спрашивает про доступ к серверу — прочитай этот файл и покажи нужный раздел.

## Твои возможности и ограничения

### Можешь из Telegram:
- Направить клиента в /settings → 🔐 SSH доступ (добавить ключ, открыть IP)
- Диагностика: `journalctl -u iia-bot -n 50`, `df -h`, `free -h`
- Показать содержимое SERVER-ACCESS.md
- Отправить recovery-access.txt как файл-документ (по просьбе клиента)
- Объяснить клиенту пошагово что делать

### НЕ можешь из Telegram (sudo заблокирован в песочнице бота):
- Управлять сервисами (systemctl restart/stop) — направляй в VS Code Terminal
- Читать .env — направляй в VS Code Terminal

## Когда клиент хочет SSH

Направь клиента: /settings → 🔐 SSH доступ. Там всё в одном месте:
- Добавить ключ (кнопка в меню)
- Открыть IP (кнопка в меню)
- Инструкция по созданию ключа

Альтернативный путь (для продвинутых) — VS Code Terminal:
1. `echo "КЛЮЧ" >> ~/.ssh/authorized_keys`
2. `sudo /usr/local/bin/allow-my-ssh.sh IP`
3. `ssh client@IP_СЕРВЕРА`

## Четыре уровня доступа

| Уровень | Способ | Когда использовать |
|---------|--------|-------------------|
| 1 | Telegram | Повседневная работа |
| 2 | VS Code tunnel | Код, терминал, sudo-операции |
| 3 | SSH | Прямое подключение (для продвинутых) |
| 4 | Recovery Console | Аварийный вход когда всё мертво |

**Recovery Console:** cloud.digitalocean.com → Droplets → сервер → Access → Recovery Console.
Логин: `client`, пароль: из `~/.iia/recovery-access.txt` (строка DO_CONSOLE_PASSWORD).
НЕ путать с Droplet Console (кнопка "Console") — она не работает из-за файрвола.

## Аварийные ситуации

### Бот не отвечает
Направь клиента: VS Code Terminal → `sudo systemctl restart iia-bot`
Если tunnel тоже не работает → Recovery Console → та же команда.

### SSH перестал работать
Домашний IP сменился. Повторить шаг 3 из инструкции SSH.

### Всё мертво
Recovery Console — единственный путь. Объясни:
1. cloud.digitalocean.com → Droplets → сервер → Access → Recovery Console
2. Логин: `client`, пароль: из сообщения бота или recovery-access.txt
3. Droplet Console (кнопка "Console") НЕ работает — именно Recovery Console

## recovery-access.txt

Файл `~/.iia/recovery-access.txt` содержит логин и пароль Recovery Console.

**Можно:** отправить файл клиенту как документ (аттачмент) если просит свой пароль.
**Нельзя:** показывать содержимое текстом в чате.

## Диагностика (можешь выполнить из Telegram)

- `journalctl -u iia-bot -n 30` — ошибки бота
- `journalctl -u code-tunnel -n 20` — ошибки tunnel
- `df -h` — диск
- `du -sh ~/.iia/monitor/*` — мониторинг (основной потребитель места)
- `ls -la ~/.iia/bot/index.js` — дата версии бота

## Чего НЕ делать

- НЕ редактировать ~/.iia/bot/index.js — перезапишется при обновлении
- НЕ удалять ~/.iia/.env — токены авторизации
- НЕ обещать sudo из Telegram
