"""
VK Agent — парсит ВКонтакте через официальный API.
Ищет в публичных группах комментарии/посты с запросом на психологическую помощь.
Выход: raw_leads.json (мерж с Monitor/Forum Hunter)
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import aiohttp

if not os.environ.get("VK_AGENT_TOKEN"):
    env_file = Path(__file__).parent.parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

# Берём токен из env или используем hardcoded (из MEMORY.md)
VK_TOKEN = os.environ.get("VK_AGENT_TOKEN") or os.environ.get("MISEMIA_VK_TOKEN") or (
    "vk1.a.YFF8UZFvLL8zIohjynppNbajzIlxIjt8drGwoDnu6NSxVWoHK42MV2403fnxLyk0"
    "VOLfTrdhAGXRRKWtaDQTZhrIKEvPTqpAa9mcwHZbdTFumK1v52FPjUmmuCyg9ZZtl_Kdc2"
    "Dg1sPoDzRinYBh2eFm4mWQQMxjjQR9NujCYNrYsKVk9RinxxPp2x9Rfd9DN-Tyf27hQ6wz"
    "naHiQS9HyQ"
)
VK_API = "https://api.vk.com/method"
VK_V = "5.199"

ROOT = Path(__file__).parent.parent.parent
INPUT_FILE = ROOT / "leads_pipeline" / "raw_keywords.json"
OUTPUT_FILE = ROOT / "leads_pipeline" / "raw_leads.json"

# Группы ВКонтакте — психология, отношения, семья
TARGET_GROUPS = [
    "psychologies",        # Psychologies Magazine
    "psy_online",          # Психология онлайн
    "semeinaya_psihologiya",
    "psihologiya_zhizni",
    "otnosheniya_i_semya",
    "depressiya_i_trevoga",
    "psy_help_online",
    "lichnaya_zhizn",
]

# Поиск по этим запросам через wall.search
SEARCH_QUERIES = [
    "нужна консультация психолога",
    "помогите не знаю что делать",
    "ищу психолога",
    "как справиться с тревогой",
    "муж изменил что делать",
    "хочу развестись помогите",
    "депрессия не могу жить",
    "как наладить отношения",
]

HELP_MARKERS = [
    "помогите", "что делать", "посоветуйте", "как быть",
    "не знаю куда", "ищу помощь", "нужен совет", "совсем плохо",
    "не могу", "сил нет", "устала", "устал", "хочу уйти",
    "ищу психолога", "нужна консультация",
]

THEME_KEYWORDS = [
    "психолог", "психотерапевт", "развод", "измена", "тревога", "депрессия",
    "отношения", "муж", "жена", "семья", "ребёнок", "конфликт", "стресс",
    "панические атаки", "невроз", "эмоции", "чувства",
]


def load_keywords() -> list[str]:
    if INPUT_FILE.exists():
        data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
        return data.get("keywords", []) + data.get("high_intent_phrases", [])
    return THEME_KEYWORDS


def is_help_seeking(text: str, keywords: list[str]) -> bool:
    text_lower = text.lower()
    has_theme = any(kw.lower() in text_lower for kw in keywords + THEME_KEYWORDS)
    has_help = any(m in text_lower for m in HELP_MARKERS)
    return has_theme and has_help


def intent_score(text: str) -> int:
    text_lower = text.lower()
    score = 0
    for m in HELP_MARKERS:
        if m in text_lower:
            score += 1
    if "психолог" in text_lower or "консультация" in text_lower:
        score += 2
    return min(score, 5)


async def vk_get(session: aiohttp.ClientSession, method: str, params: dict) -> dict:
    params.update({"access_token": VK_TOKEN, "v": VK_V})
    async with session.get(f"{VK_API}/{method}", params=params, timeout=aiohttp.ClientTimeout(total=15)) as r:
        return await r.json()


async def search_posts(session: aiohttp.ClientSession, query: str, keywords: list[str]) -> list[dict]:
    leads = []
    week_ago = int((datetime.now() - timedelta(days=7)).timestamp())
    try:
        data = await vk_get(session, "newsfeed.search", {
            "q": query,
            "count": 50,
            "start_time": week_ago,
            "extended": 0,
        })
        items = data.get("response", {}).get("items", [])
        for post in items:
            text = post.get("text", "")
            if not text or len(text) < 30:
                continue
            if not is_help_seeking(text, keywords):
                continue
            owner_id = post.get("owner_id", 0)
            post_id = post.get("id", 0)
            url = f"https://vk.com/wall{owner_id}_{post_id}"
            leads.append({
                "url": url,
                "author": str(abs(owner_id)),
                "quote": text[:400],
                "createdAt": datetime.fromtimestamp(post.get("date", 0)).isoformat(),
                "intentScore": intent_score(text),
                "source": "vk_newsfeed",
                "query": query,
            })
    except Exception as e:
        print(f"[vk_agent] newsfeed.search '{query}': {e}", flush=True)
    return leads


async def scan_group_wall(session: aiohttp.ClientSession, group: str, keywords: list[str]) -> list[dict]:
    leads = []
    week_ago = int((datetime.now() - timedelta(days=7)).timestamp())
    try:
        data = await vk_get(session, "wall.get", {
            "domain": group,
            "count": 100,
            "filter": "all",
        })
        items = data.get("response", {}).get("items", [])
        for post in items:
            if post.get("date", 0) < week_ago:
                continue
            text = post.get("text", "")
            if not text or len(text) < 30:
                continue
            if not is_help_seeking(text, keywords):
                continue
            owner_id = post.get("owner_id", 0)
            post_id = post.get("id", 0)
            leads.append({
                "url": f"https://vk.com/wall{owner_id}_{post_id}",
                "author": group,
                "quote": text[:400],
                "createdAt": datetime.fromtimestamp(post.get("date", 0)).isoformat(),
                "intentScore": intent_score(text),
                "source": f"vk_group_{group}",
            })
        # Комментарии к топовым постам
        for post in items[:10]:
            post_id = post.get("id")
            owner_id = post.get("owner_id")
            if not post_id or not owner_id:
                continue
            try:
                cdata = await vk_get(session, "wall.getComments", {
                    "owner_id": owner_id,
                    "post_id": post_id,
                    "count": 100,
                    "sort": "desc",
                })
                for c in cdata.get("response", {}).get("items", []):
                    ctext = c.get("text", "")
                    if not ctext or len(ctext) < 20:
                        continue
                    if not is_help_seeking(ctext, keywords):
                        continue
                    leads.append({
                        "url": f"https://vk.com/wall{owner_id}_{post_id}",
                        "author": str(c.get("from_id", "")),
                        "quote": ctext[:400],
                        "createdAt": datetime.fromtimestamp(c.get("date", 0)).isoformat(),
                        "intentScore": intent_score(ctext),
                        "source": f"vk_comment_{group}",
                    })
            except Exception:
                pass
    except Exception as e:
        print(f"[vk_agent] wall.get '{group}': {e}", flush=True)
    return leads


def merge_leads(existing: list[dict], new_leads: list[dict]) -> list[dict]:
    existing_urls = {l["url"] for l in existing}
    added = 0
    for lead in new_leads:
        if lead["url"] not in existing_urls:
            existing.append(lead)
            existing_urls.add(lead["url"])
            added += 1
    return existing, added


async def run():
    print("[vk_agent] Старт VK Agent", flush=True)

    if not VK_TOKEN:
        print("[vk_agent] VK токен не найден — установи VK_AGENT_TOKEN в .env", flush=True)
        return

    keywords = load_keywords()
    all_leads: list[dict] = []

    async with aiohttp.ClientSession() as session:
        # 1. Поиск по запросам через newsfeed
        tasks = [search_posts(session, q, keywords) for q in SEARCH_QUERIES]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                all_leads.extend(r)

        # 2. Сканирование стен групп
        group_tasks = [scan_group_wall(session, g, keywords) for g in TARGET_GROUPS]
        group_results = await asyncio.gather(*group_tasks, return_exceptions=True)
        for r in group_results:
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

    print(f"[vk_agent] Готово: найдено {len(all_leads)}, добавлено новых {added}, всего в файле {len(merged)}", flush=True)


if __name__ == "__main__":
    asyncio.run(run())
