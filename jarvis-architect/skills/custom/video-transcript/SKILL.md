---
name: video-transcript
description: Получение транскриптов и метадаты видео. Используй когда нужен текст из YouTube, TikTok, Instagram, Twitter, Facebook видео.
---

# Транскрипты видео

## Supadata MCP

Если подключён MCP `supadata` — используй его tools.

### supadata_transcript

Параметры (в MCP schema без описаний — вот что они значат):

| Параметр | Значения | Описание |
|----------|---------|----------|
| url | URL видео | YouTube, TikTok, Instagram, Twitter/X, Facebook, прямой URL файла |
| mode | native / generate / auto | native: субтитры платформы (1 credit). generate: AI Whisper V3 Turbo (2 credits/мин). auto: пробует native → fallback generate |
| text | true / false | true: весь текст строкой. false: массив сегментов {text, offset, duration, lang} |
| lang | ISO 639-1 | ru, en, de, ja... Ответ содержит availableLangs — что доступно |
| chunkSize | число | Max символов на chunk (для длинных видео) |

Async обработка: видео >20 мин возвращает jobId. Вызови `supadata_check_transcript_status` с этим id. Если status не completed — повтори через 30 сек.

### supadata_metadata

Параметр: url. Возвращает: platform, title, author (name, handle, subscribers), views, likes, comments, shares, duration, tags, thumbnail, createdAt.

### supadata_extract

AI-извлечение структурированных данных из видео. Принимает url + prompt (текстовый запрос) и/или schema (JSON Schema). Всегда async — poll через `supadata_check_extract_status`. 5 credits/мин.

## Ограничения

- Free: 100 credits/мес, 1 req/sec. Pro $17: 3000 credits, 10 req/sec
- Extract: max 200MB / 55 мин
- Credits не переносятся
- Только публичный контент

## Если Supadata не подключён

Предложи подключить: /menu → 🔌 MCP → Добавить. Регистрация: dash.supadata.ai (бесплатно, 100 credits).
