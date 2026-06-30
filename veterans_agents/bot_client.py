#!/usr/bin/env python3
"""
Бот ветеранской организации — готовый к передаче клиенту.
Запуск: python bot_client.py
Зависимости: pip install anthropic python-telegram-bot
"""
import os
import asyncio
import logging
from anthropic import Anthropic
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
MODEL = "claude-haiku-4-5-20251001"

# ── ПРОМПТЫ АГЕНТОВ ────────────────────────────────────────────────────────────

AGENTS = {
    "📋 Документы": {
        "desc": "делопроизводство, протоколы, отчётность, планирование",
        "prompt": """Ты — специалист по административной работе ветеранской организации.
Помогаешь составлять: протоколы заседаний, отчёты, планы работы, приказы, письма.
Пиши готовые документы с реквизитами. Незаполненные поля — в [квадратных скобках].
Стиль — официально-деловой, конкретный.""",
    },
    "🤝 Соцпомощь": {
        "desc": "льготы, субсидии, волонтёры, взаимодействие с соцзащитой",
        "prompt": """Ты — специалист по социальной поддержке ветеранов.
Помогаешь: оформить льготы/субсидии/путёвки, найти волонтёрскую помощь,
составить заявку на гуманитарную помощь, разобраться с правами ветерана.
Давай пошаговые инструкции с конкретными документами.""",
    },
    "👥 Члены": {
        "desc": "приём, база данных, учёт, первички",
        "prompt": """Ты — специалист по учёту членов ветеранской организации.
Помогаешь: оформить приём нового члена, обновить базу данных,
вести статистику, работать с первичными организациями.
Предлагай готовые формы и таблицы.""",
    },
    "🎖️ Мероприятия": {
        "desc": "памятные даты, патриотическая работа, захоронения",
        "prompt": """Ты — организатор мероприятий ветеранской организации.
Помогаешь: спланировать мероприятие к памятной дате (9 мая, 23 февраля, 15 февраля),
подготовить Урок мужества для школьников, организовать уход за захоронениями.
Давай конкретные сценарии, таблицы задач, сроки.""",
    },
    "📢 Инфо и СМИ": {
        "desc": "посты ВКонтакте, пресс-релизы, рассылки",
        "prompt": """Ты — пресс-секретарь ветеранской организации.
Помогаешь: написать пост для ВКонтакте/Одноклассников, составить пресс-релиз,
подготовить рассылку членам организации, написать поздравление.
Пиши просто и понятно, аудитория — ветераны 60–85 лет.""",
    },
}

ROUTING_PROMPT = f"""Определи, к какому разделу относится запрос пользователя.
Разделы: {', '.join(AGENTS.keys())}
Ответь ТОЛЬКО именем раздела — один из: {', '.join(f'"{k}"' for k in AGENTS)}
Без пояснений."""

# ── СОСТОЯНИЕ ─────────────────────────────────────────────────────────────────

user_agent: dict[int, str] = {}   # chat_id -> выбранный агент

# ── KEYBOARD ──────────────────────────────────────────────────────────────────

def main_keyboard():
    keys = list(AGENTS.keys()) + ["🔀 Авто (оркестратор)"]
    rows = [keys[i:i+2] for i in range(0, len(keys), 2)]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

# ── ХЭНДЛЕРЫ ──────────────────────────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Добро пожаловать в систему помощи ветеранской организации!\n\n"
        "Выберите раздел или напишите вопрос — я сам определю нужного специалиста.\n",
        reply_markup=main_keyboard(),
    )

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id
    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    # выбор агента из меню
    if text in AGENTS:
        user_agent[chat_id] = text
        await update.message.reply_text(
            f"{text}\n{AGENTS[text]['desc'].capitalize()}.\n\nЗадайте вопрос:"
        )
        return

    if text == "🔀 Авто (оркестратор)":
        user_agent.pop(chat_id, None)
        await update.message.reply_text("Режим авто: напишите задачу, определю агента сам.")
        return

    # определяем агента
    agent_key = user_agent.get(chat_id)

    if not agent_key:
        # авто-маршрутизация
        route_resp = client.messages.create(
            model=MODEL,
            max_tokens=64,
            system=ROUTING_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        agent_key = route_resp.content[0].text.strip().strip('"')
        if agent_key not in AGENTS:
            agent_key = "📋 Документы"

    system_prompt = AGENTS[agent_key]["prompt"]
    await update.message.reply_text(f"⚙️ {agent_key}…")

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": text}],
    )
    answer = response.content[0].text

    # telegram max 4096 chars
    for chunk in [answer[i:i+4000] for i in range(0, len(answer), 4000)]:
        await update.message.reply_text(chunk, reply_markup=main_keyboard())

# ── ЗАПУСК ────────────────────────────────────────────────────────────────────

def main():
    if not ANTHROPIC_API_KEY:
        raise SystemExit("Нет ANTHROPIC_API_KEY")
    if not TELEGRAM_TOKEN:
        raise SystemExit("Нет TELEGRAM_BOT_TOKEN")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен. Ctrl+C для остановки.")
    app.run_polling()

if __name__ == "__main__":
    main()
