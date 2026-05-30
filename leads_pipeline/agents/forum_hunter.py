"""
Forum Hunter Agent — парсит свежие темы (<7 дней) на целевых площадках.
Выход: массив объектов {url, author, quote, createdAt, intentScore, source}
"""

import asyncio
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

import aiohttp
import anthropic
from bs4 import BeautifulSoup

if not os.environ.get("ANTHROPIC_API_KEY"):
    env_file = Path(__file__).parent.parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


async def ask_claude(prompt: str, max_wait: int = 30) -> str:
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                lambda: _client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=256,
                    messages=[{"role": "user", "content": prompt}],
                )
            ),
            timeout=max_wait,
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"[forum_hunter] claude error: {e}", flush=True)
        return ""

ROOT = Path(__file__).parent.parent.parent
INPUT_FILE = ROOT / "leads_pipeline" / "raw_keywords.json"
OUTPUT_FILE = ROOT / "leads_pipeline" / "raw_leads.json"

TARGETS = [
    {
        "name": "pikabu_otnosheniya",
        "url_template": "https://pikabu.ru/tag/%D0%BE%D1%82%D0%BD%D0%BE%D1%88%D0%B5%D0%BD%D0%B8%D1%8F/hot?page={page}",
        "pages": 5,
        "parser": "pikabu",
    },
    {
        "name": "pikabu_semya",
        "url_template": "https://pikabu.ru/tag/%D1%81%D0%B5%D0%BC%D1%8C%D1%8F/hot?page={page}",
        "pages": 5,
        "parser": "pikabu",
    },
    {
        "name": "woman_psyche",
        "url_template": "https://www.woman.ru/psyche/medley/?p={page}",
        "pages": 5,
        "parser": "woman",
    },
    {
        "name": "woman_relations",
        "url_template": "https://www.woman.ru/relations/medley/?p={page}",
        "pages": 5,
        "parser": "woman",
    },
    {
        "name": "reddit",
        "url": "https://www.reddit.com/r/relationships/.json?limit=100&t=week",
        "is_json": True,
        "pages": 1,
        "parser": "reddit",
    },
    {
        "name": "babyblog_family",
        "url_template": "https://www.babyblog.ru/community/family?page={page}",
        "pages": 5,
        "parser": "babyblog",
    },
    {
        "name": "babyblog_psychology",
        "url_template": "https://www.babyblog.ru/community/psychology?page={page}",
        "pages": 5,
        "parser": "babyblog",
    },
]

INTENT_PROMPT = """Оцени интент автора найти профессиональную психологическую помощь по шкале 0–100.

Текст: "{text}"

Ответь только числом от 0 до 100. 100 = человек прямо ищет психолога или терапевта. 0 = просто делится историей без запроса помощи."""


BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


async def fetch(session: aiohttp.ClientSession, url: str, is_json: bool = False, referer: str = "") -> str | dict | None:
    headers = dict(BROWSER_HEADERS)
    if referer:
        headers["Referer"] = referer
    if "woman.ru" in url:
        headers["Referer"] = "https://www.woman.ru/"
        headers["Cookie"] = "user_region=ru; _ga=GA1.2.1; visited=1"
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status != 200:
                print(f"[forum_hunter] HTTP {resp.status} {url}", flush=True)
                return None
            return await resp.json() if is_json else await resp.text()
    except Exception as e:
        print(f"[forum_hunter] fetch error {url}: {e}", flush=True)
        return None


