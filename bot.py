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

_whisper_model = None
_voice_users: set[int] = set()  # users who want voice replies

def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
    return _whisper_model

from gold_news import build_news_report, build_gold_analysis, build_morning_brief
from trading import (
    load_trading_data, save_trading_data,
    build_signal, build_technical_analysis,
    calc_risk_report, add_trade, close_trade,
    format_trade_journal, format_statistics,
    generate_mql4, analyze_backtest, check_news_alerts,
)

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


async def tts_to_ogg(text: str) -> Path | None:
    try:
        import edge_tts
        tmp = Path(f"/tmp/gavrik_tts_{os.getpid()}")
        mp3 = tmp.with_suffix(".mp3")
        ogg = tmp.with_suffix(".ogg")
        communicate = edge_tts.Communicate(text, "ru-RU-DmitryNeural")
        await communicate.save(str(mp3))
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", str(mp3), "-c:a", "libopus", "-b:a", "64k", str(ogg),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        mp3.unlink(missing_ok=True)
        return ogg if ogg.exists() else None
    except Exception as e:
        logging.warning("TTS error: %s", e)
        return None


async def run_claude(prompt: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        CLAUDE_BIN, "-p", "--output-format", "text",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=prompt.encode("utf-8")), timeout=300
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return "Ошибка: превышено время ожидания ответа (300 сек)."

    if proc.returncode != 0:
        err = stderr.decode(errors="replace").strip()
        return f"Ошибка: {err or '(неизвестная ошибка, код ' + str(proc.returncode) + ')'}"

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


async def _process_message(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str) -> None:
    user_id = update.effective_user.id
    key = str(user_id)
    if key not in memory:
        memory[key] = []
    history = memory[key]
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    prompt = build_prompt(history, user_text)
    reply = await run_claude(prompt)
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": reply})
    if len(history) > MAX_HISTORY:
        memory[key] = history[-MAX_HISTORY:]
    save_memory(memory)
    for i in range(0, len(reply), 4096):
        await update.message.reply_text(reply[i : i + 4096])
    if user_id in _voice_users:
        ogg = await tts_to_ogg(reply[:1000])
        if ogg:
            try:
                await update.message.reply_voice(ogg.open("rb"))
            finally:
                ogg.unlink(missing_ok=True)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    owner_id = get_owner()
    if owner_id is None:
        set_owner(user_id)
    elif user_id != owner_id:
        await update.message.reply_text("Извини, я работаю только с моим хозяином.")
        return
    await _process_message(update, context, update.message.text)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    owner_id = get_owner()
    if owner_id is None:
        set_owner(user_id)
    elif user_id != owner_id:
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    voice_path = Path(f"/tmp/gavrik_voice_{user_id}.ogg")
    try:
        voice_file = await update.message.voice.get_file()
        await voice_file.download_to_drive(voice_path)
        model = await asyncio.get_event_loop().run_in_executor(None, _get_whisper)
        segments, _ = await asyncio.get_event_loop().run_in_executor(
            None, lambda: model.transcribe(str(voice_path), language="ru")
        )
        text = " ".join(seg.text for seg in segments).strip()
    except Exception as e:
        await update.message.reply_text(f"Не смог распознать голос: {e}")
        return
    finally:
        voice_path.unlink(missing_ok=True)

    if not text:
        await update.message.reply_text("Не расслышал, попробуй ещё раз.")
        return

    await update.message.reply_text(f"🎤 {text}")
    await _process_message(update, context, text)


