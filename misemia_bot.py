"""Telegram-бот для управления ВК страницей психотерапевта misemia."""
import os
import json
import random
import asyncio
import logging
from io import BytesIO
from pathlib import Path
from datetime import time as dtime, timezone
import aiohttp
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, MessageHandler, CommandHandler, CallbackQueryHandler,
    filters, ContextTypes,
)
from telegram.constants import ChatAction

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

MISEMIA_BOT_TOKEN = os.environ["MISEMIA_BOT_TOKEN"]
VK_TOKEN = os.environ["MISEMIA_VK_TOKEN"]
VK_GROUP_SCREEN = "misemia"
CLAUDE_BIN = "/usr/bin/claude"

VK_GROUP_ID: int | None = None

OWNER_FILE = Path("/root/telegram-bot/misemia_owner.txt")
DRAFT_FILE = Path("/root/telegram-bot/misemia_draft.json")
REPLIED_FILE = Path("/root/telegram-bot/misemia_replied.json")

STYLE_PROMPT = """Ты копирайтер психотерапевта, ведёшь страницу ВКонтакте vk.com/misemia.
Пишешь посты в двух форматах — чередуй их:

ФОРМАТ 1 — ПРОВОКАЦИОННЫЙ:
Начни с острого вопроса или вызова читателю. Покажи, что проблема глубже чем кажется.
Задай 3-4 вопроса для саморефлексии (Как часто вы...? Готовы ли вы...? Что если...?)
Финал: "Готовы ли вы изменить...?" — обязательный приём.
Тон: жёсткий, но с заботой.

ФОРМАТ 2 — ПРАКТИЧЕСКИЙ:
Конкретная тема + проблема в семье/отношениях.
5-7 советов нумерованным списком. Каждый совет — 2-3 предложения.
Тон: тёплый, поддерживающий. Финал: вопрос к читателю или призыв.

ЭМОДЗИ — обязательно используй смайлики по всему тексту:
- Начало ключевых абзацев: 💔 😔 🤯 💡 🌱 🎯 💖 🙏 ✨ 🔑 🧠
- В советах и списках: ✅ 👂 🧘‍♀️ 💪 🤔 💭 🌍 🌸 🌿 🫂
- В вопросах к читателю: 🤷‍♀️ 😬 😰 💫 🙄
- Эмоциональные акценты: 😣 🥺 😤 🌟 🎉 🙌
Каждый абзац должен содержать 1-2 смайлика. Смайлики ставь ВНУТРИ текста, не только в конце.

ВСЕГДА в самом конце поста: "Можете написать мне. +79028355176 (мессенджер МАКС)"

Пиши на русском, объём 300-600 слов. Только текст поста, без пояснений и комментариев."""


def get_photo_url(topic: str) -> str:
    import urllib.parse
    prompt = (
        f"professional psychology therapy family counseling, {topic}, "
        "calm serene warm atmosphere, soft pastel colors, no text, no watermark"
    )
    seed = abs(hash(topic)) % 99999
    return f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1200&height=630&nologo=true&seed={seed}"

COMMENT_PROMPT = """Ты помощник психотерапевта на странице ВКонтакте vk.com/misemia.
Отвечай на комментарий под постом тепло, профессионально, поддерживающе.
Объём: 2-4 предложения. Не давай медицинских советов.
Если вопрос о записи или консультации — направь: +79028355176 (мессенджер МАКС).
Только текст ответа, без пояснений."""


def get_owner() -> int | None:
    if OWNER_FILE.exists():
        try:
            return int(OWNER_FILE.read_text().strip())
        except Exception:
            return None
    return None


def set_owner(user_id: int) -> None:
    OWNER_FILE.write_text(str(user_id))


async def download_image(url: str) -> bytes | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60), allow_redirects=True) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    if len(data) > 1000:  # проверка что это реальное изображение
                        return data
                    logging.warning(f"Слишком маленький ответ от {url}: {len(data)} байт")
    except Exception as e:
        logging.warning(f"Не удалось скачать изображение: {e}")
    return None


async def upload_photo_to_vk(image_bytes: bytes, group_id: int) -> str | None:
    """Загружает фото в ВК и возвращает строку вложения типа 'photo-12345_67890'."""
    try:
        result = await vk_api("photos.getWallUploadServer", {"group_id": group_id})
        if "error" in result:
            logging.error(f"getWallUploadServer: {result['error']}")
            return None
        upload_url = result["response"]["upload_url"]

        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field("photo", image_bytes, filename="photo.jpg", content_type="image/jpeg")
            async with session.post(upload_url, data=data) as resp:
                upload_result = await resp.json(content_type=None)

        save_result = await vk_api("photos.saveWallPhoto", {
            "group_id": group_id,
            "server": upload_result["server"],
            "photo": upload_result["photo"],
            "hash": upload_result["hash"],
        })
        if "error" in save_result:
            logging.error(f"saveWallPhoto: {save_result['error']}")
            return None

        photo = save_result["response"][0]
        return f"photo{photo['owner_id']}_{photo['id']}"
    except Exception as e:
        logging.error(f"Ошибка загрузки фото в ВК: {e}")
        return None


