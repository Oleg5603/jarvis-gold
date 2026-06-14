"""
Модуль новостного монитора для трейдера по золоту (XAUUSD).
Источник данных: Investing.com economic calendar (scraping) + Yahoo Finance для цены.
"""

import asyncio
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

import aiohttp

# Ключевые события, влияющие на золото
GOLD_KEYWORDS = {
    "nfp", "non-farm", "payroll", "cpi", "inflation", "pce", "fed", "fomc",
    "interest rate", "rate decision", "powell", "gdp", "unemployment", "jobless",
    "retail sales", "ppi", "durable goods", "ism", "michigan", "consumer confidence",
    "treasury", "dollar", "dxy", "geopolit", "war", "conflict", "sanction",
    "gold", "silver", "oil", "crude", "commodity",
}

IMPACT_EMOJI = {"high": "🔴", "medium": "🟡", "low": "⚪"}


async def fetch_forex_factory_events(session: aiohttp.ClientSession) -> list[dict]:
    """Парсит события с ForexFactory через их JSON API."""
    today = datetime.now(timezone.utc)
    tomorrow = today + timedelta(days=1)

    events = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/javascript, */*",
        "Referer": "https://www.forexfactory.com/calendar",
    }

    for day_offset, target_date in enumerate([today, tomorrow]):
        date_str = target_date.strftime("%b%d.%Y").lower()
        url = f"https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    continue
                data = await resp.json(content_type=None)
                for item in data:
                    try:
                        event_date_str = item.get("date", "")
                        event_dt = datetime.fromisoformat(event_date_str.replace("Z", "+00:00"))
                        if event_dt.date() == target_date.date():
                            title = item.get("title", "")
                            currency = item.get("country", "")
                            impact = item.get("impact", "low").lower()
                            events.append({
                                "time": event_dt,
                                "title": title,
                                "currency": currency,
                                "impact": impact,
                                "day_offset": day_offset,
                            })
                    except Exception:
                        continue
            break  # Один запрос — вся неделя
        except Exception:
            continue

    return events


def _is_gold_relevant(title: str, currency: str) -> bool:
    """Определяет, влияет ли событие на золото."""
    text = (title + " " + currency).lower()
    # USD события всегда влияют на золото
    if currency.upper() in ("USD", "US"):
        return True
    # Геополитика и глобальные события
    for kw in GOLD_KEYWORDS:
        if kw in text:
            return True
    return False


def _translate_event(title: str) -> str:
    """Переводит/адаптирует названия событий для трейдера."""
    translations = {
        "Non-Farm Payrolls": "NFP — Число занятых вне с/х",
        "CPI": "CPI — Индекс потребительских цен",
        "Core CPI": "Core CPI — Базовый CPI",
        "PCE Price Index": "PCE — Индекс расходов на личное потребление",
        "FOMC": "FOMC — Заседание ФРС",
        "Fed Interest Rate Decision": "ФРС — Решение по ставке",
        "Initial Jobless Claims": "Первичные заявки на пособие по безработице",
        "GDP": "ВВП США",
        "Retail Sales": "Розничные продажи",
        "PPI": "PPI — Индекс цен производителей",
        "ISM Manufacturing PMI": "ISM — PMI в производстве",
        "ISM Services PMI": "ISM — PMI в секторе услуг",
        "Michigan Consumer Sentiment": "Индекс настроений потребителей Michigan",
        "Durable Goods Orders": "Заказы на товары длительного пользования",
        "ADP Nonfarm Employment": "ADP — Занятость в частном секторе",
        "Unemployment Rate": "Уровень безработицы",
        "Average Hourly Earnings": "Средний часовой заработок",
    }
    for en, ru in translations.items():
        if en.lower() in title.lower():
            return ru
    return title


async def get_gold_price(session: aiohttp.ClientSession) -> Optional[float]:
    """Получает текущую цену золота через Yahoo Finance."""
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC%3DF?interval=1m&range=1d"
        headers = {"User-Agent": "Mozilla/5.0"}
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
            return float(price)
    except Exception:
        return None


async def get_dxy(session: aiohttp.ClientSession) -> Optional[float]:
    """Получает текущий индекс доллара DXY."""
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB?interval=1m&range=1d"
        headers = {"User-Agent": "Mozilla/5.0"}
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
            return float(price)
    except Exception:
        return None


async def get_gold_change(session: aiohttp.ClientSession) -> Optional[tuple[float, float]]:
    """Возвращает (цена, изменение_в_процентах) за сегодня."""
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC%3DF?interval=1d&range=5d"
        headers = {"User-Agent": "Mozilla/5.0"}
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            result = data["chart"]["result"][0]
            meta = result["meta"]
            price = float(meta["regularMarketPrice"])
            prev_close = float(meta.get("chartPreviousClose", meta.get("previousClose", price)))
            change_pct = ((price - prev_close) / prev_close) * 100 if prev_close else 0
            return price, change_pct
    except Exception:
        return None


def _format_events_for_report(events: list[dict], today_only: bool = False) -> str:
    """Форматирует список событий в читаемый текст."""
    if not events:
        return "  Нет значимых событий."

    lines = []
    for ev in events:
        impact_icon = IMPACT_EMOJI.get(ev["impact"], "⚪")
        time_str = ev["time"].strftime("%H:%M UTC")
        title_ru = _translate_event(ev["title"])
        currency = ev.get("currency", "")
        currency_str = f"[{currency}] " if currency else ""
        lines.append(f"  {impact_icon} {time_str} — {currency_str}{title_ru}")

    return "\n".join(lines)


async def build_news_report() -> str:
    """Формирует отчёт о ближайших событиях, влияющих на золото."""
    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime("%d.%m.%Y")
    tomorrow_str = (now_utc + timedelta(days=1)).strftime("%d.%m.%Y")

    async with aiohttp.ClientSession() as session:
        events = await fetch_forex_factory_events(session)

    # Фильтруем только релевантные и высокое/среднее влияние
    relevant = [
        e for e in events
        if _is_gold_relevant(e["title"], e.get("currency", ""))
        and e["impact"] in ("high", "medium")
    ]

    today_events = [e for e in relevant if e["day_offset"] == 0]
    tomorrow_events = [e for e in relevant if e["day_offset"] == 1]

    lines = ["📅 *ЭКОНОМИЧЕСКИЙ КАЛЕНДАРЬ — ЗОЛОТО (XAUUSD)*\n"]

    lines.append(f"*Сегодня, {today_str}:*")
    if today_events:
        lines.append(_format_events_for_report(today_events))
    else:
        lines.append("  ✅ Крупных событий нет — спокойный день.")

    lines.append(f"\n*Завтра, {tomorrow_str}:*")
    if tomorrow_events:
        lines.append(_format_events_for_report(tomorrow_events))
    else:
        lines.append("  ✅ Крупных событий нет.")

    lines.append("\n🔴 Высокий импакт  🟡 Средний импакт")
    lines.append("_Источник: ForexFactory Economic Calendar_")

    if not today_events and not tomorrow_events:
        lines.append(
            "\n⚠️ Данные временно недоступны или событий нет. "
            "Проверь вручную: forexfactory.com/calendar"
        )

    return "\n".join(lines)


async def build_gold_analysis() -> str:
    """Формирует краткий анализ текущей ситуации по золоту."""
    async with aiohttp.ClientSession() as session:
        gold_data, dxy = await asyncio.gather(
            get_gold_change(session),
            get_dxy(session),
        )

    lines = ["📊 *АНАЛИЗ XAUUSD — ТЕКУЩАЯ СИТУАЦИЯ*\n"]

    # Цена и изменение
    if gold_data:
        price, change_pct = gold_data
        if change_pct > 0:
            trend_icon = "📈"
            trend_word = f"+{change_pct:.2f}% — растёт"
        elif change_pct < 0:
            trend_icon = "📉"
            trend_word = f"{change_pct:.2f}% — падает"
        else:
            trend_icon = "➡️"
            trend_word = "0.00% — без изменений"

        lines.append(f"*Цена:* {trend_icon} ${price:,.2f} ({trend_word} к закрытию вчера)")
    else:
        lines.append("*Цена:* данные временно недоступны (проверь TradingView)")

    # DXY
    if dxy:
        lines.append(f"*DXY (индекс $):* {dxy:.2f}")
        dxy_note = "— давит на золото 🔽" if dxy > 104 else "— поддерживает золото 🔼" if dxy < 101 else "— нейтрален ➡️"
        lines.append(f"  {dxy_note}")
    else:
        lines.append("*DXY:* данные недоступны")

    # Сентимент
    if gold_data:
        price, change_pct = gold_data
        if change_pct > 0.3:
            sentiment = "🟢 *Сентимент: БЫЧИЙ*"
            sentiment_note = "Покупатели контролируют рынок. Смотри на пробой ближайшего сопротивления."
        elif change_pct < -0.3:
            sentiment = "🔴 *Сентимент: МЕДВЕЖИЙ*"
            sentiment_note = "Продавцы давят. Следи за ближайшей поддержкой."
        else:
            sentiment = "🟡 *Сентимент: НЕЙТРАЛЬНЫЙ*"
            sentiment_note = "Рынок в консолидации. Жди пробоя или важного события."
        lines.append(f"\n{sentiment}")
        lines.append(sentiment_note)

    # Ключевые факторы
    lines.append("\n*Ключевые факторы дня:*")
    factors = [
        "• DXY: обратная корреляция с золотом — рост доллара = давление на XAU",
        "• Ставки ФРС: высокие ставки = слабее золото (нет дивидендов)",
        "• Геополитика: любая напряжённость = спрос на защитный актив",
        "• Инфляционные данные (CPI/PCE): высокая инфляция = интерес к золоту",
    ]
    lines.extend(factors)

    lines.append("\n_Данные: Yahoo Finance. Анализ не является инвестрекомендацией._")

    return "\n".join(lines)


async def build_morning_brief() -> str:
    """Утренняя сводка: события + краткая обстановка."""
    events_report, gold_analysis = await asyncio.gather(
        build_news_report(),
        build_gold_analysis(),
    )
    now_str = datetime.now(timezone.utc).strftime("%d.%m.%Y")
    header = f"☀️ *УТРЕННЯЯ СВОДКА ПО ЗОЛОТУ — {now_str}*\n{'─'*30}\n"
    return header + events_report + "\n\n" + "─" * 30 + "\n" + gold_analysis
