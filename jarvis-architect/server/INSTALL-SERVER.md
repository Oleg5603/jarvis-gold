# Инструкция для Claude Code: установка Агента на VPS

> Этот файл читает Claude Code. Если ты Claude — выполняй всё по шагам. Если у тебя ещё нет IP-адреса сервера и пароля root — спроси у пользователя одним сообщением: 1) IP-адрес сервера, 2) пароль root, 3) опционально: токен Telegram-бота от @BotFather. Дождись ответа, потом продолжай.

## Как общаться с пользователем

**КРИТИЧНО:** пользователь — новичок, который впервые работает с сервером. Он не знает что такое SSH, systemd, npm. Общайся с ним так:

1. **Перед каждым шагом** — объясни ОДНИМ предложением что сейчас будешь делать. Пример: «Сейчас подключаюсь к вашему серверу и проверяю связь...»
2. **После каждого шага** — коротко скажи что получилось. Пример: «Связь с сервером есть, всё ок. Перехожу к установке программ.»
3. **Если ошибка** — объясни простым языком что пошло не так и что делать. Не кидай сырой лог без объяснения.
4. **Не пугай техническими деталями.** Пользователю не нужно знать что такое sysctl или chmod. Просто делай и говори результат.
5. **Показывай прогресс.** После каждого крупного шага пиши что-то вроде: «Шаг 3 из 15 готов. Устанавливаю программы на сервер...»
6. **В конце** — дай чёткую пошаговую инструкцию что делать дальше (VS Code Tunnel). Каждый пункт = одно конкретное действие. «Нажмите сюда → введите это → нажмите то.»
7. **Если нужно действие от пользователя** (например, открыть консоль Beget) — объясни ГДЕ это, КАК найти, ЧТО нажать. Не пиши «зайдите в VNC-консоль» — пиши «откройте сайт beget.com → войдите в личный кабинет → найдите раздел VPS → нажмите на свой сервер → нажмите кнопку Консоль».

Стиль: дружелюбный, спокойный, как будто помогаешь другу настроить компьютер. Без воды, но с заботой.

## Контекст

Пользователь — ученик курса «Архитектор нейросотрудников». У него:
- Локально на компьютере: папка с файлами Агента (CLAUDE.md, SOUL.md, MEMORY.md, GOALS.md, memory/, knowledge/)
- Новый VPS (обычно Beget, Ubuntu 22 или 24), на который нужно всё перенести
- Опционально: токен Telegram-бота для установки Telegram-бота (работает через подписку Claude, API-ключ не нужен)

Твоя задача — подключиться к серверу, установить окружение, скопировать шаблоны файлов, настроить VS Code Tunnel, провести интервью из 10 вопросов (заполнить плейсхолдеры), скопировать заполненные файлы обратно на сервер и (если дан токен) запустить Telegram-бота. Интервью проводится в самом конце, когда сервер полностью настроен.

## Шаг 1. Найди локальные файлы

Проверь текущую папку — есть ли там DNA-файлы Агента:

```bash
ls CLAUDE.md SOUL.md MEMORY.md GOALS.md 2>/dev/null
```

Если файлы есть — запомни путь, ты скопируешь их на сервер в шаге 5.
Если файлов нет — проверь домашнюю папку и ~/jarvis/:
```bash
ls ~/jarvis/CLAUDE.md ~/jarvis/SOUL.md 2>/dev/null
ls ~/workspace/CLAUDE.md ~/workspace/SOUL.md 2>/dev/null
```
Если нигде нет — скажи пользователю: «Не нашёл файлы Агента. Откройте Claude Code в папке где лежат SOUL.md, MEMORY.md и другие файлы, и повторите команду.»

## Шаг 2. Подключись к серверу

IP и пароль пользователь указал ранее (или ты уже спросил на входе). Используй `expect` для автоматического ввода пароля.

