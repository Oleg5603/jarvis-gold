---
name: web-scraping
description: Получение контента веб-страниц. Используй когда нужно открыть URL, скрейпить сайт, извлечь данные со страницы.
---

# Веб-скрейпинг

Несколько инструментов для работы с URL. Выбор зависит от задачи.

## Инструменты

### WebFetch (встроенный)
Простой HTTP GET. Возвращает HTML/JSON/текст.
- Быстрый, бесплатный, без зависимостей
- Для: API endpoints, JSON, RSS фиды, статические страницы
- НЕ рендерит JavaScript

### supadata_scrape (MCP)
Страница → чистый markdown. Убирает навигацию, рекламу, скрипты.
- Для: статьи, блоги, документация — когда нужен чистый контент
- Params: url, noLinks (убрать ссылки), lang
- 1 credit

### supadata_map / supadata_crawl (MCP)
- map: все URL сайта (sitemap discovery)
- crawl: контент нескольких страниц (async, 1 credit/стр, limit param)
- Для: исследование сайта, массовый сбор

### Apify website-content-crawler (MCP)
JS-рендеринг, SPA, динамические сайты.
- Для: если supadata_scrape вернул пустоту (страница рендерится JS-ом)
- Вызов: search-actors → fetch-actor-details → call-actor

### Playwright (npm)
Полный headless браузер. Доступен через Bash: `npx playwright ...`
- Для: интерактив (клики, формы, авторизация), скриншоты, сложные SPA
- Если подключён Playwright MCP — удобнее через его tools

## Когда что

| Задача | Инструмент |
|--------|-----------|
| API / JSON endpoint | WebFetch |
| Статья / блог | supadata_scrape |
| JS-рендеринг / SPA | Apify crawler или Playwright |
| Все URL сайта | supadata_map |
| Много страниц | supadata_crawl |
| Формы / клики / скриншоты | Playwright |

## Проверка доступности

Не все MCP могут быть подключены. Проверяй:
- Supadata MCP → если нет, используй WebFetch
- Apify MCP → если нет, используй Playwright через Bash
- Playwright → всегда доступен через npx
