"""
Forum Hunter Agent — парсит свежие темы (<7 дней) на целевых площадках.
Выход: массив объектов {url, author, quote, createdAt, intentScore, source}
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import aiohttp
import anthropic
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent.parent.parent
INPUT_FILE = ROOT / "leads_pipeline" / "raw_keywords.json"
OUTPUT_FILE = ROOT / "leads_pipeline" / "raw_leads.json"

TARGETS = [
    {
        "name": "pikabu",
        "url": "https://pikabu.ru/tag/%D0%BE%D1%82%D0%BD%D0%BE%D1%88%D0%B5%D0%BD%D0%B8%D1%8F/hot",
        "post_selector": "article.story",
        "title_selector": "h2.story__title a",
        "text_selector": ".story__content-inner",
        "author_selector": ".user__nick",
        "date_selector": "time",
    },
    {
        "name": "woman.ru",
        "url": "https://www.woman.ru/psyche/relationship/",
        "post_selector": "div.article-list__item",
        "title_selector": "a.article-list__item-title",
        "text_selector": ".article-list__item-desc",
        "author_selector": None,
        "date_selector": ".article-list__item-date",
    },
    {
        "name": "reddit",
        "url": "https://www.reddit.com/r/relationships/.json?limit=50&t=week",
        "is_json": True,
    },
]

INTENT_PROMPT = """Оцени интент автора найти профессиональную психологическую помощь по шкале 0–100.

Текст: "{text}"

Ответь только числом от 0 до 100. 100 = человек прямо ищет психолога или терапевта. 0 = просто делится историей без запроса помощи."""


async def fetch(session: aiohttp.ClientSession, url: str, is_json: bool = False) -> str | dict | None:
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status != 200:
                return None
            return await resp.json() if is_json else await resp.text()
    except Exception as e:
        print(f"[forum_hunter] fetch error {url}: {e}", flush=True)
        return None


def parse_pikabu(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    leads = []
    for article in soup.select("article.story")[:20]:
        title_el = article.select_one("h2.story__title a")
        author_el = article.select_one(".user__nick")
        text_el = article.select_one(".story__content-inner")
        if not title_el:
            continue
        leads.append({
            "url": title_el.get("href", ""),
            "author": author_el.text.strip() if author_el else "unknown",
            "quote": (text_el.get_text(strip=True)[:300] if text_el else title_el.text.strip()),
            "source": "pikabu.ru",
            "createdAt": datetime.now().isoformat(),
        })
    return leads


def parse_woman(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    leads = []
    for item in soup.select(".article-list__item")[:20]:
        link = item.select_one("a")
        text = item.select_one(".article-list__item-desc")
        if not link:
            continue
        href = link.get("href", "")
        if not href.startswith("http"):
            href = "https://www.woman.ru" + href
        leads.append({
            "url": href,
            "author": "woman.ru reader",
            "quote": text.get_text(strip=True)[:300] if text else link.text.strip(),
            "source": "woman.ru",
            "createdAt": datetime.now().isoformat(),
        })
    return leads


def parse_reddit(data: dict) -> list[dict]:
    leads = []
    try:
        posts = data["data"]["children"]
        week_ago = datetime.now() - timedelta(days=7)
        for p in posts:
            d = p["data"]
            created = datetime.fromtimestamp(d.get("created_utc", 0))
            if created < week_ago:
                continue
            text = d.get("selftext", "") or d.get("title", "")
            leads.append({
                "url": f"https://reddit.com{d.get('permalink', '')}",
                "author": d.get("author", "unknown"),
                "quote": text[:300],
                "source": "reddit.com/r/relationships",
                "createdAt": created.isoformat(),
            })
    except Exception as e:
        print(f"[forum_hunter] reddit parse error: {e}", flush=True)
    return leads


def load_keywords() -> list[str]:
    if INPUT_FILE.exists():
        data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
        return data.get("keywords", []) + data.get("high_intent_phrases", [])
    return ["измена", "развод", "кризис", "психолог", "семейные проблемы"]


def is_relevant(text: str, keywords: list[str]) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


async def score_intent(client: anthropic.Anthropic, text: str) -> int:
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": INTENT_PROMPT.format(text=text[:200])}],
        )
        return int(re.search(r"\d+", msg.content[0].text).group())
    except Exception:
        return 30


async def run():
    print("[forum_hunter] Старт Forum Hunter Agent", flush=True)
    keywords = load_keywords()
    all_leads: list[dict] = []

    async with aiohttp.ClientSession() as session:
        for target in TARGETS:
            print(f"[forum_hunter] Парсим {target['name']}...", flush=True)
            is_json = target.get("is_json", False)
            data = await fetch(session, target["url"], is_json)
            if not data:
                continue

            if target["name"] == "pikabu":
                raw = parse_pikabu(data)
            elif target["name"] == "woman.ru":
                raw = parse_woman(data)
            elif target["name"] == "reddit":
                raw = parse_reddit(data)
            else:
                raw = []

            relevant = [l for l in raw if is_relevant(l["quote"], keywords)]
            print(f"[forum_hunter] {target['name']}: {len(raw)} постов, {len(relevant)} релевантных", flush=True)
            all_leads.extend(relevant)

    # Скоринг интента через Claude
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    print(f"[forum_hunter] Скоринг {len(all_leads)} лидов...", flush=True)

    scored = []
    for lead in all_leads[:50]:  # Лимит 50 для скорости
        score = await score_intent(client, lead["quote"])
        lead["intentScore"] = score
        lead["disclaimer"] = "Лид найден в открытом публичном источнике"
        scored.append(lead)
        await asyncio.sleep(0.3)

    # Мердж с существующим файлом
    existing = []
    if OUTPUT_FILE.exists():
        existing = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))

    seen = {l.get("url") for l in existing}
    merged = existing + [l for l in scored if l.get("url") not in seen]
    OUTPUT_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[forum_hunter] Готово: {len(scored)} новых лидов → {OUTPUT_FILE}", flush=True)


if __name__ == "__main__":
    asyncio.run(run())