Сначала проверь соединение:
```bash
expect -c '
  set timeout 15
  spawn ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 root@IP_СЕРВЕРА "echo CONNECTION_OK"
  expect {
    "password:" { send "ПАРОЛЬ\r"; exp_continue }
    "CONNECTION_OK" { exit 0 }
    timeout { exit 1 }
    eof { exit 1 }
  }
'
```

Замени `IP_СЕРВЕРА` и `ПАРОЛЬ` на данные из сообщения пользователя.

**Если не подключается** (таймаут, ошибка) — скажи пользователю:

> Прямое подключение не прошло. Скорее всего VPN блокирует соединение. Есть простой запасной путь:
>
> 1. Зайдите в панель управления Beget → ваш VPS → кнопка «Консоль»
> 2. Войдите как root с вашим паролем
> 3. Введите: `wget ntmib.github.io/jarvis-architect/s`
> 4. Введите: `bash s`
> 5. Скрипт всё установит. После этого напишите мне «готово» — я скопирую ваши файлы.

И жди ответа. Когда пользователь скажет «готово» — перейди к шагу 5 (копирование файлов).

## Шаг 3. Установи систему

Выполняй каждую команду через SSH. Вспомогательная функция:

```bash
# Для каждой команды используй этот шаблон:
expect -c '
  set timeout 120
  spawn ssh -o StrictHostKeyChecking=no root@IP_СЕРВЕРА "КОМАНДА"
  expect "password:" { send "ПАРОЛЬ\r" }
  expect eof
'
```

Последовательность:

**3.1. Базовые пакеты:**
```
apt-get update -qq 2>&1 | tail -3 && apt-get install -y -qq curl git jq unzip 2>&1 | tail -3
```

**3.2. Node.js 20:**
```
curl -fsSL https://deb.nodesource.com/setup_20.x | bash - 2>&1 | tail -5 && apt-get install -y -qq nodejs 2>&1 | tail -3 && node -v
```

**3.3. Claude Code CLI:**
```
npm install -g @anthropic-ai/claude-code 2>&1 | tail -5 && which claude
```

**3.4. Пользователь agent и папки:**
```
id agent 2>/dev/null || useradd -m -s /bin/bash agent && mkdir -p /home/agent/workspace/memory /home/agent/workspace/knowledge /home/agent/projects /home/agent/.agent/bot /home/agent/.claude/skills && chown -R agent:agent /home/agent && echo OK
```

**3.5. Права на Claude Code для пользователя agent:**
```
CLAUDE_REAL=$(readlink -f $(which claude 2>/dev/null) 2>/dev/null) && if [ -n "$CLAUDE_REAL" ]; then chmod -R a+rX $(dirname "$CLAUDE_REAL") 2>/dev/null; chmod -R a+rX $(dirname $(dirname "$CLAUDE_REAL")) 2>/dev/null; chmod -R a+rX $(dirname $(dirname $(dirname "$CLAUDE_REAL"))) 2>/dev/null; fi && echo OK
```

**3.6. Отключение IPv6 (фикс зависаний Node.js):**
```
sysctl -w net.ipv6.conf.all.disable_ipv6=1 2>/dev/null; sysctl -w net.ipv6.conf.default.disable_ipv6=1 2>/dev/null; echo OK
```

После каждого шага проверяй вывод. Если ошибка — покажи пользователю и предложи решение. Не останавливайся без причины.

## Шаг 4. Установи VS Code CLI

```
if ! command -v code >/dev/null 2>&1; then curl -fL 'https://github.com/Ntmib/jarvis-architect/releases/download/v1.0.0/vscode-cli.tar.gz' -o /tmp/vscode.tar.gz 2>&1 || curl -fL 'https://code.visualstudio.com/sha/download?build=stable&os=cli-alpine-x64' -o /tmp/vscode.tar.gz 2>&1; tar -xzf /tmp/vscode.tar.gz -C /usr/local/bin/ 2>&1; rm -f /tmp/vscode.tar.gz; fi && code --version 2>/dev/null || echo 'VS Code CLI not found'
```