def save_draft(text: str, topic: str = "", photo_url: str = "") -> None:
    DRAFT_FILE.write_text(
        json.dumps({"text": text, "topic": topic, "photo_url": photo_url}, ensure_ascii=False),
        encoding="utf-8",
    )


def load_draft() -> dict:
    if DRAFT_FILE.exists():
        try:
            return json.loads(DRAFT_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def load_replied() -> set:
    if REPLIED_FILE.exists():
        try:
            return set(json.loads(REPLIED_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return set()


def save_replied(ids: set) -> None:
    # Keep only last 2000 IDs to avoid unbounded growth
    ids_list = list(ids)[-2000:]
    REPLIED_FILE.write_text(json.dumps(ids_list, ensure_ascii=False), encoding="utf-8")


async def run_claude(prompt: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        CLAUDE_BIN, "-p", "--output-format", "text",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=prompt.encode("utf-8")), timeout=120
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return "Ошибка: превышено время ожидания."
    if proc.returncode != 0:
        err = stderr.decode(errors="replace").strip()
        return f"Ошибка: {err or 'неизвестная'}"
    return stdout.decode(errors="replace").strip() or "(пустой ответ)"


async def vk_api(method: str, params: dict) -> dict:
    params["access_token"] = VK_TOKEN
    params["v"] = "5.199"
    url = f"https://api.vk.com/method/{method}"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=params) as resp:
            return await resp.json()


async def resolve_group_id() -> int:
    result = await vk_api("groups.getById", {"group_ids": VK_GROUP_SCREEN, "fields": "id"})
    if "error" in result:
        raise RuntimeError(result["error"].get("error_msg", "VK API error"))
    groups = result.get("response", {}).get("groups", [])
    if not groups:
        raise RuntimeError("Group not found")
    return groups[0]["id"]


async def publish_to_vk(text: str, attachment: str | None = None) -> str:
    if VK_GROUP_ID is None:
        return "Ошибка: ID группы не определён"
    params = {
        "owner_id": f"-{VK_GROUP_ID}",
        "from_group": 1,
        "message": text,
    }
    if attachment:
        params["attachments"] = attachment
    result = await vk_api("wall.post", params)
    if "error" in result:
        return f"Ошибка VK: {result['error'].get('error_msg', 'неизвестная')}"
    post_id = result["response"]["post_id"]
    return f"https://vk.com/misemia?w=wall-{VK_GROUP_ID}_{post_id}"


def post_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Опубликовать в ВК", callback_data="publish"),
        InlineKeyboardButton("🔄 Переписать", callback_data="rewrite"),
    ]])


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if get_owner() is None:
        set_owner(user_id)
    await update.message.reply_text(
        "Привет! Я помогаю вести ВК страницу misemia.\n\n"
        "Команды:\n"
        "/post [тема] — написать пост\n"
        "/comments — проверить и ответить на комментарии ВК\n\n"
        "Или просто напиши тему — я напишу пост, ты утвердишь."
    )


async def generate_post(topic: str) -> str:
    prompt = f"{STYLE_PROMPT}\n\nТема поста: {topic}"
    return await run_claude(prompt)


async def send_draft(message, text: str, photo_url: str = "") -> None:
    if photo_url:
        try:
            image_bytes = await download_image(photo_url)
            if image_bytes:
                await message.reply_photo(photo=BytesIO(image_bytes), caption="📸 Фото для поста")
            else:
                logging.warning("Фото не скачалось — отправляю пост без превью изображения")
        except Exception as e:
            logging.warning(f"Не удалось отправить фото превью: {e}")
    preview = text[:3800] if len(text) > 3800 else text
    await message.reply_text(
        f"📝 *Черновик поста:*\n\n{preview}",
        parse_mode="Markdown",
        reply_markup=post_keyboard(),
    )


