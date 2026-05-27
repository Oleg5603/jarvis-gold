import os
import json
import asyncio
import logging
from pathlib import Path
from datetime import time as dtime, timezone
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from telegram.constants import ChatAction

from gold_news import build_news_report, build_gold_analysis, build_morning_brief

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CLAUDE_BIN = "/usr/bin/claude"
MEMORY_FILE = Path("/root/telegram-bot/memory.json")
OWNER_FILE = Path("/root/telegram-bot/owner.txt")
MAX_HISTORY = 50

SYSTEM_PROMPT = (
    "Ты Гаврик — личный ИИ-ассистент. Ты помогаешь с текстами, кодом, анализом, "
    "советами, разработкой приложений и сайтов, созданием квизов. "
    "Общайся дружески, на русском, обращайся к хозяину на ты. "
    "Отвечай по делу, но с теплотой."
)


def load_memory() -> dict:
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_memory(mem: dict) -> None:
    MEMORY_FILE.write_text(json.dumps(mem, ensure_ascii=False, indent=2), encoding="utf-8")


def get_owner() -> int | None:
    if OWNER_FILE.exists():
        try:
            return int(OWNER_FILE.read_text().strip())
        except Exception:
            return None
    return None


def set_owner(user_id: int) -> None:
    OWNER_FILE.write_text(str(user_id))


memory: dict = load_memory()


def build_prompt(history: list, current_message: str) -> str:
    lines = [SYSTEM_PROMPT, ""]
    if history:
        lines.append("История нашего разговора:")
        for msg in history:
            speaker = "Хозяин" if msg["role"] == "user" else "Гаврик"
            lines.append(f"{speaker}: {msg['content']}")
        lines.append("")
    lines.append(f"Новое сообщение от хозяина: {current_message}")
    lines.append("\nОтветь как Гаврик:")
    return "\n".join(lines)


async def run_claude(prompt: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        CLAUDE_BIN, "-p", prompt, "--output-format", "text",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return "Ошибка: превышено время ожидания ответа (120 сек)."

    if proc.returncode != 0:
        err = stderr.decode(errors="replace").strip()
        return f"Ошибка: {err}"

    return stdout.decode(errors="replace").strip() or "(пустой ответ)"


async def cmd_news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if get_owner() not in (None, user_id):
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    try:
        report = await build_news_report()
    except Exception as e:
        report = f"Ошибка при получении данных: {e}"
    await update.message.reply_text(report, parse_mode="Markdown")


async def cmd_gold(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if get_owner() not in (None, user_id):
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    try:
        analysis = await build_gold_analysis()
    except Exception as e:
        analysis = f"Ошибка при получении данных: {e}"
    await update.message.reply_text(analysis, parse_mode="Markdown")


async def morning_brief_job(context) -> None:
    owner_id = get_owner()
    if owner_id is None:
        return
    try:
        brief = await build_morning_brief()
    except Exception as e:
        brief = f"⚠️ Ошибка формирования утренней сводки: {e}"
    await context.bot.send_message(chat_id=owner_id, text=brief, parse_mode="Markdown")


async def cmd_test_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if get_owner() not in (None, user_id):
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    try:
        brief = await build_morning_brief()
    except Exception as e:
        brief = f"⚠️ Ошибка: {e}"
    await update.message.reply_text(brief, parse_mode="Markdown")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    owner_id = get_owner()

    if owner_id is None:
        set_owner(user_id)
        await update.message.reply_text(
            "Привет! Я Гаврик — твой личный ИИ-ассистент.\n"
            "Ты стал моим хозяином. Спрашивай что угодно!"
        )
    elif user_id == owner_id:
        await update.message.reply_text("Привет! Я Гаврик, твой помощник. Чем могу помочь?")
    else:
        await update.message.reply_text("Извини, я работаю только с моим хозяином.")


async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    owner_id = get_owner()

    if owner_id is not None and user_id != owner_id:
        return

    key = str(user_id)
    memory[key] = []
    save_memory(memory)
    await update.message.reply_text("История очищена. Начнём с чистого листа!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    owner_id = get_owner()

    if owner_id is None:
        set_owner(user_id)
        owner_id = user_id
    elif user_id != owner_id:
        await update.message.reply_text("Извини, я работаю только с моим хозяином.")
        return

    user_text = update.message.text
    key = str(user_id)

    if key not in memory:
        memory[key] = []

    history = memory[key]

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )

    prompt = build_prompt(history, user_text)
    reply = await run_claude(prompt)

    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": reply})

    if len(history) > MAX_HISTORY:
        memory[key] = history[-MAX_HISTORY:]

    save_memory(memory)

    for i in range(0, len(reply), 4096):
        await update.message.reply_text(reply[i : i + 4096])


async def handle_cyrillic_commands(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает кириллические команды /новости и /золото."""
    text = (update.message.text or "").strip().lower()
    if text.startswith("/новости"):
        await cmd_news(update, context)
    elif text.startswith("/золото"):
        await cmd_gold(update, context)
    else:
        await handle_message(update, context)


def main() -> None:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear_history))
    # Latin aliases for the commands (Telegram only accepts ASCII command names)
    app.add_handler(CommandHandler("novosti", cmd_news))
    app.add_handler(CommandHandler("zoloto", cmd_gold))
    app.add_handler(CommandHandler("news", cmd_news))
    app.add_handler(CommandHandler("gold", cmd_gold))
    app.add_handler(CommandHandler("test_alert", cmd_test_alert))
    # Handles both cyrillic commands and regular messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cyrillic_commands))

    # Утренний алерт каждый день в 08:00 UTC
    app.job_queue.run_daily(
        morning_brief_job,
        time=dtime(hour=9, minute=0, tzinfo=timezone.utc),  # 12:00 МСК
        name="morning_gold_brief",
    )

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
