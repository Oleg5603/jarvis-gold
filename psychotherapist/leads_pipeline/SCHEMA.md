# Схема коммуникации агентов

## Mermaid-диаграмма

```mermaid
flowchart TD
    Start([▶ orchestrator.py]) --> Scout

    Scout["🔍 Scout Agent\nscout_agent.py\nСобирает семантику:\nключевые слова, фразы"]
    Scout -->|raw_keywords.json| Parallel

    subgraph Parallel["⚡ Параллельный запуск"]
        Monitor["📡 Monitor Agent\nmonitor_agent.py\nСканирует Telegram-каналы\n#отношения #брак #психология"]
        ForumHunter["🕷 Forum Hunter\nforum_hunter.py\nПарсит: pikabu, woman.ru,\nbabyblog, reddit, vc.ru"]
    end

    Parallel -->|raw_leads.json| Validator

    Validator["✅ Validator Agent\nvalidator_agent.py\nПроверяет: не бот, подходит\nтеме, оценивает confidenceScore"]
    Validator -->|enriched_leads.json| CRM

    CRM["📋 CRM Agent\ncrm_agent.py\nФильтрует, ранжирует\nпо готовности 1–5"]
    CRM -->|ready_for_crm.json| Done

    Done([✅ Лиды готовы])

    style Scout fill:#4a9eff,color:#fff
    style Monitor fill:#f59e0b,color:#fff
    style ForumHunter fill:#f59e0b,color:#fff
    style Validator fill:#10b981,color:#fff
    style CRM fill:#8b5cf6,color:#fff
```

## Файлы данных

| Файл | Кто пишет | Кто читает | Что внутри |
|------|-----------|------------|-----------|
| `raw_keywords.json` | Scout | Monitor, Forum Hunter | Ключевые слова, фразы, эмоциональные маркеры |
| `raw_leads.json` | Monitor + Forum Hunter | Validator | Сырые лиды: URL, автор, цитата, интент |
| `enriched_leads.json` | Validator | CRM | Лиды с confidence_score, валидацией |
| `ready_for_crm.json` | CRM | Пользователь / Google Sheets | Финальные лиды с уровнем готовности 1–5 |

## Протокол передачи

- Все данные — JSON-файлы в `./leads_pipeline/`
- Лог каждого агента: `logs/{agent_id}_{timestamp}.log`
- Оркестратор запускает агентов через `asyncio.create_subprocess_exec`
- Ошибка одного агента **не останавливает** весь пайплайн
- Monitor и Forum Hunter пишут в один файл с автомерджем по URL

## Переменные окружения

| Переменная | Агент | Обязательно |
|-----------|-------|-------------|
| `ANTHROPIC_API_KEY` | Scout, Forum Hunter, Validator | Да |
| `TELEGRAM_API_ID` | Monitor | Нет (агент пропускается) |
| `TELEGRAM_API_HASH` | Monitor | Нет (агент пропускается) |
| `GOOGLE_SHEETS_ID` | CRM | Нет (файл всё равно создаётся) |

## Запуск

```bash
# Установить зависимости
pip install anthropic aiohttp beautifulsoup4 telethon gspread

# Запустить пайплайн
cd /root/telegram-bot
python leads_pipeline/orchestrator.py

# Или отдельный агент
python leads_pipeline/agents/scout_agent.py
```