## Шаг 5. Скопируй файлы Агента на сервер

> **Примечание:** на этом этапе файлы могут содержать `{{плейсхолдеры}}` — это нормально. Плейсхолдеры будут заполнены позже (Шаг 11 — интервью), после чего заполненные файлы будут скопированы повторно (Шаг 12).

Скопируй все DNA-файлы из локальной папки на сервер. Используй scp с expect:

```bash
# Шаблон для копирования одного файла:
expect -c '
  set timeout 30
  spawn scp -o StrictHostKeyChecking=no ./ФАЙЛ root@IP_СЕРВЕРА:/home/agent/workspace/
  expect "password:" { send "ПАРОЛЬ\r" }
  expect eof
'
```

Скопируй по очереди все DNA-файлы (каждый — если существует локально):
1. `CLAUDE.md`
2. `SOUL.md`
3. `MEMORY.md`
4. `GOALS.md`
5. `USER.md`
6. `MISSION.md`
7. `PROJECTS.md`
8. `PREFERENCES.md`
9. `LEARNED.md`

Потом скопируй папки (рекурсивно, флаг -r):
10. `memory/` → `/home/agent/workspace/memory/`
11. `knowledge/` → `/home/agent/workspace/knowledge/`

**Настройки Claude Code (.claude/):**
7. Если у пользователя есть локальная папка `.claude/` — скопируй её в `/home/agent/.claude/` (НЕ в workspace!). Это настройки Claude Code: settings.json (правила светофора) и skills/ (навыки).

Если `.claude/` нет локально — скачай дефолтные настройки и скиллы из репозитория:
```
curl -fsSL https://raw.githubusercontent.com/Ntmib/jarvis-architect/main/.claude/settings.json -o /home/agent/.claude/settings.json
```

**Скачай дополнительные шаблоны (SOUL-режимы, SERVICES.md):**
```
REPO="https://raw.githubusercontent.com/Ntmib/jarvis-architect/main"
for F in SERVICES.md SOUL-coder.md SOUL-researcher.md SOUL-strategist.md; do
  curl -fsSL "$REPO/$F" -o "/home/agent/workspace/$F" 2>/dev/null
done && echo OK
```

**Установи скиллы (навыки агента):**
Скиллы — это готовые инструкции, которые усиливают агента. Скачай базовые скиллы:
```
REPO="https://raw.githubusercontent.com/Ntmib/jarvis-architect/main"
for SKILL in discovery-interview content-creator fullstack-developer frontend-design reminder; do mkdir -p /home/agent/.claude/skills/$SKILL && curl -fsSL "$REPO/.claude/skills/$SKILL/SKILL.md" -o /home/agent/.claude/skills/$SKILL/SKILL.md; done && echo OK
```

После копирования — поправь владельца и создай симлинк для единой памяти:
```
chown -R agent:agent /home/agent/workspace /home/agent/.claude && ln -sf /home/agent/workspace/CLAUDE.md /home/agent/CLAUDE.md && chown -h agent:agent /home/agent/CLAUDE.md && echo OK
```

> **Зачем симлинк:** Claude Code в VS Code открывается в `/home/agent/` и ищет `CLAUDE.md` в этой папке. Симлинк делает так, что и бот, и VS Code читают один и тот же файл с правилами — единый мозг агента.

## Шаг 6. Проверь результат

Выполни на сервере:
```
echo '=== Node.js ===' && node -v && echo '=== Claude Code ===' && which claude && echo '=== VS Code CLI ===' && which code 2>/dev/null || echo 'нет' && echo '=== Файлы Агента ===' && ls -la /home/agent/workspace/ && echo '=== Папки ===' && ls -d /home/agent/workspace/memory /home/agent/workspace/knowledge 2>/dev/null
```

Покажи пользователю результат. Скажи:

