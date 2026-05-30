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

import anthropic

if not os.environ.get("ANTHROPIC_API_KEY"):
    env_file = Path(__file__).parent.parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

_api_key = os.environ.get("ANTHROPIC_API_KEY")
_client = anthropic.Anthropic(api_key=_api_key) if _api_key else None


async def ask_claude(prompt: str, max_wait: int = 120) -> str:
    if _client is None:
        return ""
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                lambda: _client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=2048,
                    messages=[{"role": "user", "content": prompt}],
                )
            ),
            timeout=max_wait,
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"[validator] claude error: {e}", flush=True)
        return ""

ROOT = Path(__file__).parent.parent.parent
INPUT_FILE = ROOT / "leads_pipeline" / "raw_leads.json"
OUTPUT_FILE = ROOT / "leads_pipeline" / "enriched_leads.json"

BOT_MARKERS = [
    "купи", "скидка", "акция", "подпишись", "перейди по ссылке",
    "заработок", "инвестиции", "крипта", "млм", "100% гарантия",
]

BATCH_VALIDATE_PROMPT = """Ты аналитик лидов для психотерапевта, работающего с парами в кризисе (измены, развод, потеря близости).

Оцени каждый контакт из списка. Для каждого верни JSON-объект с полями:
- authenticity (0-100): реальный человек, не бот, не реклама
- problem_match (0-100): проблема подходит семейному психотерапевту
- readiness (0-100): человек готов обратиться за помощью
- confidence_score: среднее трёх оценок
- notes: одна короткая фраза

Верни ТОЛЬКО JSON-массив (без пояснений):
[{{"authenticity":0,"problem_match":0,"readiness":0,"confidence_score":0,"notes":""}}, ...]

Контакты для оценки:
{leads_json}"""


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


def fallback_scores(lead: dict) -> dict:
    """Локальная оценка без Claude — быстро, без API."""
    text = (lead.get("quote", "") + " " + lead.get("title", "")).lower()
    high_intent = ["хочу развестись", "муж изменил", "жена изменила", "спасти брак",
                   "помогите", "не знаю что делать", "психолог", "терапевт", "консультация"]
    medium_intent = ["кризис", "конфликт", "ругаемся", "охладел", "не понимает",
                     "потеряли близость", "чужие", "развод", "измена"]
    score = 30
    for phrase in high_intent:
        if phrase in text:
            score += 15
    for phrase in medium_intent:
        if phrase in text:
            score += 8
    score = min(score, 95)
    return {"authenticity": 70, "problem_match": score, "readiness": max(30, score - 15),
            "confidence_score": round((70 + score + max(30, score - 15)) / 3),
            "notes": "локальная оценка"}


async def ai_validate_batch(candidates: list[dict]) -> list[dict]:
    """Один вызов Claude для всех кандидатов — экономит время."""
    leads_for_prompt = [
        {"id": i, "source": l.get("source", ""), "author": l.get("author", ""),
         "quote": l.get("quote", "")[:200]}
        for i, l in enumerate(candidates)
    ]
    prompt = BATCH_VALIDATE_PROMPT.format(leads_json=json.dumps(leads_for_prompt, ensure_ascii=False))
    raw = await ask_claude(prompt, max_wait=90)

    if not raw:
        return [fallback_scores(l) for l in candidates]

    try:
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip()
        results = json.loads(raw)
        if isinstance(results, list) and len(results) == len(candidates):
            return results
    except Exception:
        pass

    return [fallback_scores(l) for l in candidates]


async def run():
    print("[validator] Старт Validator Agent", flush=True)

    if not INPUT_FILE.exists():
        print("[validator] raw_leads.json не найден — нет лидов для валидации", flush=True)
        sys.exit(0)

    raw_leads = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    print(f"[validator] Лидов на входе: {len(raw_leads)}", flush=True)

    # Базовая фильтрация
    candidates = []
    for i, lead in enumerate(raw_leads):
        ok, reason = basic_validate(lead)
        if not ok:
            print(f"[validator] #{i+1} отклонён: {reason}", flush=True)
        else:
            candidates.append(lead)

    print(f"[validator] Прошли базовый фильтр: {len(candidates)}", flush=True)

    if not candidates:
        OUTPUT_FILE.write_text("[]", encoding="utf-8")
        print("[validator] Нет кандидатов для AI-валидации", flush=True)
        sys.exit(0)

    # Один батчевый вызов Claude для всех кандидатов
    print(f"[validator] Батчевая AI-валидация {len(candidates)} лидов...", flush=True)
    all_scores = await ai_validate_batch(candidates)

    enriched = []
    for lead, scores in zip(candidates, all_scores):
        confidence = scores.get("confidence_score", 0)
        enriched_lead = {
            **lead,
            "validation": scores,
            "confidence_score": confidence,
            "validated_at": datetime.now().isoformat(),
            "ready_for_contact": confidence >= 55,
        }
        enriched.append(enriched_lead)
        print(f"[validator] {lead.get('source', '')} confidence={confidence:.0f}", flush=True)

    OUTPUT_FILE.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    ready = sum(1 for l in enriched if l["ready_for_contact"])
    print(f"[validator] Готово: {len(enriched)} верифицировано, {ready} готовы к контакту → {OUTPUT_FILE}", flush=True)


if __name__ == "__main__":
    asyncio.run(run())
