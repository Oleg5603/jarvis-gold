# CLAUDE.md — Описание проекта

## Репозиторий
- GitHub: `https://github.com/Oleg5603/jarvis-gold`
- Основная ветка: `main`
- Рабочая ветка (суфлёр): `nutritionist`
- Сервер: `159.194.200.172` (root)

## Стек
- Python 3.11+
- PyQt6 — десктопные окна
- SpeechRecognition + pyaudio — распознавание речи (Google Speech API, онлайн)
- PyInstaller — сборка в .exe
- GitHub Actions — CI/CD, автосборка Windows .exe

## Структура проекта
```
telegram-bot/
├── bot.py                  ← основной Telegram-бот (Гаврик)
├── gold_news.py            ← новости золота
├── misemia_bot.py          ← бот для мисемии
├── memory.json             ← персистентная память бота
├── owner.txt               ← id хозяина
├── settings.json           ← настройки окружения
├── nutritionist/           ← суфлёр нутрициолога
│   ├── main.py             ← запуск, поток распознавания речи
│   ├── window_questions.py ← Окно 1: вопросы + таймер
│   ├── window_tips.py      ← Окно 2: рекомендации
│   ├── knowledge_base.py   ← 19 тем, 344 ключевых слова
│   └── SETUP_AND_BUILD.bat ← сборка на Windows
└── .github/workflows/      ← GitHub Actions (сборка Sufler.exe)
```

## Суфлёр нутрициолога
- Слушает микрофон → распознаёт ключевые слова → показывает подсказки
- 2 окна: вопросы к клиенту + рекомендации по Малаховой "Будь стройной"
- Таймер консультации с кнопками +10 мин, цветовая индикация
- Индикатор статуса микрофона
- Собирается в zip-архив через GitHub Actions → скачать: Actions → Artifacts → Sufler-zip

## Как работать с Claude Code
- Основной ИИ-ассистент: **Гаврик** (claude-sonnet-4-6)
- Пуш в ветку `nutritionist` → автоматически запускает сборку .exe
- Релизы создаются через Artifacts (не через GitHub Releases — нет прав)