> Сервер готов. Установлено:
> - Node.js (версия)
> - Claude Code CLI
> - Ваши файлы Агента скопированы в /home/agent/workspace/
> - Рабочая папка для проектов: /home/agent/projects/

## Шаг 7. Установи Telegram-бота (если указан токен бота)

**Если пользователь указал Telegram-бот токен** — установи бота. Если токен не указан — пропусти этот шаг и перейди к шагу 8.

**7.1. Скачай файлы бота из репозитория:**
```
REPO="https://raw.githubusercontent.com/Ntmib/jarvis-architect/main"
BOT="/home/agent/.agent/bot"
mkdir -p $BOT/lib $BOT/scripts $BOT/migrations

# Core bot files
for F in index.js secrets-menu.js voice-helper.js package.json VERSION update-bot.sh; do
  curl -fsSL "$REPO/bot/$F" -o "$BOT/$F"
done
chmod +x "$BOT/update-bot.sh"

# Lib (semantic memory — optional, works without sql.js)
for F in db.js embeddings.js memory-indexer.js memory-search.js; do
  curl -fsSL "$REPO/bot/lib/$F" -o "$BOT/lib/$F"
done

# Scripts
for F in manage-schedule.js memory-search.js reindex.js; do
  curl -fsSL "$REPO/bot/scripts/$F" -o "$BOT/scripts/$F"
done

# Migrations
curl -fsSL "$REPO/bot/migrations/001_memory_index.sql" -o "$BOT/migrations/001_memory_index.sql"

echo OK
```

**7.2. Установи зависимости:**
```
cd /home/agent/.agent/bot && npm install --production 2>&1 | tail -5 && echo OK
```

**7.3. Создай файл окружения:**
```
cat > /home/agent/.agent/.env << 'ENVEOF'
BOT_TOKEN=ТОКЕН_БОТА
AGENT_HOME=/home/agent
ENVEOF
```
Замени `ТОКЕН_БОТА` на значение из сообщения пользователя.

**Безопасность (auto-lock):** Бот автоматически привязывается к первому пользователю, который напишет ему `/start`. После этого бот отвечает ТОЛЬКО ему — все остальные игнорируются. Данные владельца сохраняются в `/home/agent/.agent/owner.json`. Ничего дополнительно настраивать не нужно.

**7.4. Поправь владельца файлов:**
```
chown -R agent:agent /home/agent/.agent
```

**7.5. Зарегистрируй systemd-сервис (БЕЗ запуска):**
```
curl -fsSL https://raw.githubusercontent.com/Ntmib/jarvis-architect/main/bot/agent-bot.service -o /etc/systemd/system/agent-bot.service && systemctl daemon-reload && systemctl enable agent-bot && echo OK
```

> **Важно:** бот НЕ запускается сейчас. Он будет запущен в Шаге 13, после того как файлы Агента будут заполнены данными пользователя. Это нужно чтобы бот сразу заработал с правильными данными.

Скажи пользователю: «Telegram-бот подготовлен. Запустим его чуть позже, когда настроим Вашего Агента.»

## Шаг 8. Настрой VS Code Tunnel

VS Code Tunnel требует авторизации через GitHub. Скажи пользователю:

