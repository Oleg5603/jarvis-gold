"""
Profiler Agent — психологический профиль каждого лида.
Вход: leads_pipeline/ready_for_crm.json → Выход: warming_pipeline/profiles.json
"""

import asyncio
import json
import os
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

ROOT = Path(__file__).parent.parent.parent
INPUT_FILE = ROOT / "leads_pipeline" / "ready_for_crm.json"
OUTPUT_FILE = ROOT / "warming_pipeline" / "profiles.json"

PROFILE_PROMPT = """Ты психолог-аналитик. Прочитай сообщение с форума и составь профиль человека.

Источник: {source}
Цитата: {quote}

Ответь ТОЛЬКО валидным JSON (без пояснений):
{{
  "pain_point": "главная боль — одно предложение",
  "emotional_state": "одно слово: отчаяние/растерянность/злость/тоска/надежда/обида",
  "communication_style": "одно слово: открытый/закрытый/агрессивный/пассивный/рациональный",
  "readiness_to_help": "высокая/средняя/низкая — готовность принять помощь",
  "best_opening": "как начать разговор — 1-2 предложения максимально конкретно",
  "avoid": "что точно не говорить этому человеку",
  "urgency": "высокая/средняя/низкая — насколько остро стоит проблема"
}}"""


async def profile_lead(lead: dict) -> dict:
    if _client is None:
        return _template_profile(lead)

    prompt = PROFILE_PROMPT.format(
        source=lead.get("source_name", "форум"),
        quote=lead.get("quote", "")[:300],
    )
    try:
        resp = await asyncio.wait_for(
            asyncio.to_thread(lambda: _client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}],
            )),
            timeout=60,
        )
        raw = resp.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"[profiler] ошибка Claude: {e}", flush=True)
        return _template_profile(lead)


def _template_profile(lead: dict) -> dict:
    quote = (lead.get("quote", "") + " " + lead.get("quote", "")).lower()
    urgency = "высокая" if any(w in quote for w in ["помогите", "не знаю", "хочу развестись", "изменил"]) else "средняя"
    return {
        "pain_point": "семейный кризис — уточнить при контакте",
        "emotional_state": "растерянность",
        "communication_style": "открытый",
        "readiness_to_help": "средняя",
        "best_opening": "Вижу, вы писали о сложной ситуации в отношениях. Если хотите поговорить — я рядом.",
        "avoid": "советы и оценки без запроса",
        "urgency": urgency,
        "_fallback": True,
    }


async def run():
    print("[profiler] Старт Profiler Agent", flush=True)

    if not INPUT_FILE.exists():
        print("[profiler] ready_for_crm.json не найден", flush=True)
        sys.exit(0)

    leads = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    print(f"[profiler] Лидов на входе: {len(leads)}", flush=True)

    if not leads:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text("[]", encoding="utf-8")
        sys.exit(0)

    if _client is None:
        print("[profiler] ANTHROPIC_API_KEY не найден — использую шаблонные профили", flush=True)

    profiles = []
    for i, lead in enumerate(leads, 1):
        author = lead.get("author", f"лид_{i}")
        print(f"[profiler] {i}/{len(leads)}: {author}", flush=True)
        profile_data = await profile_lead(lead)
        profiles.append({
            **lead,
            "profile": profile_data,
            "profiled_at": datetime.now().isoformat(),
        })

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[profiler] Готово: {len(profiles)} профилей → {OUTPUT_FILE}", flush=True)


if __name__ == "__main__":
    asyncio.run(run())
