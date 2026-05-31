"""
Monitor Agent — сканирует публичные Telegram-каналы по тегам #отношения #брак #психология.
Требует: Telethon + TELEGRAM_API_ID + TELEGRAM_API_HASH в .env
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
INPUT_FILE = ROOT / "leads_pipeline" / "raw_keywords.json"
OUTPUT_FILE = ROOT / "leads_pipeline" / "raw_leads.json"

TARGET_CHANNELS = [
    "psychologytoday_ru",
    "semya_i_otnosheniya",
    "psy_online_help",
    "razvod_i_tochka",
    "otnosheniya_psy",
]

SEARCH_TAGS = ["#отношения", "#брак", "#развод", "#измена", "#психология", "#семья"]


def load_keywords() -> list[str]:
    if INPUT_FILE.exists():
        data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
        return data.get("keywords", []) + data.get("high_intent_phrases", [])
    return ["психолог", "развод", "измена", "кризис", "помогите"]


def is_help_seeking(text: str, keywords: list[str]) -> bool:
    text_lower = text.lower()
    help_markers = ["помогите", "что делать", "посоветуйте", "как быть", "не знаю куда", "ищу помощь", "нужен совет"]
    has_keyword = any(kw.lower() in text_lower for kw in keywords)
    has_help = any(m in text_lower for m in help_markers)
    return has_keyword and has_help


async def run():
    print("[monitor] Старт Monitor Agent", flush=True)

    api_id = os.environ.get("TELEGRAM_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH")

    if not api_id or not api_hash:
        print("[monitor] TELEGRAM_API_ID/HASH не настроены — пропуск Monitor Agent", flush=True)
        print("[monitor] Получить на https://my.telegram.org → API development tools", flush=True)
        sys.exit(0)

    try:
        from telethon import TelegramClient
        from telethon.tl.types import Channel
    except ImportError:
        print("[monitor] telethon не установлен: pip install telethon", flush=True)
        sys.exit(0)

    keywords = load_keywords()
    week_ago = datetime.now() - timedelta(days=7)
    leads: list[dict] = []

    session_file = ROOT / "leads_pipeline" / "tg_monitor.session"
    client = TelegramClient(str(session_file), int(api_id), api_hash)

    async with client:
        for channel_name in TARGET_CHANNELS:
            try:
                entity = await client.get_entity(channel_name)
                print(f"[monitor] Сканируем @{channel_name}...", flush=True)

                async for msg in client.iter_messages(entity, limit=200):
                    if not msg.text or not msg.date:
                        continue
                    if msg.date.replace(tzinfo=None) < week_ago:
                        break

                    if is_help_seeking(msg.text, keywords):
                        sender = await msg.get_sender()
                        username = getattr(sender, "username", None) or str(getattr(sender, "id", "unknown"))
                        leads.append({
                            "url": f"https://t.me/{channel_name}/{msg.id}",
                            "author": username,
                            "quote": msg.text[:300],
                            "source": f"telegram/@{channel_name}",
                            "intentScore": 70,
                            "createdAt": msg.date.isoformat(),
                            "disclaimer": "Лид найден в открытом публичном Telegram-канале",
                        })

                print(f"[monitor] @{channel_name}: найдено {len(leads)} лидов", flush=True)
            except Exception as e:
                print(f"[monitor] Ошибка @{channel_name}: {e}", flush=True)

    # Мердж с существующим файлом
    existing = []
    if OUTPUT_FILE.exists():
        existing = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))

    seen = {l.get("url") for l in existing}
    merged = existing + [l for l in leads if l.get("url") not in seen]
    OUTPUT_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[monitor] Готово: {len(leads)} новых лидов → {OUTPUT_FILE}", flush=True)


if __name__ == "__main__":
    asyncio.run(run())
