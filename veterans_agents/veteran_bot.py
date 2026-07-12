#!/usr/bin/env python3
"""
Бот ветеранской организации — готовый к передаче клиенту.
Запуск: python bot_client.py
Зависимости: pip install openai python-telegram-bot
Один ключ OPENROUTER_API_KEY — доступ ко всем моделям ниже.
"""
import os
import logging
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Пусто = доступ открыт всем (по умолчанию, для публичного клиентского бота).
# Если задать через запятую в .env (ALLOWED_USER_IDS=123,456) — доступ будет только у них.
_raw_allowed_ids = os.getenv("ALLOWED_USER_IDS", "")
ALLOWED_USER_IDS: set[int] = {
    int(x.strip()) for x in _raw_allowed_ids.split(",") if x.strip().isdigit()
}

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)

# ── МОДЕЛИ (через OpenRouter, один ключ на всё) ─────────────────────────────────

MODELS = {
    "Llama":  {"label": "🟢 Llama 3.3 (бесплатно)", "model": "meta-llama/llama-3.3-70b-instruct:free"},
    "Claude": {"label": "🟣 Claude Haiku (платно)", "model": "anthropic/claude-haiku-4.5"},
    "Gemini": {"label": "🔵 Gemini Flash (платно)", "model": "google/gemini-2.0-flash-001"},
}
DEFAULT_MODEL = "Llama"


def call_llm(model_key: str, system: str, user_text: str) -> str:
    if not OPENROUTER_API_KEY:
        return "⚠️ Не задан OPENROUTER_API_KEY. Получите ключ на openrouter.ai/keys."
    resp = client.chat.completions.create(
        model=MODELS[model_key]["model"],
        max_tokens=2048,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
    )
    return resp.choices[0].message.content


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
user_model: dict[int, str] = {}   # chat_id -> выбранная модель

# ── KEYBOARD ──────────────────────────────────────────────────────────────────

def main_keyboard():
    keys = list(AGENTS.keys()) + ["🔀 Авто (оркестратор)", "⚙️ Модель ИИ"]
    rows = [keys[i:i+2] for i in range(0, len(keys), 2)]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def model_keyboard():
    rows = [[m["label"]] for m in MODELS.values()] + [["⬅️ Назад"]]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def label_to_model(label: str) -> str | None:
    for key, info in MODELS.items():
        if info["label"] == label:
            return key
    return None

# ── ХЭНДЛЕРЫ ──────────────────────────────────────────────────────────────────

def _is_allowed(chat_id: int) -> bool:
    return not ALLOWED_USER_IDS or chat_id in ALLOWED_USER_IDS


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update.effective_chat.id):
        await update.message.reply_text("⛔ Доступ к этому боту ограничен.")
        return
    await update.message.reply_text(
        "👋 Добро пожаловать в систему помощи ветеранской организации!\n\n"
        "Выберите раздел или напишите вопрос — я сам определю нужного специалиста.\n",
        reply_markup=main_keyboard(),
    )

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id

    if not _is_allowed(chat_id):
        await update.message.reply_text("⛔ Доступ к этому боту ограничен.")
        return

    # ── меню модели ──
    if text == "⚙️ Модель ИИ":
        current = user_model.get(chat_id, DEFAULT_MODEL)
        await update.message.reply_text(
            f"Текущая модель: {MODELS[current]['label']}\n\nВыберите другую:",
            reply_markup=model_keyboard(),
        )
        return

    if text == "⬅️ Назад":
        await update.message.reply_text("Главное меню:", reply_markup=main_keyboard())
        return

    chosen_model = label_to_model(text)
    if chosen_model:
        user_model[chat_id] = chosen_model
        await update.message.reply_text(
            f"Готово ✅ Теперь использую: {MODELS[chosen_model]['label']}",
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
    model_key = user_model.get(chat_id, DEFAULT_MODEL)
    agent_key = user_agent.get(chat_id)

    if not agent_key:
        routed = call_llm(model_key, ROUTING_PROMPT, text).strip().strip('"')
        agent_key = routed if routed in AGENTS else "📋 Документы"

    system_prompt = AGENTS[agent_key]["prompt"]
    await update.message.reply_text(f"⚙️ {agent_key} · {MODELS[model_key]['label']}…")

    answer = call_llm(model_key, system_prompt, text)

    # telegram max 4096 chars
    for chunk in [answer[i:i+4000] for i in range(0, len(answer), 4000)]:
        await update.message.reply_text(chunk, reply_markup=main_keyboard())

# ── ЗАПУСК ────────────────────────────────────────────────────────────────────

def main():
    if not TELEGRAM_TOKEN:
        raise SystemExit("Нет TELEGRAM_BOT_TOKEN")
    if not OPENROUTER_API_KEY:
        raise SystemExit("Нет OPENROUTER_API_KEY (получить на openrouter.ai/keys)")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен. Ctrl+C для остановки.")
    app.run_polling()

if __name__ == "__main__":
    main()