async def cmd_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    owner_id = get_owner()
    if owner_id and user_id != owner_id:
        return
    topic = " ".join(context.args) if context.args else "актуальная психологическая тема для семьи"
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    text = await generate_post(topic)
    photo_url = get_photo_url(topic)
    save_draft(text, topic, photo_url)
    await send_draft(update.message, text, photo_url)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    owner_id = get_owner()
    if owner_id is None:
        set_owner(user_id)
    elif user_id != owner_id:
        return
    topic = update.message.text.strip()
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    text = await generate_post(topic)
    photo_url = get_photo_url(topic)
    save_draft(text, topic, photo_url)
    await send_draft(update.message, text, photo_url)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "publish":
        draft = load_draft()
        if not draft:
            await query.edit_message_text("Нет черновика для публикации.")
            return
        await query.edit_message_text("⏳ Загружаю фото и публикую в ВК...")

        attachment = None
        photo_url = draft.get("photo_url", "")
        if photo_url and VK_GROUP_ID:
            image_bytes = await download_image(photo_url)
            if image_bytes:
                attachment = await upload_photo_to_vk(image_bytes, VK_GROUP_ID)
                if not attachment:
                    logging.warning("Фото не загрузилось в ВК, публикую без фото")

        url = await publish_to_vk(draft["text"], attachment)
        if url.startswith("http"):
            photo_note = " с фото 📸" if attachment else ""
            await query.edit_message_text(f"✅ Опубликовано{photo_note}!\n{url}")
        else:
            await query.edit_message_text(f"❌ {url}")

    elif query.data == "rewrite":
        draft = load_draft()
        topic = draft.get("topic", "актуальная психологическая тема")
        await query.edit_message_text("🔄 Переписываю пост...")
        text = await generate_post(topic)
        photo_url = get_photo_url(topic)
        save_draft(text, topic, photo_url)
        await send_draft(query.message, text, photo_url)


async def process_comments(group_id: int) -> int:
    """Проверяет последние 5 постов и отвечает на новые комментарии."""
    replied_ids = load_replied()
    new_replied = set()

    result = await vk_api("wall.get", {
        "owner_id": f"-{group_id}",
        "count": 5,
        "filter": "owner",
    })
    if "error" in result:
        logging.error(f"VK wall.get error: {result['error']}")
        return 0

    posts = result.get("response", {}).get("items", [])
    replied_count = 0

    for post in posts:
        post_id = post["id"]
        comments_result = await vk_api("wall.getComments", {
            "owner_id": f"-{group_id}",
            "post_id": post_id,
            "count": 20,
            "sort": "desc",
        })
        comments = comments_result.get("response", {}).get("items", [])

        for comment in comments:
            comment_id = comment["id"]
            # Skip already replied or comments from the group itself
            if comment_id in replied_ids:
                continue
            if comment.get("from_id") == -group_id:
                new_replied.add(comment_id)
                continue
            comment_text = comment.get("text", "").strip()
            if not comment_text:
                new_replied.add(comment_id)
                continue

            prompt = f"{COMMENT_PROMPT}\n\nКомментарий: {comment_text}"
            reply_text = await run_claude(prompt)

            reply_result = await vk_api("wall.createComment", {
                "owner_id": f"-{group_id}",
                "post_id": post_id,
                "reply_to_comment": comment_id,
                "message": reply_text,
                "from_group": 1,
            })
            if "error" not in reply_result:
                replied_count += 1
                new_replied.add(comment_id)
                logging.info(f"Replied to comment {comment_id}")
            else:
                logging.warning(f"Failed to reply to {comment_id}: {reply_result['error']}")

    save_replied(replied_ids | new_replied)
    return replied_count


async def cmd_comments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    owner_id = get_owner()
    if owner_id and user_id != owner_id:
        return
    if VK_GROUP_ID is None:
        await update.message.reply_text("Ошибка: ID группы не определён.")
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    await update.message.reply_text("🔍 Проверяю комментарии в ВК...")
    count = await process_comments(VK_GROUP_ID)
    if count > 0:
        await update.message.reply_text(f"✅ Ответил на {count} новых комментариев.")
    else:
        await update.message.reply_text("Новых комментариев без ответа не найдено.")


async def auto_comments_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    owner_id = get_owner()
    if owner_id is None or VK_GROUP_ID is None:
        return
    count = await process_comments(VK_GROUP_ID)
    if count > 0:
        await context.bot.send_message(
            chat_id=owner_id,
            text=f"🤖 Автоответ: ответил на {count} новых комментариев в ВК.",
        )


async def post_init(app: Application) -> None:
    global VK_GROUP_ID
    try:
        VK_GROUP_ID = await resolve_group_id()
        logging.info(f"VK group resolved: {VK_GROUP_SCREEN} → ID {VK_GROUP_ID}")
    except Exception as e:
        logging.error(f"Не удалось определить ID группы ВК: {e}")


def main() -> None:
    app = (
        Application.builder()
        .token(MISEMIA_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("post", cmd_post))
    app.add_handler(CommandHandler("comments", cmd_comments))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Автопроверка комментариев каждый час
    app.job_queue.run_repeating(auto_comments_job, interval=3600, first=60)

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
