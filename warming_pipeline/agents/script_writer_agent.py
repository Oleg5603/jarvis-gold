"""
Script Writer Agent — персональное первое сообщение для каждого лида.
Вход: warming_pipeline/profiles.json → Выход: warming_pipeline/scripts.json
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
INPUT_FILE = ROOT / "warming_pipeline" / "profiles.json"
OUTPUT_FILE = ROOT / "warming_pipeline" / "scripts.json"

SCRIPT_PROMPT = """Ты копирайтер для психотерапевта (специализация: семейные кризисы, восстановление отношений).

Напиши первое сообщение человеку, который написал на форуме о проблемах в браке.
Профиль:
- Боль: {pain_point}
- Состояние: {emotional_state}
- Стиль: {communication_style}
- Готовность к помощи: {readiness}
- Как открыть разговор: {best_opening}
- Избегать: {avoid}
- Цитата из поста: {quote}

ТРЕБОВАНИЯ:
- Сообщение 2-3 предложения, не больше
- Тёплое, без навязчивости, без рекламы
- Упомяни их ситуацию конкретно (из цитаты) — покажи что читал
- Не предлагай услуги в лоб — только открой диалог
- Заканчивай открытым вопросом или предложением

Ответь ТОЛЬКО JSON:
{{
  "message": "текст первого сообщения",
  "tone": "описание тона в 3 словах",
  "expected_response_rate": "высокий/средний/низкий"
}}"""


async def write_script(profile: dict) -> dict:
    p = profile.get("profile", {})

    if _client is None:
        return _template_script(profile)

    prompt = SCRIPT_PROMPT.format(
        pain_point=p.get("pain_point", "семейный кризис"),
        emotional_state=p.get("emotional_state", "растерянность"),
        communication_style=p.get("communication_style", "открытый"),
        readiness=p.get("readiness_to_help", "средняя"),
        best_opening=p.get("best_opening", ""),
        avoid=p.get("avoid", ""),
        quote=profile.get("quote", "")[:200],
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
        print(f"[script_writer] ошибка Claude: {e}", flush=True)
        return _template_script(profile)


def _template_script(profile: dict) -> dict:
    p = profile.get("profile", {})
    opening = p.get("best_opening", "Вижу, что вы проходите через непростое время в отношениях.")
    return {
        "message": f"{opening} Если захотите поговорить об этом — я здесь и готова выслушать. Как вы сейчас?",
        "tone": "тёплый поддерживающий мягкий",
        "expected_response_rate": "средний",
        "_fallback": True,
    }


async def run():
    print("[script_writer] Старт Script Writer Agent", flush=True)

    if not INPUT_FILE.exists():
        print("[script_writer] profiles.json не найден", flush=True)
        sys.exit(0)

    profiles = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    print(f"[script_writer] Профилей на входе: {len(profiles)}", flush=True)

    if not profiles:
        OUTPUT_FILE.write_text("[]", encoding="utf-8")
        sys.exit(0)

    if _client is None:
        print("[script_writer] Нет API-ключа — использую шаблонные скрипты", flush=True)

    scripts = []
    for i, profile in enumerate(profiles, 1):
        author = profile.get("author", f"лид_{i}")
        print(f"[script_writer] {i}/{len(profiles)}: {author}", flush=True)
        script = await write_script(profile)
        scripts.append({
            **profile,
            "first_contact": script,
            "script_written_at": datetime.now().isoformat(),
        })

    OUTPUT_FILE.write_text(json.dumps(scripts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[script_writer] Готово: {len(scripts)} скриптов → {OUTPUT_FILE}", flush=True)


if __name__ == "__main__":
    asyncio.run(run())