> Настраиваю **туннель** — прямой коридор между Вашим VS Code и сервером.
>
> **Зачем это нужно.** Один раз настроили — и сервер всегда у Вас в списке: открываете VS Code → видите файлы Агента, правите их как обычную папку. Без туннеля файлы пришлось бы править через чёрное окно консоли в браузере — неудобно и медленно.
>
> **Если у Вас нет VS Code на компьютере** — не страшно: после настройки туннеля можно работать через браузер по адресу `vscode.dev` (войти тем же GitHub-аккаунтом и подключиться к туннелю).
>
> Вам нужно зайти в консоль сервера через браузер. Вот как:
>
> **Шаг 1.** Откройте панель управления Вашего хостинга (beget.com или другой) и войдите в личный кабинет
> **Шаг 2.** Найдите раздел **VPS** и откройте **Консоль** Вашего сервера
> **Шаг 3.** Войдите как `root` с Вашим паролем
> **Шаг 4.** Наберите на клавиатуре команду (не копируйте — наберите вручную):
> ```
> code tunnel --accept-server-license-terms
> ```
> **Шаг 5.** На экране появится ссылка `https://github.com/login/device` и 8-значный код (например `ABCD-1234`). Откройте `github.com/login/device` в браузере на компьютере и введите код с экрана
> **Шаг 6.** После авторизации вернитесь в консоль и нажмите **Ctrl+C**
> **Шаг 7.** Наберите команду:
> ```
> code tunnel service install --accept-server-license-terms
> ```
>
> Туннель настроен! Напишите мне «готово» когда закончите.

## Шаг 9. Как подключиться из VS Code

Когда пользователь скажет что закончил настройку туннеля, скажи:

> Отлично! Теперь подключаемся к серверу из VS Code на вашем компьютере:
>
> **Шаг 1.** Откройте VS Code на вашем компьютере (обычная программа, не в браузере)
> **Шаг 2.** Посмотрите на левую панель — там ряд иконок. Найдите иконку в виде **монитора с маленьким значком** (называется Remote Explorer). Если не видите — нажмите Ctrl+Shift+P, напишите "Remote Explorer" и выберите его
> **Шаг 3.** В открывшейся панели найдите раздел **Tunnels** — там будет название вашего сервера
> **Шаг 4.** Нажмите на него — VS Code откроет папки вашего сервера
> **Шаг 5.** Перейдите в папку `/home/agent/workspace/` — это дом вашего Агента
>
> Всё! Теперь вы работаете на сервере прямо из VS Code, как в обычной папке на своём компьютере. Ваш Агент живёт здесь и работает 24/7.

## Шаг 10. Авторизуй Claude Code через VS Code

> **Важно:** авторизация Claude делается через терминал VS Code на сервере — там ссылки кликабельны и текст можно вставить из буфера обмена. НЕ через консоль хостинга (Beget и др.) — там это не работает.

Скажи пользователю:

