"""
Validator Agent — верифицирует авторов: проверяет что не бот, оценивает confidenceScore.
Вход: raw_leads.json → Выход: enriched_leads.json
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import aiohttp
import anthropic

ROOT = Path(__file__).parent.parent.parent
INPUT_FILE = ROOT / "leads_pipeline" / "raw_leads.json"
OUTPUT_FILE = ROOT / "leads_pipeline" / "enriched_leads.json"

BOT_MARKERS = [
    "купи", "скидка", "акция", "подпишись", "перейди по ссылке",
    "заработок", "инвестиции", "крипта", "млм", "100% гарантия",
]

VALIDATE_PROMPT = """Ты аналитик лидов. Оцени качество этого контакта для психотерапевта, работающего с парами.

Источник: {source}
Автор: {author}
Цитата: "{quote}"

Оцени по критериям (от 0 до 100 каждый):
- authenticity: насколько это реальный человек (не бот, не реклама)
- problem_match: насколько проблема подходит психотерапевту по супружеским отношениям
- readiness: насколько человек готов к обращению за помощью

Ответь только JSON:
{{"authenticity": 0-100, "problem_match": 0-100, "readiness": 0-100, "confidence_score": среднее_трёх, "notes": "короткий комментарий"}}"""


def is_likely_bot(text: str) -> bool:
    text_lower = text.lower()
    return sum(1 for m in BOT_MARKERS if m in text_lower) >= 2


def basic_validate(lead: dict) -> tuple[bool, str]:
    text = lead.get("quote", "")
    if len(text) < 30:
        return False, "Слишком короткий текст"
    if is_likely_bot(text):
        return False, "Похоже на рекламу/бота"
    if not lead.get("url"):
        return False, "Нет URL"
    return True, "OK"


async def ai_validate(client: anthropic.Anthropic, lead: dict) -> dict:
    prompt = VALIDATE_PROMPT.format(
        source=lead.get("source", ""),
        author=lead.get("author", ""),
        quote=lead.get("quote", "")[:250],
    )
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip()
        return json.loads(raw)
    except Exception as e:
        return {"authenticity": 50, "problem_match": 50, "readiness": 30, "confidence_score": 43, "notes": str(e)}


async def run():
    print("[validator] Старт Validator Agent", flush=True)

    if not INPUT_FILE.exists():
        print("[validator] raw_leads.json не найден — нет лидов для валидации", flush=True)
        sys.exit(0)

    raw_leads = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    print(f"[validator] Лидов на входе: {len(raw_leads)}", flush=True)

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    enriched = []

    for i, lead in enumerate(raw_leads):
        ok, reason = basic_validate(lead)
        if not ok:
            print(f"[validator] #{i+1} отклонён: {reason}", flush=True)
            continue

        scores = await ai_validate(client, lead)
        confidence = scores.get("confidence_score", 0)

        enriched_lead = {
            **lead,
            "validation": scores,
            "confidence_score": confidence,
            "validated_at": datetime.now().isoformat(),
            "ready_for_contact": confidence >= 55,
        }
        enriched.append(enriched_lead)
        print(f"[validator] #{i+1} {lead.get('source', '')} confidence={confidence:.0f}", flush=True)
        await asyncio.sleep(0.5)

    OUTPUT_FILE.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    ready = sum(1 for l in enriched if l["ready_for_contact"])
    print(f"[validator] Готово: {len(enriched)} верифицировано, {ready} готовы к контакту → {OUTPUT_FILE}", flush=True)


if __name__ == "__main__":
    asyncio.run(run())