async def fetch_woman_via_google(session: aiohttp.ClientSession, section: str) -> list[dict]:
    """Ищет woman.ru через Google, обходя защиту от прямого парсинга."""
    query = f"site:woman.ru/{section} муж жена брак развод измена психолог"
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}&num=20&hl=ru"
    headers = dict(BROWSER_HEADERS)
    headers["Referer"] = "https://www.google.com/"
    leads = []
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return leads
            html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")
        for g in soup.select("div.g")[:20]:
            link_el = g.select_one("a[href]")
            title_el = g.select_one("h3")
            snippet_el = g.select_one("div.VwiC3b, span.aCOpRe, div[data-sncf]")
            if not link_el or not title_el:
                continue
            href = link_el["href"]
            if not href.startswith("https://www.woman.ru"):
                continue
            title = title_el.get_text(strip=True)
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            quote = f"{title}. {snippet}".strip(". ")
            if len(quote) < 15:
                continue
            leads.append({
                "url": href,
                "author": "woman.ru reader",
                "quote": quote[:400],
                "source": "woman.ru",
                "createdAt": datetime.now().isoformat(),
            })
    except Exception as e:
        print(f"[forum_hunter] google/woman.ru error: {e}", flush=True)
    return leads


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

    # Пробуем разные селекторы — woman.ru меняла вёрстку несколько раз
    SELECTORS = [
        ("a.thread.forum-threads__thread", ".thread__title", None),
        ("article.article-preview", "h2,h3,.article__title", ".article__author"),
        ("div.article-card", "h2,h3,.article-card__title", None),
        (".item-preview", "h2,h3", None),
    ]

    for sel, title_sel, author_sel in SELECTORS:
        items = soup.select(sel)[:30]
        if not items:
            continue
        for item in items:
            href = item.get("href", "") or (item.select_one("a") or {}).get("href", "")
            title_el = item.select_one(title_sel) if title_sel else None
            title = title_el.get_text(strip=True) if title_el else item.get_text(strip=True)[:200]
            if not title or len(title) < 10:
                continue
            author = "woman.ru reader"
            if author_sel:
                a_el = item.select_one(author_sel)
                if a_el:
                    author = a_el.get_text(strip=True)[:50] or author
            url = href if href.startswith("http") else ("https://www.woman.ru" + href if href else "https://www.woman.ru")
            leads.append({
                "url": url,
                "author": author,
                "quote": title,
                "source": "woman.ru",
                "createdAt": datetime.now().isoformat(),
            })
        if leads:
            break

    # Финальный fallback — ищем любые ссылки с длинным текстом
    if not leads:
        for a in soup.find_all("a", href=True)[:60]:
            text = a.get_text(strip=True)
            if len(text) > 20:
                href = a["href"]
                url = href if href.startswith("http") else "https://www.woman.ru" + href
                leads.append({
                    "url": url,
                    "author": "woman.ru reader",
                    "quote": text[:300],
                    "source": "woman.ru",
                    "createdAt": datetime.now().isoformat(),
                })

    return leads[:30]