async def handle_cyrillic_commands(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает кириллические команды /новости и /золото."""
    text = (update.message.text or "").strip().lower()
    if text.startswith("/новости"):
        await cmd_news(update, context)
    elif text.startswith("/золото"):
        await cmd_gold(update, context)
    else:
        await handle_message(update, context)


# ── Торговые команды XAUUSD ────────────────────────────────────────────────────

def _owner_check(update: Update) -> bool:
    owner_id = get_owner()
    return owner_id is None or update.effective_user.id == owner_id


async def cmd_signal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_check(update):
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    text = await build_signal()
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_analiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_check(update):
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    text = await build_technical_analysis()
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_risk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_check(update):
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Использование: `/risk <лот> <стоп_пунктов>`\nПример: `/risk 0.1 50`",
            parse_mode="Markdown"
        )
        return

    try:
        lot = float(args[0].replace(",", "."))
        stop_pts = float(args[1].replace(",", "."))
    except ValueError:
        await update.message.reply_text("Неверный формат. Пример: `/risk 0.1 50`", parse_mode="Markdown")
        return

    data = load_trading_data()
    balance = data.get("balance")
    if balance is None:
        await update.message.reply_text("Какой у тебя баланс счёта в $? Введи число:")
        context.user_data["awaiting_balance"] = (lot, stop_pts)
        return

    text = calc_risk_report(lot, stop_pts, balance)
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_sdelka(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_check(update):
        return
    args = context.args
    if len(args) < 4:
        await update.message.reply_text(
            "Использование: `/sdelka <buy/sell> <вход> <стоп> <тейк>`\nПример: `/sdelka buy 2350 2330 2390`",
            parse_mode="Markdown"
        )
        return
    try:
        direction = args[0].upper()
        if direction not in ("BUY", "SELL"):
            raise ValueError
        entry = float(args[1].replace(",", "."))
        stop  = float(args[2].replace(",", "."))
        take  = float(args[3].replace(",", "."))
    except ValueError:
        await update.message.reply_text("Неверный формат. Пример: `/sdelka buy 2350 2330 2390`", parse_mode="Markdown")
        return

    data = load_trading_data()
    trade = add_trade(data, direction, entry, stop, take)
    save_trading_data(data)
    d_emoji = "⬆️" if direction == "BUY" else "⬇️"
    await update.message.reply_text(
        f"✅ Сделка #{trade['id']} записана\n"
        f"{d_emoji} *{direction}* | Вход: ${entry:,.1f} | SL: ${stop:,.1f} | TP: ${take:,.1f}",
        parse_mode="Markdown"
    )


async def cmd_jurnal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_check(update):
        return
    data = load_trading_data()
    text = format_trade_journal(data)
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_statistika(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_check(update):
        return
    data = load_trading_data()
    text = format_statistics(data)
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_zakryt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_check(update):
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Использование: `/zakryt <номер> <пунктов>`\nПример: `/zakryt 1 +45`",
            parse_mode="Markdown"
        )
        return
    try:
        trade_num   = int(args[0])
        result_pts  = float(args[1].replace(",", ".").replace("+", ""))
    except ValueError:
        await update.message.reply_text("Неверный формат. Пример: `/zakryt 1 45`", parse_mode="Markdown")
        return

    data = load_trading_data()
    trade = close_trade(data, trade_num, result_pts)
    if trade is None:
        await update.message.reply_text(f"Сделка #{trade_num} не найдена среди открытых.")
        return
    save_trading_data(data)
    res_emoji = "✅" if result_pts > 0 else "❌"
    sign = "+" if result_pts > 0 else ""
    await update.message.reply_text(
        f"{res_emoji} Сделка #{trade['id']} закрыта: *{sign}{result_pts:.0f} пп*",
        parse_mode="Markdown"
    )


async def cmd_kod(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_check(update):
        return
    description = " ".join(context.args).strip()
    if not description:
        await update.message.reply_text(
            "Использование: `/kod <описание стратегии>`\nПример: `/kod пересечение MA 8 и 21 на H1`",
            parse_mode="Markdown"
        )
        return
    code = generate_mql4(description)
    await update.message.reply_text(code, parse_mode="Markdown")


async def cmd_baktest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_check(update):
        return
    results = " ".join(context.args).strip()
    if not results:
        await update.message.reply_text(
            "Использование: `/baktest <результаты>`\nПример: `/baktest winrate 55%, drawdown 12%, 80 сделок`",
            parse_mode="Markdown"
        )
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    text = await analyze_backtest(results)
    await update.message.reply_text(text, parse_mode="Markdown")


async def news_alert_job(context) -> None:
    owner_id = get_owner()
    if owner_id is None:
        return
    await check_news_alerts(context.bot, owner_id)


async def handle_balance_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ловит ответ с балансом если бот ждал его."""
    pending = context.user_data.pop("awaiting_balance", None)
    if pending is None:
        await handle_message(update, context)
        return
    try:
        balance = float(update.message.text.replace(",", ".").replace("$", "").strip())
    except ValueError:
        await update.message.reply_text("Не понял сумму, введи просто число, например: `5000`", parse_mode="Markdown")
        context.user_data["awaiting_balance"] = pending
        return
    data = load_trading_data()
    data["balance"] = balance
    save_trading_data(data)
    lot, stop_pts = pending
    text = calc_risk_report(lot, stop_pts, balance)
    await update.message.reply_text(f"✅ Баланс ${balance:,.0f} сохранён.\n\n{text}", parse_mode="Markdown")


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
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
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
