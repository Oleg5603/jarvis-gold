"""
Forum Hunter Agent — парсит свежие темы (<7 дней) на целевых площадках.
Выход: массив объектов {url, author, quote, createdAt, intentScore, source}
"""

import asyncio
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import aiohttp
from bs4 import BeautifulSoup

CLAUDE_BIN = "/usr/bin/claude"


async def ask_claude(prompt: str, max_wait: int = 30) -> str:
    proc = await asyncio.create_subprocess_exec(
        CLAUDE_BIN, "-p", "--output-format", "text",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(prompt.encode()), timeout=max_wait)
        return stdout.decode().strip()
    except asyncio.TimeoutError:
        proc.kill()
        return ""

ROOT = Path(__file__).parent.parent.parent
INPUT_FILE = ROOT / "leads_pipeline" / "raw_keywords.json"
OUTPUT_FILE = ROOT / "leads_pipeline" / "raw_leads.json"

TARGETS = [
    {
        "name": "pikabu",
        "url": "https://pikabu.ru/tag/%D0%BE%D1%82%D0%BD%D0%BE%D1%88%D0%B5%D0%BD%D0%B8%D1%8F/hot",
    },
    {
        "name": "woman.ru",
        "url": "https://www.woman.ru/psyche/relationship/",
    },
    {
        "name": "reddit",
        "url": "https://www.reddit.com/r/relationships/.json?limit=50&t=week",
        "is_json": True,
    },
    {
        "name": "babyblog",
        "url": "https://www.babyblog.ru/community/list/family_relationship",
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


def parse_babyblog(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    leads = []
    for item in soup.select(".community-record, .post-item, article")[:20]:
        link = item.select_one("a[href*='/user/'], a[href*='/community/']") or item.select_one("a")
        title = item.select_one("h2, h3, .post-title, .record-title")
        text_el = item.select_one(".record-text, .post-text, p")
        if not link and not title:
            continue
        href = (link.get("href", "") if link else "") or ""
        if href and not href.startswith("http"):
            href = "https://www.babyblog.ru" + href
        quote = ""
        if text_el:
            quote = text_el.get_text(strip=True)[:300]
        elif title:
            quote = title.get_text(strip=True)
        if not quote:
            continue
        leads.append({
            "url": href or "https://www.babyblog.ru",
            "author": "babyblog reader",
            "quote": quote,
            "source": "babyblog.ru",
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


# Строгие маркеры — требуем минимум 2 совпадения из этого списка
STRONG_MARKERS = [
    "измена", "развод", "кризис в браке", "не понимаем друг друга",
    "хочу развестись", "муж изменил", "жена изменила", "расстаёмся",
    "нужна помощь психолога", "семейный психолог", "потеряли близость",
    "ругаемся каждый день", "не могу простить", "предательство",
    "хочу сохранить брак", "разлюбил", "разлюбила",
]


def load_keywords() -> list[str]:
    if INPUT_FILE.exists():
        data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
        return data.get("keywords", []) + data.get("high_intent_phrases", [])
    return ["измена", "развод", "кризис", "психолог", "семейные проблемы"]


def is_relevant(text: str, keywords: list[str]) -> bool:
    text_lower = text.lower()
    # Минимум 2 точных совпадения из Scout-ключевых слов
    kw_hits = sum(1 for kw in keywords if kw.lower() in text_lower)
    if kw_hits >= 2:
        return True
    # Или хотя бы 1 сильный маркер + 1 ключевое слово
    strong_hits = sum(1 for m in STRONG_MARKERS if m in text_lower)
    return strong_hits >= 1 and kw_hits >= 1


async def score_intent(text: str) -> int:
    try:
        raw = await ask_claude(INTENT_PROMPT.format(text=text[:200]))
        m = re.search(r"\d+", raw)
        return int(m.group()) if m else 30
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
            elif target["name"] == "babyblog":
                raw = parse_babyblog(data)
            else:
                raw = []

            relevant = [l for l in raw if is_relevant(l["quote"], keywords)]
            print(f"[forum_hunter] {target['name']}: {len(raw)} постов, {len(relevant)} релевантных", flush=True)
            all_leads.extend(relevant)

    print(f"[forum_hunter] Скоринг {len(all_leads)} лидов...", flush=True)

    scored = []
    for lead in all_leads[:50]:  # Лимит 50 для скорости
        score = await score_intent(lead["quote"])
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