def parse_babyblog(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    leads = []
    for item in soup.select("article.postCard")[:20]:
        link = item.find("a", href=lambda h: h and "/post/" in h)
        title_el = item.find(class_=lambda c: c and "title" in c.lower() if c else False)
        text_el = item.find(class_=lambda c: c and ("text" in c.lower() or "content" in c.lower()) if c else False)
        author_el = item.find(class_=lambda c: c and "author" in c.lower() if c else False)
        href = link.get("href", "") if link else ""
        if href and not href.startswith("http"):
            href = "https://www.babyblog.ru" + href
        quote = ""
        if title_el:
            quote = title_el.get_text(strip=True)[:300]
        elif text_el:
            quote = text_el.get_text(strip=True)[:300]
        if not quote:
            continue
        author = author_el.get_text(strip=True).split("→")[0].strip() if author_el else "babyblog reader"
        leads.append({
            "url": href or "https://www.babyblog.ru",
            "author": author[:50],
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


# Психологический словарь для babyblog/psychology — язык самоанализа, не прямых кризисов
PSYCHOLOGY_MARKERS = [
    "не чувствую близости", "эмоциональная холодность", "одиночество в браке",
    "не понимаем друг друга", "потеряла себя", "потерял себя", "боюсь развода",
    "отдалились друг от друга", "нет эмоциональной связи", "живём как чужие",
    "не общаемся", "холодность в отношениях", "нет близости", "потеря интереса",
    "разные ценности", "несовместимость", "не слышит меня", "не слышу его",
    "не понимает", "устала бороться", "нет взаимопонимания", "эмоциональное выгорание",
    "хочу измениться", "хочу наладить отношения", "работа над собой в браке",
    "потеряли тепло", "пропало уважение", "нет доверия", "нужна помощь",
]

# Маркеры — достаточно одного из них
STRONG_MARKERS = [
    "измена", "развод", "кризис в браке", "не понимаем друг друга",
    "хочу развестись", "муж изменил", "жена изменила", "расстаёмся",
    "нужна помощь психолога", "семейный психолог", "потеряли близость",
    "ругаемся каждый день", "не могу простить", "предательство",
    "хочу сохранить брак", "разлюбил", "разлюбила", "на грани развода",
    "бывший муж", "бывшая жена", "расстались", "не живём вместе",
    "муж ушёл", "жена ушла", "не общается с ребёнком", "раздельное проживание",
]

# Мягкие ключевые слова — нужно минимум 2
SOFT_KEYWORDS = [
    "муж", "жена", "брак", "семья", "ребёнок", "дети", "отношения",
    "психолог", "конфликт", "ссора", "обида", "измена", "развод",
    "кризис", "расстались", "разлучились", "не понимает",
]


def load_keywords() -> list[str]:
    if INPUT_FILE.exists():
        data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
        return data.get("keywords", []) + data.get("high_intent_phrases", [])
    return ["измена", "развод", "кризис", "психолог", "семейные проблемы"]


def is_relevant(text: str, keywords: list[str], source_name: str = "") -> bool:
    text_lower = text.lower()
    # Для babyblog/psychology — проверяем психологический словарь
    if source_name == "babyblog_psychology":
        if any(m in text_lower for m in PSYCHOLOGY_MARKERS):
            return True
        # Ещё вариант: 1 сильный маркер тоже подойдёт
        return any(m in text_lower for m in STRONG_MARKERS)
    # 1 сильного маркера достаточно
    if any(m in text_lower for m in STRONG_MARKERS):
        return True
    # Или 2 мягких ключевых слова из SOFT_KEYWORDS
    soft_hits = sum(1 for kw in SOFT_KEYWORDS if kw in text_lower)
    if soft_hits >= 2:
        return True
    # Или 2 Scout-ключевых слова (из файла raw_keywords.json)
    kw_hits = sum(1 for kw in keywords if kw.lower() in text_lower)
    return kw_hits >= 2


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
            name = target["name"]
            pages = target.get("pages", 1)
            is_json = target.get("is_json", False)
            target_total_raw = 0
            target_total_rel = 0

            # woman.ru: сначала пробуем прямой парсинг, если 0 — Google-фоллбэк
            if target.get("parser") == "woman":
                raw = []
                for page in range(1, pages + 1):
                    url = target["url_template"].format(page=page)
                    print(f"[forum_hunter] {name} стр.{page}/{pages}...", flush=True)
                    data = await fetch(session, url)
                    if data:
                        raw.extend(parse_woman(data))
                    await asyncio.sleep(0.7)
                if not raw:
                    print(f"[forum_hunter] {name}: прямой парсинг не дал результатов, пробуем Google...", flush=True)
                    section = "psyche" if "psyche" in name else "relations"
                    raw = await fetch_woman_via_google(session, section)
                target_total_raw = len(raw)
                relevant = [l for l in raw if is_relevant(l["quote"], keywords, name)]
                target_total_rel = len(relevant)
                all_leads.extend(relevant)
                print(f"[forum_hunter] {name}: {target_total_raw} постов, {target_total_rel} релевантных", flush=True)
                continue

            for page in range(1, pages + 1):
                if "url_template" in target:
                    url = target["url_template"].format(page=page)
                else:
                    url = target["url"]

                print(f"[forum_hunter] {name} стр.{page}/{pages}...", flush=True)
                data = await fetch(session, url, is_json)
                if not data:
                    break

                parser = target.get("parser", name)
                if parser == "pikabu":
                    raw = parse_pikabu(data)
                elif parser == "reddit":
                    raw = parse_reddit(data)
                elif parser == "babyblog":
                    raw = parse_babyblog(data)
                else:
                    raw = []

                relevant = [l for l in raw if is_relevant(l["quote"], keywords, name)]
                target_total_raw += len(raw)
                target_total_rel += len(relevant)
                all_leads.extend(relevant)

                if not raw:
                    break
                await asyncio.sleep(0.5)

            print(f"[forum_hunter] {name}: {target_total_raw} постов, {target_total_rel} релевантных", flush=True)

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
