# Напоминания и регулярные задачи

Когда пользователь просит напомнить, настроить расписание, регулярную задачу или дайджест.

## Триггеры

Активируй этот скилл когда слышишь: "напомни", "не забудь", "каждый день", "каждое утро",
"дайджест", "регулярно", "еженедельно", "отключи напоминание", "мои напоминания",
"убери напоминание", "перенеси на", "через N минут".

## Инструмент

```bash
node ~/.agent/bot/scripts/manage-schedule.js <command> [args]
```

ЗАПРЕЩЕНО:
- crontab — не использовать
- CronCreate / CronDelete / CronList — это инструменты ДРУГОЙ системы, НЕ бота. НИКОГДА не используй их
- Ручная правка schedules.json — только через manage-schedule.js
- Выдуманные ID — не придумывай ID, скрипт генерирует их сам

ЕДИНСТВЕННЫЙ способ создать напоминание: `node ~/.agent/bot/scripts/manage-schedule.js add ...`

## Два типа payload

| payload | Когда | Что происходит при срабатывании |
|---------|-------|---------------------------------|
| reminder | "напомни", "не забудь" (простой текст) | Бот отправляет текст дословно. Claude НЕ вызывается. Бесплатно |
| task | "присылай дайджест", "анализируй", "составь отчёт" | Бот вызывает Claude с prompt. Claude выполняет задачу |

## Маппинг фраз пользователя

| Фраза | type | payload | параметры |
|-------|------|---------|-----------|
| "напомни завтра в 9 позвонить маме" | once | reminder | at: завтра 09:00 ISO, text: "Позвонить маме" |
| "через 30 минут напомни про звонок" | once | reminder | at: now+30m ISO, text: "Про звонок" |
| "каждый день в 8 утра напоминай пить воду" | daily | reminder | hour: 8, minute: 0, text: "Пить воду" |
| "каждое утро в 10 присылай дайджест новостей по AI" | daily | task | hour: 10, minute: 0, prompt: "Найди последние новости по AI..." |
| "по пятницам в 18:00 присылай итоги недели" | weekly | task | hour: 18, weekdays: [5], prompt: "Прочитай memory/ за неделю..." |
| "каждый пн и ср в 9 напоминай про тренировку" | weekly | reminder | hour: 9, weekdays: [1,3], text: "Тренировка" |

## Примеры команд

### Создать разовое напоминание
```bash
node ~/.agent/bot/scripts/manage-schedule.js add '{"name":"Позвонить маме","type":"once","at":"2026-05-15T09:00:00+03:00","payload":"reminder","text":"Позвонить маме"}'
```

### Создать ежедневный дайджест
```bash
node ~/.agent/bot/scripts/manage-schedule.js add '{"name":"AI дайджест","type":"daily","hour":10,"minute":0,"payload":"task","prompt":"Найди последние новости по AI за вчера и сегодня. Составь дайджест из 5-7 пунктов."}'
```

### Создать еженедельное напоминание
```bash
node ~/.agent/bot/scripts/manage-schedule.js add '{"name":"Итоги недели","type":"weekly","hour":18,"minute":0,"weekdays":[5],"payload":"task","prompt":"Прочитай memory/ за последнюю неделю, GOALS.md. Составь краткие итоги."}'
```

### Посмотреть все
```bash
node ~/.agent/bot/scripts/manage-schedule.js list
```

### Найти по тексту
```bash
node ~/.agent/bot/scripts/manage-schedule.js search "дайджест"
```

### Отключить / Включить / Изменить / Удалить
```bash
node ~/.agent/bot/scripts/manage-schedule.js disable <id>
node ~/.agent/bot/scripts/manage-schedule.js enable <id>
node ~/.agent/bot/scripts/manage-schedule.js update <id> '{"hour":8,"minute":0}'
node ~/.agent/bot/scripts/manage-schedule.js remove <id>
```

## Правила

1. Определи текст и время из фразы пользователя. Timezone: используй timezone из state.json
2. Для "через N минут" — вычисли текущее время + N минут, передай как ISO datetime
3. После создания — сообщи пользователю: что создано, когда сработает
4. После удаления/отключения — подтверди что именно убрал
5. Если пользователь говорит "мои напоминания" — покажи список (list), с именами и временем
6. Если неясно reminder или task — спроси. Если просто "напомни" — reminder. Если "присылай/делай" — task
7. weekdays: 1=Пн, 2=Вт, 3=Ср, 4=Чт, 5=Пт, 6=Сб, 7=Вс