> Теперь нужно авторизовать Claude на сервере — чтобы бот мог разговаривать через Вашу подписку. Авторизация делается один раз.
>
> **Шаг 1.** Откройте VS Code на компьютере (Вы уже подключились к серверу в предыдущем шаге)
> **Шаг 2.** Откройте терминал: нажмите **Ctrl + `** (кнопка с обратной кавычкой, рядом с цифрой 1, там же где буква Ё)
> **Шаг 3.** В терминале введите команду:
> ```
> sudo -u agent claude auth login
> ```
> **Шаг 4.** Появится ссылка — **кликните по ней** (в VS Code терминале ссылки кликабельны). Откроется страница авторизации в браузере. Нажмите **Authorize**
> **Шаг 5.** На странице появится код — нажмите **Copy**
> **Шаг 6.** Вернитесь в терминал VS Code и вставьте код (Ctrl+Shift+V или правой кнопкой → Paste). Нажмите Enter
> **Шаг 7.** Должна появиться строчка «Logged in as ...» — значит всё получилось
>
> Когда закончите, напишите мне «готово».
>
> **Если что-то пошло не так:** сделайте скриншот терминала VS Code и пришлите мне. Частые случаи: код просрочился (повторите команду), или код вставили два раза (вставляйте один раз и сразу Enter).

Жди ответа пользователя. Когда скажет «готово» — продолжай.

## Шаг 11. Интервью — настройка Агента под пользователя

Скажи пользователю:

> Сервер полностью настроен. Теперь самое интересное — настроим Агента под Вас. Задам 10 коротких вопросов (5-7 минут).

**Прочитай файл `INSTALL.md`** из локальной папки (где лежат скачанные файлы) и **выполни Шаги 1-6** (приветствие, чтение файлов, интервью из 10 вопросов, замена плейсхолдеров, удаление WIZARD-комментариев, превью пользователю).

**НЕ выполняй Шаги 7-9 из INSTALL.md** (удаление файлов и коммит) — это сделаем здесь, в Шаге 14.

После того как пользователь подтвердил превью — возвращайся сюда и продолжай с Шага 12.

## Шаг 12. Скопируй заполненные файлы на сервер

Теперь DNA-файлы заполнены реальными данными пользователя. Скопируй их на сервер повторно — они заменят шаблоны с {{плейсхолдерами}}.

Используй тот же шаблон scp с expect из Шага 5. Скопируй все 9 DNA-файлов (каждый — если существует):
1. `CLAUDE.md`
2. `SOUL.md`
3. `MEMORY.md`
4. `GOALS.md`
5. `USER.md`
6. `MISSION.md`
7. `PROJECTS.md`
8. `PREFERENCES.md`
9. `LEARNED.md`

После копирования — поправь владельца:
```
chown -R agent:agent /home/agent/workspace && echo OK
```

Скажи пользователю: «Ваши данные скопированы на сервер. Агент теперь знает кто Вы.»

## Шаг 13. Запусти Telegram-бота

**Если пользователь указал токен бота** — теперь запускаем:
```
systemctl start agent-bot && sleep 3 && systemctl status agent-bot --no-pager -l 2>&1 | head -15
```

Если бот запустился — скажи пользователю:

> Telegram-бот запущен! Напишите своему боту в Telegram `/start` — он уже знает Вас и готов к работе.
> Бот работает 24/7 на сервере. Он использует вашу подписку Claude — никаких API-ключей и доплат не нужно.

Если ошибка — покажи лог (`journalctl -u agent-bot -n 20 --no-pager`) и предложи решение.

**Если токен бота не указан** — пропусти этот шаг.

## Шаг 14. Локальная очистка

Удали служебные файлы из локальной папки и сделай первый коммит:

```bash
git rm -r INSTALL.md README.md examples/ 2>/dev/null || true
git add -A
git commit -m "Архитектура Агента собрана"
```

Если у пользователя настроен git remote — сделай `git push`. Если нет — спроси и помоги настроить.

## Шаг 15. Финальная шпаргалка

Выведи пользователю итог:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Установка Агента на сервер завершена
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Что готово
  — Сервер настроен (Node.js, Claude Code CLI, VS Code CLI)
  — VS Code Tunnel привязан к Вашему GitHub
  — Claude авторизован через Вашу подписку
  — 8 DNA-файлов заполнены Вашими данными
  — Файлы Агента на сервере: /home/agent/workspace/
  — Telegram-бот запущен (если давали токен)

Как работать с Агентом
  — VS Code: откройте VS Code → Remote Explorer → Tunnels →
    выберите Ваш сервер → папка /home/agent/workspace/
  — Telegram-бот: напишите боту — он уже знает Вас
  — Файл SOUL.md — «паспорт» Вашего Агента, откройте его первым

Полезные команды бота
  /model   — переключить модель (Sonnet/Opus/Haiku)
  /update  — обновить бота до новой версии
  /status  — проверить состояние
  /settings — подключить API-ключи (Deepgram, GitHub, и др.)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

После вывода шпаргалки — коротко поздравь пользователя с установкой и попрощайся. Не нужно повторять то, что уже на экране.

## Важно

- НЕ показывай пароль пользователя в выводе после его ввода
- НЕ показывай токены и API-ключи в выводе
- НЕ сохраняй пароль в файлы (кроме .env для бота)
- НЕ задавай уточняющих вопросов — действуй по шагам
- Если что-то падает — покажи ошибку и предложи решение, не останавливайся молча
- Если expect не найден (Linux без expect) — предложи установить: `apt-get install -y expect` или предложи VNC-путь
