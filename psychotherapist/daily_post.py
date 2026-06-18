"""Ежедневный автопостинг в ВК — SvetBot_DailyPost, 12:00."""
import os
import json
import asyncio
import logging
import subprocess
import urllib.parse
from datetime import date
from pathlib import Path
from io import BytesIO
import aiohttp
from dotenv import load_dotenv

load_dotenv("/root/telegram-bot/.env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("/tmp/daily_post.log"),
        logging.StreamHandler(),
    ],
)

VK_TOKEN = os.environ["MISEMIA_VK_TOKEN"]
VK_GROUP_SCREEN = "misemia"

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

TOPICS = [
    "случай из практики — клиент не мог выразить злость, держал всё в себе",
    "тревога без причины — почему тело тревожится, когда голова говорит «всё хорошо»",
    "отношения на расстоянии — как сохранить близость когда партнёры далеко",
    "синдром хорошей девочки — почему так тяжело отказать и сказать «нет»",
    "детские травмы — как они проявляются во взрослых отношениях",
    "ссоры в паре — зачем мы ругаемся и что стоит за конфликтом",
    "выгорание — когда устала быть сильной",
    "страх одиночества — почему мы остаёмся в токсичных отношениях",
    "самооценка — почему мы обесцениваем себя и как это остановить",
    "границы в семье — как объяснить родственникам что можно а что нет",
    "ревность — это страх или недоверие?",
    "прощение — можно ли простить и зачем это нужно именно вам",
    "манипуляции — как распознать и не поддаться",
    "одиночество в браке — почему рядом человек а ощущение пустоты",
]

STATE_FILE = Path("/tmp/daily_post_state.json")


def get_today_topic() -> str:
    state = {}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
        except Exception:
            pass

    last_index = state.get("last_index", -1)
    next_index = (last_index + 1) % len(TOPICS)

    state["last_index"] = next_index
    state["last_date"] = str(date.today())
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False))

    return TOPICS[next_index]


def generate_text(topic: str) -> str:
    prompt = f"{STYLE_PROMPT}\n\nТема поста: {topic}"
    result = subprocess.run(
        ["/usr/bin/claude", "-p", "--output-format", "text"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI error: {result.stderr[:300]}")
    return result.stdout.strip()


def get_photo_url(topic: str) -> str:
    prompt = (
        f"professional psychology therapy family counseling, {topic}, "
        "calm serene warm atmosphere, soft pastel colors, no text, no watermark"
    )
    seed = abs(hash(topic)) % 99999
    return f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1200&height=630&nologo=true&seed={seed}"


async def vk_api(session: aiohttp.ClientSession, method: str, params: dict) -> dict:
    url = f"https://api.vk.com/method/{method}"
    params["access_token"] = VK_TOKEN
    params["v"] = "5.131"
    async with session.post(url, data=params) as resp:
        return await resp.json()


async def resolve_group_id(session: aiohttp.ClientSession) -> int:
    result = await vk_api(session, "groups.getById", {"group_ids": VK_GROUP_SCREEN, "fields": "id"})
    return result["response"][0]["id"]


async def upload_photo(session: aiohttp.ClientSession, image_bytes: bytes, group_id: int) -> str | None:
    try:
        result = await vk_api(session, "photos.getWallUploadServer", {"group_id": group_id})
        upload_url = result["response"]["upload_url"]
        data = aiohttp.FormData()
        data.add_field("photo", BytesIO(image_bytes), filename="photo.jpg", content_type="image/jpeg")
        async with session.post(upload_url, data=data) as resp:
            upload_result = await resp.json()
        save_result = await vk_api(session, "photos.saveWallPhoto", {
            "group_id": group_id,
            "photo": upload_result["photo"],
            "server": upload_result["server"],
            "hash": upload_result["hash"],
        })
        photo = save_result["response"][0]
        return f"photo{photo['owner_id']}_{photo['id']}"
    except Exception as e:
        logging.warning(f"Ошибка загрузки фото: {e}")
        return None


async def download_image(session: aiohttp.ClientSession, url: str) -> bytes | None:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                return await resp.read()
    except Exception as e:
        logging.warning(f"Ошибка скачивания фото: {e}")
    return None


async def publish(text: str, attachment: str | None, group_id: int, session: aiohttp.ClientSession) -> str:
    params = {
        "owner_id": f"-{group_id}",
        "from_group": 1,
        "message": text,
    }
    if attachment:
        params["attachments"] = attachment
    result = await vk_api(session, "wall.post", params)
    post_id = result["response"]["post_id"]
    return f"https://vk.com/misemia?w=wall-{group_id}_{post_id}"


async def main():
    topic = get_today_topic()
    logging.info(f"Тема: {topic}")

    logging.info("Генерирую текст через Claude...")
    text = generate_text(topic)
    logging.info(f"Текст готов ({len(text)} символов)")

    photo_url = get_photo_url(topic)

    async with aiohttp.ClientSession() as session:
        group_id = await resolve_group_id(session)
        logging.info(f"Group ID: {group_id}")

        image_bytes = await download_image(session, photo_url)
        attachment = None
        if image_bytes:
            attachment = await upload_photo(session, image_bytes, group_id)
            logging.info(f"Фото загружено: {attachment}")
        else:
            logging.warning("Фото не скачалось — публикую без картинки")

        url = await publish(text, attachment, group_id, session)
        logging.info(f"Опубликовано: {url}")
        print(url)


if __name__ == "__main__":
    asyncio.run(main())
