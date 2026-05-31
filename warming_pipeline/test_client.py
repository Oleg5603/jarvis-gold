"""
Тестовый клиент — пробный запуск Booking Agent.
Создаёт фейкового горячего лида, генерирует скрипт и шлёт результат хозяину.
Запуск: python warming_pipeline/test_client.py
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import urllib.request
import urllib.parse

ROOT = Path(__file__).parent.parent

# Загружаем .env
env_file = ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

LANA_BOT_TOKEN = os.environ.get("LANA_BOT_TOKEN", "")
LANA_CHAT_ID = os.environ.get("LANA_CHAT_ID", "347824016")
MAIN_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OWNER_CHAT_ID = "449885090"

MSK = timezone(timedelta(hours=3))


TEST_LEAD = {
    "author": "Марина_тест",
    "source_url": "https://pikabu.ru/story/test_lead",
    "text": "Муж ушёл месяц назад, дети плачут, я не сплю. Не знаю как жить дальше. Боюсь что схожу с ума.",
    "intent_score": 9,
    "confidence_score": 85,
    "profile": {
        "pain_point": "разрыв семьи и потеря опоры",
        "emotional_state": "острый кризис, страх, бессонница",
        "communication_style": "открытая, ищет поддержку",
        "readiness": "высокая — сама описывает боль подробно",
    },
    "first_contact": {
        "message": (
            "Марина, я вижу как вам сейчас тяжело. То, что вы чувствуете — это нормальная реакция на очень сильный удар. "
            "Вы не сходите с ума, вы переживаете кризис. И из него есть выход."
        ),
    },
    "sequence": [
        {"day": 1, "touch": "первый контакт — поддержка без давления"},
        {"day": 3, "touch": "история другой женщины, которая прошла это"},
        {"day": 7, "touch": "инструмент: как успокоить себя за 5 минут"},
        {"day": 14, "touch": "мягкий вопрос о состоянии"},
        {"day": 21, "touch": "предложение первой бесплатной встречи"},
    ],
}


def send_telegram(token: str, chat_id: str, text: str) -> bool:
    if not token or not chat_id:
        print(f"[test] Нет токена или chat_id: token={bool(token)}, chat_id={chat_id}", flush=True)
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
        print(f"[test] Ошибка Telegram: {e}", flush=True)
        return False


async def generate_booking_message(lead: dict) -> dict:
    try:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("нет ключа")

        client = anthropic.Anthropic(api_key=api_key)
        profile = lead["profile"]
        first_message = lead["first_contact"]["message"][:200]

        prompt = f"""Ты копирайтер для психотерапевта (семейные кризисы).

Профиль человека:
- Боль: {profile['pain_point']}
- Состояние: {profile['emotional_state']}
- Первое сообщение: {first_message}

Напиши финальное (5-е касание) сообщение — мягкое приглашение на бесплатную консультацию через @LanaS777Bot.
2–3 предложения, без давления, тёплый тон.

Ответь ТОЛЬКО JSON:
{{"booking_message": "...", "cta": "...", "priority": "горячий"}}"""

        resp = await asyncio.wait_for(
            asyncio.to_thread(lambda: client.messages.create(
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
        print(f"[test] Claude недоступен: {e} — использую шаблон", flush=True)
        return {
            "booking_message": (
                "Марина, вы уже сделали большой шаг — начали говорить о том, что происходит. "
                "Иногда один разговор с психологом помогает увидеть выход. "
                "Если откликается — напишите боту @LanaS777Bot, он подберёт удобное время для бесплатной первой встречи."
            ),
            "cta": "Написать @LanaS777Bot для записи",
            "priority": "горячий",
        }


async def run():
    now_msk = datetime.now(MSK)
    print(f"\n[test] Тестовый клиент — {now_msk:%d.%m.%Y %H:%M} МСК", flush=True)

    lead = TEST_LEAD.copy()
    booking = await generate_booking_message(lead)

    booking_msg = booking.get("booking_message", "")
    priority = booking.get("priority", "горячий")

    # Сообщение для Ланы
    lana_text = (
        f"🧪 <b>ТЕСТОВЫЙ КЛИЕНТ</b>\n\n"
        f"👤 Автор: <b>{lead['author']}</b>\n"
        f"💬 Боль: {lead['profile']['pain_point']}\n"
        f"🔥 Статус: {priority}\n\n"
        f"📝 Готовое финальное сообщение:\n"
        f"<i>{booking_msg}</i>\n\n"
        f"🗓 Последовательность касаний:\n"
        + "\n".join(f"  День {s['day']}: {s['touch']}" for s in lead['sequence'])
    )

    # Сообщение хозяину
    owner_text = (
        f"📊 <b>РЕЗУЛЬТАТ ТЕСТОВОГО КЛИЕНТА</b>\n"
        f"Дата: {now_msk:%d.%m.%Y %H:%M} МСК\n\n"
        f"👤 Тест-лид: <b>{lead['author']}</b>\n"
        f"🎯 intent_score: {lead['intent_score']}/10 | confidence: {lead['confidence_score']}%\n"
        f"💬 Боль: {lead['profile']['pain_point']}\n"
        f"💡 Состояние: {lead['profile']['emotional_state']}\n\n"
        f"📩 Первое сообщение:\n<i>{lead['first_contact']['message'][:200]}</i>\n\n"
        f"🏁 Финальное сообщение (5-е касание):\n<i>{booking_msg}</i>\n\n"
        f"🤖 Лид отправлен @LanaS777Bot — ждём ответа от тест-клиента."
    )

    print(f"\n[test] Отправка Лане (ID {LANA_CHAT_ID})...", flush=True)
    ok_lana = send_telegram(LANA_BOT_TOKEN, LANA_CHAT_ID, lana_text)
    print(f"[test] Лана: {'✅' if ok_lana else '❌'}", flush=True)

    print(f"[test] Отправка хозяину (ID {OWNER_CHAT_ID})...", flush=True)
    ok_owner = send_telegram(MAIN_BOT_TOKEN, OWNER_CHAT_ID, owner_text)
    print(f"[test] Хозяин: {'✅' if ok_owner else '❌'}", flush=True)

    # Сохраняем результат
    result_file = ROOT / "warming_pipeline" / "test_client_result.json"
    result_file.write_text(json.dumps({
        "lead": lead,
        "booking": booking,
        "sent_to_lana": ok_lana,
        "sent_to_owner": ok_owner,
        "run_at": now_msk.isoformat(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[test] Готово! Результат → {result_file}", flush=True)
    print(f"[test] Лане отправлено: {'да' if ok_lana else 'нет'}", flush=True)
    print(f"[test] Хозяину отправлено: {'да' if ok_owner else 'нет'}", flush=True)


if __name__ == "__main__":
    asyncio.run(run())
