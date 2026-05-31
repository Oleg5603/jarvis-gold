"""
Scout Agent — собирает семантику: реальные фразы людей о проблемах в браке.
Читает форумы, анализирует через Claude, выдаёт JSON с ключевыми словами.
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import aiohttp
import anthropic
from bs4 import BeautifulSoup

# Загружаем .env если ключ не задан
if not os.environ.get("ANTHROPIC_API_KEY"):
    env_file = Path(__file__).parent.parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

_api_key = os.environ.get("ANTHROPIC_API_KEY")
_client = anthropic.Anthropic(api_key=_api_key) if _api_key else None


async def ask_claude(prompt: str, max_wait: int = 90) -> str:
    if _client is None:
        print("[scout] ANTHROPIC_API_KEY не задан — пропуск Claude", flush=True)
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
        print(f"[scout] claude error: {e}", flush=True)
        return ""

ROOT = Path(__file__).parent.parent.parent
OUTPUT_FILE = ROOT / "leads_pipeline" / "raw_keywords.json"

SEED_URLS = [
    "https://pikabu.ru/tag/%D0%BE%D1%82%D0%BD%D0%BE%D1%88%D0%B5%D0%BD%D0%B8%D1%8F",
    "https://www.woman.ru/psyche/relationship/",
    "https://www.reddit.com/r/relationships/.json?limit=25&t=week",
]

SCOUT_PROMPT_TEMPLATE = """Ты эксперт по маркетингу и психологии. Перед тобой — тексты с форумов, где люди пишут о проблемах в браке и отношениях.

Твоя задача:
1. Выдели 30–50 ключевых фраз, которыми люди РЕАЛЬНО описывают кризис в отношениях
2. Разбей по эмоциональным маркерам: отчаяние, злость, надежда, растерянность, поиск помощи
3. Определи фразы с ВЫСОКИМ интентом (человек уже ищет специалиста или готов к этому)

Формат ответа — только валидный JSON без пояснений:
{{
  "keywords": ["фраза1", "фраза2"],
  "high_intent_phrases": ["хочу к психологу", "нужна помощь с браком"],
  "emotional_markers": {{
    "despair": ["больше не могу", "хочу развестись"],
    "anger": ["изменил", "предал"],
    "hope": ["хочу сохранить семью"],
    "confusion": ["не понимаю что делать"],
    "seeking_help": ["посоветуйте специалиста"]
  }}
}}

Тексты для анализа:
{texts}"""


async def fetch_page(session: aiohttp.ClientSession, url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; LeadResearcher/1.0)"}
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                return await resp.text()
    except Exception as e:
        print(f"[scout] fetch error {url}: {e}", flush=True)
    return ""


def extract_texts(html: str, url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    texts = []

    if "reddit" in url and html.startswith("{"):
        try:
            data = json.loads(html)
            posts = data["data"]["children"]
            for p in posts:
                d = p["data"]
                if d.get("selftext"):
                    texts.append(d["selftext"][:500])
                texts.append(d.get("title", ""))
        except Exception:
            pass
    else:
        for tag in soup.find_all(["p", "div", "article"], limit=50):
            text = tag.get_text(strip=True)
            if len(text) > 80:
                texts.append(text[:400])

    return [t for t in texts if t][:20]


async def run():
    print("[scout] Старт Scout Agent", flush=True)
    all_texts = []

    async with aiohttp.ClientSession() as session:
        pages = await asyncio.gather(*[fetch_page(session, url) for url in SEED_URLS])

    for url, html in zip(SEED_URLS, pages):
        texts = extract_texts(html, url)
        all_texts.extend(texts)
        print(f"[scout] {url}: {len(texts)} текстов", flush=True)

    if not all_texts:
        # Fallback: используем заготовленную семантику
        all_texts = [
            "Муж изменил, не знаю что делать",
            "Как сохранить брак после измены",
            "Мы постоянно ругаемся, хочу развода",
            "Нет близости в браке уже 2 года",
            "Муж не понимает меня, чужие люди",
        ]
        print("[scout] Используем fallback-тексты", flush=True)

    prompt = SCOUT_PROMPT_TEMPLATE.format(texts="\n---\n".join(all_texts[:30]))

    print("[scout] Анализируем через Claude...", flush=True)
    raw = await ask_claude(prompt, max_wait=120)
    print(f"[scout] Ответ Claude ({len(raw)} символов)", flush=True)

    keywords_data = None
    if raw:
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip()
        try:
            keywords_data = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"[scout] JSON parse error: {e}, используем fallback", flush=True)

    if not keywords_data:
        print("[scout] Используем расширенный fallback", flush=True)
        keywords_data = {
            "keywords": ["измена", "развод", "кризис брака", "психолог семья", "конфликты супруги",
                         "не понимает", "охладел", "потеря близости", "ругаемся постоянно", "хочу уйти"],
            "high_intent_phrases": ["нужна помощь психолога", "хочу к семейному терапевту",
                                     "как сохранить брак", "советуйте специалиста"],
            "emotional_markers": {
                "despair": ["больше не могу", "устала от отношений"],
                "anger": ["изменил", "предал", "невозможно жить"],
                "hope": ["хочу сохранить семью"],
                "confusion": ["не знаю что делать"],
                "seeking_help": ["посоветуйте специалиста", "куда обратиться"]
            }
        }
    keywords_data["generated_at"] = datetime.now().isoformat()
    keywords_data["source_count"] = len(all_texts)

    OUTPUT_FILE.write_text(json.dumps(keywords_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[scout] Готово: {len(keywords_data.get('keywords', []))} ключевых слов → {OUTPUT_FILE}", flush=True)


if __name__ == "__main__":
    asyncio.run(run())
