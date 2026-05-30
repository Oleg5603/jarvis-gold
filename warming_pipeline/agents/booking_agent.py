"""
Booking Agent — финальный шаг прогрева: приглашение записаться через @LanaS777Bot.
Горячие лиды автоматически отправляются в бота и напрямую Лане.
Вход: warming_pipeline/sequences.json → Выход: warming_pipeline/booked_leads.json
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import anthropic
import urllib.request
import urllib.parse

if not os.environ.get("ANTHROPIC_API_KEY"):
    env_file = Path(__file__).parent.parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

_api_key = os.environ.get("ANTHROPIC_API_KEY")
_client = anthropic.Anthropic(api_key=_api_key) if _api_key else None

ROOT = Path(__file__).parent.parent.parent
INPUT_FILE = ROOT / "warming_pipeline" / "sequences.json"
OUTPUT_FILE = ROOT / "warming_pipeline" / "booked_leads.json"

BOT_USERNAME = "LanaS777Bot"
LANA_BOT_TOKEN = os.environ.get("LANA_BOT_TOKEN", "")
LANA_CHAT_ID = os.environ.get("LANA_CHAT_ID", "")


def send_telegram(token: str, chat_id: str, text: str) -> bool:
    if not token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[booking] Ошибка отправки в Telegram: {e}", flush=True)
        return False


def notify_hot_lead(lead: dict, booking: dict) -> None:
    author = lead.get("author", "неизвестен")
    source_url = lead.get("url", "")
    pain = lead.get("profile", {}).get("pain_point", "семейный кризис")
    booking_msg = booking.get("booking_message", "")

    text = (
        f"🔥 <b>Горячий лид!</b>\n\n"
        f"👤 Автор: <b>{author}</b>\n"
        f"💬 Боль: {pain}\n"
        f"🔗 Пост: {source_url}\n\n"
        f"📝 Готовое сообщение:\n<i>{booking_msg}</i>"
    )

    if LANA_BOT_TOKEN and LANA_CHAT_ID:
        ok = send_telegram(LANA_BOT_TOKEN, LANA_CHAT_ID, text)
        print(f"[booking] Отправка Лане: {'✅' if ok else '❌'}", flush=True)

BOOKING_PROMPT = """Ты копирайтер для психотерапевта (специализация: семейные кризисы).

Человек прошёл несколько касаний, тема разговора развивалась. Теперь нужно мягко предложить записаться на бесплатную консультацию через Telegram-бота.

Профиль человека:
- Боль: {pain_point}
- Состояние: {emotional_state}
- Первое сообщение, которое ему написали: {first_message}

Напиши ОДНО финальное сообщение (5-е касание):
- 2–3 предложения
- Никакого давления — только мягкое предложение
- Упомяни что это бесплатная первая встреча
- Включи: "Если откликается — можно написать боту @{bot}: он подберёт удобное время"
- Тон тёплый, как от живого человека

Ответь ТОЛЬКО JSON:
{{
  "booking_message": "текст финального сообщения",
  "cta": "текст призыва к действию (1 фраза)",
  "priority": "горячий/тёплый/холодный"
}}"""


async def generate_booking_message(lead: dict) -> dict:
    profile = lead.get("profile", {})
    first_contact = lead.get("first_contact", {})

    if _client is None:
        return _template_booking(lead)

    prompt = BOOKING_PROMPT.format(
        pain_point=profile.get("pain_point", "семейный кризис"),
        emotional_state=profile.get("emotional_state", "растерянность"),
        first_message=first_contact.get("message", "")[:200],
        bot=BOT_USERNAME,
    )

    try:
        resp = await asyncio.wait_for(
            asyncio.to_thread(lambda: _client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )),
            timeout=60,
        )
        raw = resp.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"[booking] ошибка Claude: {e}", flush=True)
        return _template_booking(lead)


def _template_booking(lead: dict) -> dict:
    profile = lead.get("profile", {})
    pain = profile.get("pain_point", "то, через что вы проходите")
    intent = lead.get("intent_score", 0) or 0
    confidence = lead.get("confidence_score", 0) or 0

    if intent >= 8 or confidence >= 60:
        priority = "горячий"
    elif intent >= 4 or confidence >= 43:
        priority = "тёплый"
    else:
        priority = "холодный"

    return {
        "booking_message": (
            f"Я понимаю, как непросто справляться с {pain} в одиночку. "
            f"Иногда один разговор с психологом помогает увидеть выход. "
            f"Если откликается — напишите боту @{BOT_USERNAME}, он подберёт удобное время для бесплатной первой встречи."
        ),
        "cta": f"Написать @{BOT_USERNAME} для записи",
        "priority": priority,
        "_fallback": True,
    }


async def run():
    print("[booking] Старт Booking Agent", flush=True)

    if not INPUT_FILE.exists():
        print("[booking] sequences.json не найден", flush=True)
        sys.exit(0)

    sequences = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    print(f"[booking] Лидов на входе: {len(sequences)}", flush=True)

    if not sequences:
        OUTPUT_FILE.write_text("[]", encoding="utf-8")
        sys.exit(0)

    if _client is None:
        print("[booking] Нет API-ключа — использую шаблонные сообщения", flush=True)

    booked = []
    for i, lead in enumerate(sequences, 1):
        author = lead.get("author", f"лид_{i}")
        print(f"[booking] {i}/{len(sequences)}: {author}", flush=True)

        booking = await generate_booking_message(lead)

        priority = booking.get("priority", "")
        if priority == "горячий":
            notify_hot_lead(lead, booking)

        booked.append({
            **lead,
            "booking_step": {
                **booking,
                "bot_link": f"https://t.me/{BOT_USERNAME}",
                "touch_number": 5,
                "generated_at": datetime.now().isoformat(),
            },
        })

    OUTPUT_FILE.write_text(json.dumps(booked, ensure_ascii=False, indent=2), encoding="utf-8")

    hot = sum(1 for b in booked if b.get("booking_step", {}).get("priority") == "горячий")
    warm = sum(1 for b in booked if b.get("booking_step", {}).get("priority") == "тёплый")
    print(f"[booking] Готово: {len(booked)} лидов → {OUTPUT_FILE}", flush=True)
    print(f"[booking] Горячих: {hot}, Тёплых: {warm}", flush=True)
    print(f"[booking] Ссылка для записи: https://t.me/{BOT_USERNAME}", flush=True)


if __name__ == "__main__":
    asyncio.run(run())
