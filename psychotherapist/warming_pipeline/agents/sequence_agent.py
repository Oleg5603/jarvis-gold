"""
Sequence Builder Agent — план прогрева 5 касаний для каждого лида.
Вход: warming_pipeline/scripts.json → Выход: warming_pipeline/sequences.json
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
INPUT_FILE = ROOT / "warming_pipeline" / "scripts.json"
OUTPUT_FILE = ROOT / "warming_pipeline" / "sequences.json"

SEQUENCE_PROMPT = """Ты стратег отдела продаж для психотерапевта. Построй план прогрева человека из 5 шагов.

Профиль:
- Боль: {pain_point}
- Состояние: {emotional_state}
- Готовность: {readiness}
- Срочность: {urgency}
- Первое сообщение уже готово: "{first_message}"

Построй 5 касаний ПОСЛЕ первого сообщения (если нет ответа — продолжаем греть ценностью):

Ответь ТОЛЬКО JSON (массив из 5 объектов):
[
  {{
    "touch": 2,
    "delay_days": 3,
    "channel": "форум/тг/email",
    "type": "follow_up/value/social_proof/soft_offer/close",
    "message": "текст сообщения 1-3 предложения",
    "goal": "цель этого касания"
  }}
]"""

TEMPLATE_SEQUENCE = [
    {
        "touch": 2,
        "delay_days": 3,
        "channel": "тот же",
        "type": "follow_up",
        "message": "Просто хотела убедиться, что моё сообщение не потерялось. Как вы?",
        "goal": "напомнить о себе ненавязчиво",
    },
    {
        "touch": 3,
        "delay_days": 7,
        "channel": "тот же",
        "type": "value",
        "message": "Нашла материал, который, возможно, будет полезен в вашей ситуации. Могу поделиться?",
        "goal": "дать пользу, показать экспертность",
    },
    {
        "touch": 4,
        "delay_days": 14,
        "channel": "тот же",
        "type": "social_proof",
        "message": "Недавно работала с парой в похожей ситуации — они смогли найти путь вперёд. Если захотите узнать как — напишите.",
        "goal": "показать что есть выход, без навязчивости",
    },
    {
        "touch": 5,
        "delay_days": 21,
        "channel": "тот же",
        "type": "soft_offer",
        "message": "Провожу бесплатную 20-минутную встречу-знакомство. Если хотите поговорить — просто напишите.",
        "goal": "предложить точку входа без риска и давления",
    },
    {
        "touch": 6,
        "delay_days": 30,
        "channel": "тот же",
        "type": "close",
        "message": "Буду рада помочь, когда будете готовы. Желаю сил и ясности в вашей ситуации.",
        "goal": "закрыть цикл с теплом, оставить дверь открытой",
    },
]


async def build_sequence(lead: dict) -> list:
    p = lead.get("profile", {})
    fc = lead.get("first_contact", {})

    if _client is None:
        return TEMPLATE_SEQUENCE

    prompt = SEQUENCE_PROMPT.format(
        pain_point=p.get("pain_point", "семейный кризис"),
        emotional_state=p.get("emotional_state", "растерянность"),
        readiness=p.get("readiness_to_help", "средняя"),
        urgency=p.get("urgency", "средняя"),
        first_message=fc.get("message", "")[:150],
    )

    try:
        resp = await asyncio.wait_for(
            asyncio.to_thread(lambda: _client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )),
            timeout=60,
        )
        raw = resp.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip()
        seq = json.loads(raw)
        if isinstance(seq, list) and len(seq) >= 4:
            return seq
    except Exception as e:
        print(f"[sequence_builder] ошибка Claude: {e}", flush=True)

    return TEMPLATE_SEQUENCE


async def run():
    print("[sequence_builder] Старт Sequence Builder Agent", flush=True)

    if not INPUT_FILE.exists():
        print("[sequence_builder] scripts.json не найден", flush=True)
        sys.exit(0)

    leads = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    print(f"[sequence_builder] Скриптов на входе: {len(leads)}", flush=True)

    if not leads:
        OUTPUT_FILE.write_text("[]", encoding="utf-8")
        sys.exit(0)

    if _client is None:
        print("[sequence_builder] Нет API-ключа — использую шаблонные последовательности", flush=True)

    sequences = []
    for i, lead in enumerate(leads, 1):
        author = lead.get("author", f"лид_{i}")
        print(f"[sequence_builder] {i}/{len(leads)}: {author}", flush=True)
        seq = await build_sequence(lead)
        sequences.append({
            **lead,
            "warming_sequence": seq,
            "total_touches": len(seq) + 1,
            "total_days": max((s.get("delay_days", 0) for s in seq), default=0),
            "sequence_built_at": datetime.now().isoformat(),
        })

    OUTPUT_FILE.write_text(json.dumps(sequences, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[sequence_builder] Готово: {len(sequences)} последовательностей → {OUTPUT_FILE}", flush=True)


if __name__ == "__main__":
    asyncio.run(run())
