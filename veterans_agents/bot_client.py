#!/usr/bin/env python3
"""
Бот ветеранской организации — готовый к передаче клиенту.
Запуск: python bot_client.py
Зависимости: pip install anthropic google-generativeai groq python-telegram-bot
(можно поставить только те библиотеки, чьим провайдером будете пользоваться)
"""
import os
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ── ПРОВАЙДЕРЫ ─────────────────────────────────────────────────────────────────

PROVIDERS = {
    "Claude": {"label": "🟣 Claude (платный)", "model": "claude-haiku-4-5-20251001"},
    "Gemini": {"label": "🔵 Gemini (бесплатно)", "model": "gemini-2.0-flash"},
    "Groq":   {"label": "🟠 Groq (бесплатно)", "model": "llama-3.3-70b-versatile"},
}
DEFAULT_PROVIDER = "Claude"


def call_llm(provider: str, system: str, user_text: str) -> str:
    """Единая точка вызова любой модели."""
    if provider == "Claude":
        from anthropic import Anthropic
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key:
            return "⚠️ Не задан ANTHROPIC_API_KEY. Переключитесь на другого провайдера или добавьте ключ."
        client = Anthropic(api_key=key)
        resp = client.messages.create(
            model=PROVIDERS["Claude"]["model"],
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user_text}],
        )
        return resp.content[0].text

    if provider == "Gemini":
        import google.generativeai as genai
        key = os.getenv("GEMINI_API_KEY", "")
        if not key:
            return "⚠️ Не задан GEMINI_API_KEY. Переключитесь на другого провайдера или добавьте ключ."
        genai.configure(api_key=key)
        model = genai.GenerativeModel(PROVIDERS["Gemini"]["model"], system_instruction=system)
        resp = model.generate_content(user_text)
        return resp.text

    if provider == "Groq":
        from groq import Groq
        key = os.getenv("GROQ_API_KEY", "")
        if not key:
            return "⚠️ Не задан GROQ_API_KEY. Переключитесь на другого провайдера или добавьте ключ."
        client = Groq(api_key=key)
        resp = client.chat.completions.create(
            model=PROVIDERS["Groq"]["model"],
            max_tokens=2048,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_text},
            ],
        )
        return resp.choices[0].message.content

    raise ValueError(f"Неизвестный провайдер: {provider}")


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

user_agent: dict[int, str] = {}      # chat_id -> выбранный агент
user_provider: dict[int, str] = {}   # chat_id -> выбранный провайдер

# ── KEYBOARD ──────────────────────────────────────────────────────────────────

def main_keyboard():
    keys = list(AGENTS.keys()) + ["🔀 Авто (оркестратор)", "⚙️ Провайдер ИИ"]
    rows = [keys[i:i+2] for i in range(0, len(keys), 2)]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def provider_keyboard():
    rows = [[p["label"]] for p in PROVIDERS.values()] + [["⬅️ Назад"]]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def label_to_provider(label: str) -> str | None:
    for key, info in PROVIDERS.items():
        if info["label"] == label:
            return key
    return None

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

    # ── меню провайдера ──
    if text == "⚙️ Провайдер ИИ":
        current = user_provider.get(chat_id, DEFAULT_PROVIDER)
        await update.message.reply_text(
            f"Текущий провайдер: {PROVIDERS[current]['label']}\n\nВыберите другой:",
            reply_markup=provider_keyboard(),
        )
        return

    if text == "⬅️ Назад":
        await update.message.reply_text("Главное меню:", reply_markup=main_keyboard())
        return

    chosen_provider = label_to_provider(text)
    if chosen_provider:
        user_provider[chat_id] = chosen_provider
        await update.message.reply_text(
            f"Готово ✅ Теперь использую: {PROVIDERS[chosen_provider]['label']}",
            reply_markup=main_keyboard(),
        )
        return

    # ── выбор агента из меню ──
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

    # ── определяем агента ──
    provider = user_provider.get(chat_id, DEFAULT_PROVIDER)
    agent_key = user_agent.get(chat_id)

    if not agent_key:
        routed = call_llm(provider, ROUTING_PROMPT, text).strip().strip('"')
        agent_key = routed if routed in AGENTS else "📋 Документы"

    system_prompt = AGENTS[agent_key]["prompt"]
    await update.message.reply_text(f"⚙️ {agent_key} · {PROVIDERS[provider]['label']}…")

    answer = call_llm(provider, system_prompt, text)

    # telegram max 4096 chars
    for chunk in [answer[i:i+4000] for i in range(0, len(answer), 4000)]:
        await update.message.reply_text(chunk, reply_markup=main_keyboard())

# ── ЗАПУСК ────────────────────────────────────────────────────────────────────

def main():
    if not TELEGRAM_TOKEN:
        raise SystemExit("Нет TELEGRAM_BOT_TOKEN")
    if not any(os.getenv(k) for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY")):
        raise SystemExit("Нужен хотя бы один ключ: ANTHROPIC_API_KEY, GEMINI_API_KEY или GROQ_API_KEY")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен. Ctrl+C для остановки.")
    app.run_polling()

if __name__ == "__main__":
    main()
