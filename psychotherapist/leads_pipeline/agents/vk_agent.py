"""
VK Agent — ищет лиды в ВКонтакте через DuckDuckGo (site:vk.com).
Не требует токена. Находит публичные посты с запросом на психологическую помощь.
Выход: raw_leads.json (мерж с Monitor/Forum Hunter)
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import aiohttp
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent.parent.parent
INPUT_FILE = ROOT / "leads_pipeline" / "raw_keywords.json"
OUTPUT_FILE = ROOT / "leads_pipeline" / "raw_leads.json"

SEARCH_QUERIES = [
    "site:vk.com нужен психолог помогите",
    "site:vk.com муж изменил что делать семья",
    "site:vk.com ищу психотерапевта онлайн",
    "site:vk.com тревога депрессия помогите советуйте",
    "site:vk.com хочу развестись что делать отношения",
    "site:vk.com панические атаки как справиться",
    "site:vk.com устала от отношений не знаю что делать",
    "site:vk.com муж пьет что делать семья",
]

HELP_MARKERS = [
    "помогите", "что делать", "посоветуйте", "как быть",
    "не знаю куда", "ищу помощь", "нужен совет", "совсем плохо",
    "не могу", "сил нет", "устала", "устал", "хочу уйти",
    "ищу психолога", "нужна консультация", "подскажите",
]

THEME_KEYWORDS = [
    "психолог", "психотерапевт", "развод", "измена", "тревога", "депрессия",
    "отношения", "семья", "конфликт", "стресс", "паник", "невроз",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def load_keywords() -> list[str]:
    if INPUT_FILE.exists():
        data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
        return data.get("keywords", []) + data.get("high_intent_phrases", [])
    return THEME_KEYWORDS


def is_help_seeking(text: str, keywords: list[str]) -> bool:
    tl = text.lower()
    has_theme = any(kw.lower() in tl for kw in keywords + THEME_KEYWORDS)
    has_help = any(m in tl for m in HELP_MARKERS)
    return has_theme or has_help


def intent_score(text: str) -> int:
    tl = text.lower()
    score = sum(1 for m in HELP_MARKERS if m in tl)
    if any(k in tl for k in ["психолог", "консультация", "психотерапевт"]):
        score += 2
    return min(score, 5)


def ddgs_search(query: str, max_results: int = 15) -> list[dict]:
    try:
        from ddgs import DDGS
        return list(DDGS().text(query, max_results=max_results))
    except Exception as e:
        print(f"[vk_agent] ddgs error: {e}", flush=True)
        return []


async def fetch_page_text(session: aiohttp.ClientSession, url: str) -> str:
    """Пробуем получить текст поста с VK."""
    try:
        # Для wall-постов пробуем m.vk.com
        if "/wall" in url:
            mobile_url = url.replace("vk.com/", "m.vk.com/").replace("https://vk.com/", "https://m.vk.com/")
        else:
            mobile_url = url
        async with session.get(mobile_url, timeout=aiohttp.ClientTimeout(total=8), headers=HEADERS) as r:
            if r.status != 200:
                return ""
            html = await r.text()
            soup = BeautifulSoup(html, "html.parser")
            # Убираем скрипты
            for tag in soup(["script", "style", "nav", "header", "footer"]):
                tag.decompose()
            return soup.get_text(separator=" ", strip=True)[:1000]
    except Exception:
        return ""


async def process_query(session: aiohttp.ClientSession, query: str, keywords: list[str]) -> list[dict]:
    results = await asyncio.to_thread(ddgs_search, query, 15)
    leads = []
    for r in results:
        url = r.get("href", "")
        if not url or "vk.com" not in url:
            continue
        # Достаём текст из сниппета DDG
        snippet = (r.get("title", "") + " " + r.get("body", "")).strip()
        # Пробуем дополнить текстом со страницы
        page_text = await fetch_page_text(session, url)
        full_text = (snippet + " " + page_text).strip()
        if len(full_text) < 20:
            continue
        if not is_help_seeking(full_text, keywords):
            continue
        leads.append({
            "url": url,
            "author": url.split("/")[3] if len(url.split("/")) > 3 else "vk",
            "quote": full_text[:400],
            "createdAt": datetime.now().isoformat(),
            "intentScore": intent_score(full_text),
            "source": "vk_ddgs",
            "query": query.replace("site:vk.com ", ""),
        })
    return leads


def merge_leads(existing: list[dict], new_leads: list[dict]) -> tuple[list[dict], int]:
    existing_urls = {l["url"] for l in existing}
    added = 0
    for lead in new_leads:
        if lead["url"] not in existing_urls:
            existing.append(lead)
            existing_urls.add(lead["url"])
            added += 1
    return existing, added


async def run():
    print("[vk_agent] Старт VK Agent (поиск через DDG + site:vk.com)", flush=True)

    keywords = load_keywords()
    all_leads: list[dict] = []

    async with aiohttp.ClientSession() as session:
        tasks = [process_query(session, q, keywords) for q in SEARCH_QUERIES]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                all_leads.extend(r)

    # Мерж с существующими лидами
    existing: list[dict] = []
    if OUTPUT_FILE.exists():
        try:
            existing = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
        except Exception:
            existing = []

    merged, added = merge_leads(existing, all_leads)
    OUTPUT_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[vk_agent] Найдено {len(all_leads)}, добавлено новых {added}, всего {len(merged)}", flush=True)


if __name__ == "__main__":
    asyncio.run(run())
