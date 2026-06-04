---
name: monitor-knowledge
description: Search monitoring data, configure scoring criteria, help user manage sources and digest. Use when user asks about trends, news, monitoring, digest quality, or content research.
---

# Мониторинг контента

## Поиск

Данные из YouTube, Twitter, Telegram, GitHub, RSS хранятся локально в SQLite. Поиск через CLI:

```bash
NODE_PATH=$HOME/.iia/bot/node_modules node $HOME/.iia/monitor/search.js keyword "Claude Code"
NODE_PATH=$HOME/.iia/bot/node_modules node $HOME/.iia/monitor/search.js semantic "стратегия AI"
NODE_PATH=$HOME/.iia/bot/node_modules node $HOME/.iia/monitor/search.js hybrid "AI agents"
NODE_PATH=$HOME/.iia/bot/node_modules node $HOME/.iia/monitor/search.js latest --days 1
NODE_PATH=$HOME/.iia/bot/node_modules node $HOME/.iia/monitor/search.js author karpathy
NODE_PATH=$HOME/.iia/bot/node_modules node $HOME/.iia/monitor/search.js stats
```

Опции: `--days N` (дефолт 7), `--limit N` (дефолт 10), `--json` (для обработки).

### Когда что

- Точное имя/термин/продукт → `keyword`
- "Найди похожее на X" / размытая тема → `semantic`
- Для контента / исследования → `hybrid`
- "Что нового?" → `latest`
- "Что писал X?" → `author`
- Telegram каналы, RSS статьи → те же команды, данные в одной базе

## Настройка скоринга

### DIGEST-CONTEXT.md — критерии оценки контента

Файл `~/workspace/DIGEST-CONTEXT.md` определяет что важно для пользователя при оценке контента. Скоринг читает этот файл и учитывает при выставлении оценок.

Если файла нет — используется `USER.md` как fallback.

**Когда создать/обновить:**
- Пользователь говорит что дайджест нерелевантный
- Пользователь хочет фокус на определённых темах
- После добавления новых источников с новой тематикой

**Пример содержания:**
```markdown
## Что важно
- AI агенты, автоматизация, разработка
- Claude Code, OpenClaw, инструменты для кодинга
- Реальные кейсы применения AI в бизнесе
- Новые модели, бенчмарки, архитектурные решения

## Что НЕ важно
- Крипта, трейдинг, NFT
- Общие новости без AI контекста
- Маркетинговые анонсы без сути
```

**Как создать:** `Write` файл `DIGEST-CONTEXT.md` в корне workspace. Обсуди с пользователем его интересы.

### Per-source критерии: ~/workspace/scoring/{source}.md

Дополнительно к общим критериям можно создать файлы для каждого источника:
```
~/workspace/scoring/youtube.md    — критерии для YouTube
~/workspace/scoring/twitter.md    — критерии для Twitter
~/workspace/scoring/github.md     — критерии для GitHub
~/workspace/scoring/telegram.md   — критерии для Telegram
~/workspace/scoring/rss.md        — критерии для RSS
```

Эти критерии **добавляются** к общим (DIGEST-CONTEXT.md), не заменяют их. Используй когда пользователь хочет разные фокусы для разных источников.

**Пример `~/workspace/scoring/twitter.md`:**
```
Фокус: AI-инженерия, стартапы, кейсы автоматизации
Важные аккаунты: @karpathy, @swyx, @emollick
Игнорировать: мемы, ретвиты без комментария
```

### USER.md — профиль пользователя

`USER.md` содержит краткую информацию о пользователе (роль, цели, проекты). Используется как fallback для скоринга если DIGEST-CONTEXT.md нет. Также влияет на стиль ответов агента.

## Управление источниками

Источники управляются **через Telegram-бот** (кнопки и команды), не через тебя напрямую.

Если пользователь просит добавить/удалить источник — направь его:

| Тип | Команда в боте |
|-----|---------------|
| YouTube | `/sources add yt @канал` или `/sources add yt URL` |
| Twitter | `/sources add tw @аккаунт` |
| GitHub | `/sources add gh owner/repo` |
| Telegram | `/sources add tg @channel` |
| RSS | `/sources add rss https://example.com/feed.xml` |
| Удалить | `/sources remove yt/tw/gh/tg/rss <имя>` |
| Список | `/sources` |

## Дайджест и расписание

Дайджест (сводка нового контента) настраивается **через Telegram-бот**:

- Кнопка `/monitor` → Дайджест → настройки (время, частота)
- Разовый дайджест: `/digest`

Ты можешь повлиять на **качество** дайджеста через `DIGEST-CONTEXT.md` (см. выше).

## Правила

- Всегда проверяй knowledge base при вопросах о мониторинге, трендах, новостях
- Для контента — сначала `hybrid`, потом детали через `keyword`
- Указывай автора, дату, score, ссылку в ответе
- Если дайджест нерелевантный — предложи создать/обновить DIGEST-CONTEXT.md
- Если пользователь хочет новый источник — направь на команду бота
- Если search.js не найден: `ls $HOME/.iia/monitor/search.js`
