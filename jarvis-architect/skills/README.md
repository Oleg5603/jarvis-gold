# Claude Code Skills

Публичная коллекция скиллов для Claude Code. Часть курса «Архитектор нейросотрудников» — устанавливаются в Агента ученика по запросу.

## Структура

```
global/     — универсальные скиллы (дизайн, UI, презентации)
custom/     — специализированные скиллы (код, исследования, контент)
```

## Global (8 скиллов)

| Скилл | Назначение |
|---|---|
| banner-design | Баннеры для соцсетей и рекламы |
| brand | Голос бренда, стайлгайды, айдентика |
| design | Логотипы, корпоративная айдентика, иконки |
| design-system | Дизайн-токены, компоненты |
| presentation-generator | HTML-презентации для курсов, питчей, вебинаров |
| slides | HTML-презентации с Chart.js |
| ui-styling | Стилизация через Tailwind/shadcn |
| ui-ux-pro-max | UI/UX для веб и мобайл, 50+ стилей |

## Custom (12 скиллов)

| Скилл | Назначение |
|---|---|
| code-review | Анализ кода |
| competitor-research | Исследование трендов и анализ ЦА |
| discovery-interview | Интервью для превращения идей в ТЗ |
| frontend-design | Продакшн-фронтенд с высоким дизайном |
| fullstack-developer | Фулстек: React, Node.js, базы данных |
| instagram-stories | Instagram Stories с текстом на фото |
| media-download | Скачивание медиа |
| monitor-knowledge | Мониторинг и база знаний |
| server-management | Управление сервером |
| system | Системные операции |
| video-transcript | Транскрипция видео |
| web-scraping | Парсинг веб-страниц |

## Установка одного скилла

Скажи своему Агенту:

```
Установи скилл <имя> из https://github.com/Ntmib/claude-skills-public
```

Агент скачает файлы и положит в `~/.claude/skills/<имя>/`. После `/reset` скилл активен.

## Установка всех скиллов

```bash
git clone https://github.com/Ntmib/claude-skills-public ~/claude-skills-public
cp -r ~/claude-skills-public/global/* ~/.claude/skills/
cp -r ~/claude-skills-public/custom/* ~/.claude/skills/
```

## Лицензия

Скиллы предоставляются «как есть» для использования с Claude Code.
