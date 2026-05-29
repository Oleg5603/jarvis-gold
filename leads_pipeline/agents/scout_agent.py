"""
Scout Agent — собирает семантику: реальные фразы людей о проблемах в браке.
Читает форумы, анализирует через Claude, выдаёт JSON с ключевыми словами.
"""

import asyncio
import json
import sys
import os
from datetime import datetime
from pathlib import Path

import aiohttp
import anthropic
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent.parent.parent
OUTPUT_FILE = ROOT / "leads_pipeline" / "raw_keywords.json"

SEED_URLS = [
    "https://pikabu.ru/tag/%D0%BE%D1%82%D0%BD%D0%BE%D1%88%D0%B5%D0%BD%D0%B8%D1%8F",
    "https://www.woman.ru/psyche/relationship/",
    "https://www.reddit.com/r/relationships/.json?limit=25&t=week",
]

SCOUT_PROMPT = """Ты эксперт по маркетингу и психологии. Перед тобой — тексты с форумов, где люди пишут о проблемах в браке и отношениях.

Твоя задача:
1. Выдели 30–50 ключевых фраз, которыми люди РЕАЛЬНО описывают кризис в отношениях
2. Разбей по эмоциональным маркерам: отчаяние, злость, надежда, растерянность, поиск помощи
3. Определи фразы с ВЫСОКИМ интентом (человек уже ищет специалиста или готов к этому)

Формат ответа — только валидный JSON:
{
  "keywords": ["фраза1", "фраза2", ...],
  "high_intent_phrases": ["хочу к психологу", "нужна помощь с браком", ...],
  "emotional_markers": {
    "despair": ["больше не могу", "хочу развестись", ...],
    "anger": ["изменил", "предал", "невозможно жить", ...],
    "hope": ["хочу сохранить семью", "попробуем ещё раз", ...],
    "confusion": ["не понимаю что делать", "куда обратиться", ...],
    "seeking_help": ["кто-нибудь через это прошёл", "посоветуйте специалиста", ...]
  }
}

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

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    prompt = SCOUT_PROMPT.format(texts="\n---\n".join(all_texts[:30]))

    print("[scout] Анализируем через Claude...", flush=True)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    # Вырезаем JSON если обёрнут в ```
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    keywords_data = json.loads(raw)
    keywords_data["generated_at"] = datetime.now().isoformat()
    keywords_data["source_count"] = len(all_texts)

    OUTPUT_FILE.write_text(json.dumps(keywords_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[scout] Готово: {len(keywords_data.get('keywords', []))} ключевых слов → {OUTPUT_FILE}", flush=True)


if __name__ == "__main__":
    asyncio.run(run())
