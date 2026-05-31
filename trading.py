"""Модуль торговых инструментов для трейдера по XAUUSD."""

import json
import re
import asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

import aiohttp

TRADING_DATA_FILE = Path("/root/telegram-bot/trading_data.json")


# ── Хранилище данных ──────────────────────────────────────────────────────────

def load_trading_data() -> dict:
    if TRADING_DATA_FILE.exists():
        try:
            return json.loads(TRADING_DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"balance": None, "trades": [], "next_trade_id": 1}


def save_trading_data(data: dict) -> None:
    TRADING_DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── Получение рыночных данных ─────────────────────────────────────────────────

async def _fetch_ohlc(session: aiohttp.ClientSession) -> Optional[dict]:
    """OHLC за 5 дней, 1-часовые свечи."""
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC%3DF?interval=1h&range=5d"
        headers = {"User-Agent": "Mozilla/5.0"}
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            result = data["chart"]["result"][0]
            meta = result["meta"]
            q = result["indicators"]["quote"][0]

            closes = [c for c in q.get("close", []) if c is not None]
            highs  = [h for h in q.get("high",  []) if h is not None]
            lows   = [l for l in q.get("low",   []) if l is not None]

            if not closes:
                return {"price": float(meta["regularMarketPrice"])}

            price = float(meta["regularMarketPrice"])
            high_5d = max(highs)
            low_5d  = min(lows)
            high_24h = max(highs[-24:]) if len(highs) >= 24 else max(highs)
            low_24h  = min(lows[-24:])  if len(lows)  >= 24 else min(lows)

            # Тренд: сравниваем среднее последних 4 часов с 12-часовой давностью
            recent = closes[-4:]
            older  = closes[-16:-12] if len(closes) >= 16 else closes[:4]
            avg_r  = sum(recent) / len(recent)
            avg_o  = sum(older)  / len(older)
            if avg_r > avg_o * 1.001:
                trend = "ВОСХОДЯЩИЙ"
            elif avg_r < avg_o * 0.999:
                trend = "НИСХОДЯЩИЙ"
            else:
                trend = "БОКОВОЙ"

            return {
                "price":     price,
                "trend":     trend,
                "high_24h":  high_24h,
                "low_24h":   low_24h,
                "high_5d":   high_5d,
                "low_5d":    low_5d,
                "resistance": round(high_24h),
                "support":    round(low_24h),
                "closes_4h":  closes[-4:],
            }
    except Exception:
        return None


# ── /signal — торговый сигнал ─────────────────────────────────────────────────

def _calc_signal(ohlc: dict) -> dict:
    price      = ohlc["price"]
    trend      = ohlc.get("trend", "БОКОВОЙ")
    resistance = ohlc.get("resistance", price + 20)
    support    = ohlc.get("support",    price - 20)
    rng        = max(resistance - support, 5)
    pos        = (price - support) / rng  # 0 = у поддержки, 1 = у сопротивления

    if trend == "ВОСХОДЯЩИЙ" and pos < 0.6:
        d    = "BUY"
        entry = round(price, 1)
        stop  = round(support - 10, 1)
        take  = round(resistance - 5, 1)
        conf  = "ВЫСОКАЯ" if pos < 0.4 else "СРЕДНЯЯ"
    elif trend == "НИСХОДЯЩИЙ" and pos > 0.4:
        d    = "SELL"
        entry = round(price, 1)
        stop  = round(resistance + 10, 1)
        take  = round(support + 5, 1)
        conf  = "ВЫСОКАЯ" if pos > 0.6 else "СРЕДНЯЯ"
    else:
        d    = "НЕЙТРАЛЬНО"
        entry = round(price, 1)
        stop  = round(support - 10, 1)
        take  = round(resistance - 5, 1)
        conf  = "НИЗКАЯ"

    if d == "BUY" and entry > stop:
        rr = round((take - entry) / (entry - stop), 1)
    elif d == "SELL" and stop > entry:
        rr = round((entry - take) / (stop - entry), 1)
    else:
        rr = 0.0

    return {"direction": d, "entry": entry, "stop": stop, "take": take,
            "rr": rr, "confidence": conf, "trend": trend,
            "support": support, "resistance": resistance}


async def build_signal() -> str:
    async with aiohttp.ClientSession() as session:
        ohlc = await _fetch_ohlc(session)

    if not ohlc:
        return "⚠️ Не удалось получить данные с биржи. Проверь соединение."

    sig = _calc_signal(ohlc)
    ts  = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    d_emoji   = {"BUY": "🟢", "SELL": "🔴", "НЕЙТРАЛЬНО": "🟡"}.get(sig["direction"], "🟡")
    c_emoji   = {"ВЫСОКАЯ": "✅", "СРЕДНЯЯ": "⚡", "НИЗКАЯ": "⚠️"}.get(sig["confidence"], "⚡")

    lines = [f"📡 *ТОРГОВЫЙ СИГНАЛ XAUUSD*  _{ts}_\n",
             f"*Направление:* {d_emoji} *{sig['direction']}*",
             f"*Уверенность:* {c_emoji} {sig['confidence']}",
             f"\n*Текущая цена:* ${ohlc['price']:,.1f}"]

    if sig["direction"] != "НЕЙТРАЛЬНО":
        lines += [f"*Вход:* ${sig['entry']:,.1f}",
                  f"*Стоп:* ${sig['stop']:,.1f}",
                  f"*Тейк:* ${sig['take']:,.1f}",
                  f"*R:R:* 1:{sig['rr']}"]

    lines += [f"\n*Тренд:* {sig['trend']}",
              f"*Поддержка:* ${sig['support']:,.1f}",
              f"*Сопротивление:* ${sig['resistance']:,.1f}",
              "\n*Обоснование:*"]

    if sig["direction"] == "BUY":
        lines.append(
            f"Восходящий тренд, цена ближе к поддержке ${sig['support']:,.1f}. "
            f"Потенциал роста до ${sig['take']:,.1f}. Стоп под поддержкой."
        )
    elif sig["direction"] == "SELL":
        lines.append(
            f"Нисходящий тренд, цена у сопротивления ${sig['resistance']:,.1f}. "
            f"Потенциал снижения до ${sig['take']:,.1f}. Стоп над сопротивлением."
        )
    else:
        lines.append(
            f"Рынок в консолидации ${sig['support']:,.1f}–${sig['resistance']:,.1f}. "
            f"Жди чёткого пробоя уровня перед входом."
        )

    lines.append("\n_⚠️ Не является инвестиционной рекомендацией._")
    return "\n".join(lines)


# ── /analiz — технический анализ ─────────────────────────────────────────────

async def build_technical_analysis() -> str:
    async with aiohttp.ClientSession() as session:
        ohlc = await _fetch_ohlc(session)

    if not ohlc:
        return "⚠️ Не удалось получить рыночные данные."

    price = ohlc["price"]
    ts    = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    t_emoji = {"ВОСХОДЯЩИЙ": "📈", "НИСХОДЯЩИЙ": "📉", "БОКОВОЙ": "➡️"}.get(ohlc.get("trend", "БОКОВОЙ"), "➡️")

    lines = [f"📊 *ТЕХНИЧЕСКИЙ АНАЛИЗ XAUUSD*  _{ts}_\n",
             f"*ТРЕНД:* {t_emoji} {ohlc.get('trend', 'БОКОВОЙ')}",
             f"*Цена:* ${price:,.1f}",
             "\n*КЛЮЧЕВЫЕ УРОВНИ:*",
             f"  🔴 Сопротивление 1: ${ohlc['resistance']:,.1f}",
             f"  🔴 Сопротивление 2: ${ohlc['high_5d']:,.1f}  _(хай 5 дней)_",
             f"  🟢 Поддержка 1: ${ohlc['support']:,.1f}",
             f"  🟢 Поддержка 2: ${ohlc['low_5d']:,.1f}  _(лоу 5 дней)_"]

    rng_24 = ohlc["high_24h"] - ohlc["low_24h"]
    lines.append(f"\n*ДИАПАЗОН 24ч:* ${rng_24:.1f}  (${ohlc['low_24h']:,.1f} – ${ohlc['high_24h']:,.1f})")

    lines.append("\n*ПАТТЕРНЫ:*")
    cls = ohlc.get("closes_4h", [])
    if len(cls) >= 3:
        if cls[-1] > cls[-2] > cls[-3]:
            lines.append("  • Три последовательных роста — бычья динамика")
        elif cls[-1] < cls[-2] < cls[-3]:
            lines.append("  • Три последовательных падения — медвежья динамика")
        else:
            lines.append("  • Нет чёткого краткосрочного паттерна")
    else:
        lines.append("  • Недостаточно данных")

    lines.append("\n*ПРОГНОЗ НА 4–8 ЧАСОВ:*")
    trend = ohlc.get("trend", "БОКОВОЙ")
    if trend == "ВОСХОДЯЩИЙ":
        lines += [f"  ⬆️ Сохранение тренда → ${ohlc['resistance'] - 3:,.1f}",
                  f"  ⬇️ Пробой поддержки ${ohlc['support']:,.1f} → ${ohlc['low_5d']:,.1f}"]
    elif trend == "НИСХОДЯЩИЙ":
        lines += [f"  ⬇️ Сохранение тренда → ${ohlc['support'] + 3:,.1f}",
                  f"  ⬆️ Пробой сопротивления ${ohlc['resistance']:,.1f} → ${ohlc['high_5d']:,.1f}"]
    else:
        lines += [f"  ↔️ Диапазон ${ohlc['support']:,.1f} – ${ohlc['resistance']:,.1f}",
                  "  Торгуй от границ, стопы за уровни"]

    lines.append("\n_Данные: Yahoo Finance. Не является инвестрекомендацией._")
    return "\n".join(lines)


# ── /risk — риск-калькулятор ──────────────────────────────────────────────────

def calc_risk_report(lot: float, stop_points: float, balance: float) -> str:
    """$1 на пункт на стандартный лот XAUUSD."""
    dollar_risk  = lot * stop_points * 1.0
    percent_risk = (dollar_risk / balance) * 100 if balance > 0 else 0

    rec_1pct = round((balance * 0.01) / (stop_points), 2) if stop_points > 0 and balance > 0 else 0
    rec_2pct = round((balance * 0.02) / (stop_points), 2) if stop_points > 0 and balance > 0 else 0

    risk_emoji = "✅" if percent_risk <= 2 else "⚠️" if percent_risk <= 5 else "❌"

    lines = ["💰 *РИСК-МЕНЕДЖМЕНТ XAUUSD*\n",
             f"*Лот:* {lot}",
             f"*Стоп:* {stop_points:.0f} пунктов",
             f"*Баланс:* ${balance:,.0f}",
             "",
             f"*Риск в $:* ${dollar_risk:,.2f}",
             f"*Риск %:* {risk_emoji} *{percent_risk:.2f}%*",
             "",
             "*Рекомендуемый лот:*",
             f"  1% риска → {rec_1pct} лот",
             f"  2% риска → {rec_2pct} лот",
             ""]

    if percent_risk <= 1:
        lines.append("✅ Консервативный риск — отлично для стабильного роста")
    elif percent_risk <= 2:
        lines.append("⚡ Умеренный риск — допустимо")
    elif percent_risk <= 5:
        lines.append("⚠️ Повышенный риск — будь осторожен")
    else:
        lines.append("❌ Риск слишком высок — снизь лот")

    return "\n".join(lines)


# ── Журнал сделок ─────────────────────────────────────────────────────────────

def add_trade(data: dict, direction: str, entry: float, stop: float, take: float) -> dict:
    trade_id = data.get("next_trade_id", 1)
    trade = {
        "id":           trade_id,
        "direction":    direction.upper(),
        "entry":        entry,
        "stop":         stop,
        "take":         take,
        "opened_at":    datetime.now(timezone.utc).isoformat(),
        "closed_at":    None,
        "result_points": None,
        "status":       "OPEN",
    }
    data.setdefault("trades", []).append(trade)
    data["next_trade_id"] = trade_id + 1
    return trade


def close_trade(data: dict, trade_num: int, result_points: float) -> Optional[dict]:
    """trade_num — порядковый номер из /jurnal (1-based, только открытые)."""
    open_trades = [t for t in data.get("trades", []) if t["status"] == "OPEN"]
    if trade_num < 1 or trade_num > len(open_trades):
        return None
    target_id = open_trades[trade_num - 1]["id"]
    for t in data["trades"]:
        if t["id"] == target_id:
            t["status"]        = "CLOSED"
            t["result_points"] = result_points
            t["closed_at"]     = datetime.now(timezone.utc).isoformat()
            return t
    return None


def format_trade_journal(data: dict) -> str:
    trades = data.get("trades", [])
    if not trades:
        return "📋 Журнал пуст.\n\nЗаписать сделку: `/sdelka buy вход стоп тейк`"

    last_10 = trades[-10:]
    open_trades = [t for t in last_10 if t["status"] == "OPEN"]
    lines = ["📋 *ЖУРНАЛ СДЕЛОК XAUUSD (последние 10)*\n"]

    for i, t in enumerate(last_10, 1):
        if t["status"] == "OPEN":
            s_emoji = "🔵"
            result  = " → *ОТКРЫТА*"
        elif (t.get("result_points") or 0) > 0:
            s_emoji = "✅"
            result  = f" → *+{t['result_points']:.0f} пп*"
        else:
            s_emoji = "❌"
            result  = f" → *{t['result_points']:.0f} пп*" if t.get("result_points") is not None else ""

        d_emoji = "⬆️" if t["direction"] == "BUY" else "⬇️"
        date    = t["opened_at"][:10] if t.get("opened_at") else "?"
        lines.append(
            f"{i}. {s_emoji} {d_emoji} *{t['direction']}* "
            f"${t['entry']:,.1f} | SL ${t['stop']:,.1f} | TP ${t['take']:,.1f}"
            f"{result}  _{date}_"
        )

    if open_trades:
        nums = [str(i + 1) for i, t in enumerate(last_10) if t["status"] == "OPEN"]
        lines.append(f"\n_Открытых: {len(open_trades)} (номера: {', '.join(nums)})_")
        lines.append("_Закрыть: `/zakryt <номер> <пунктов>`_")

    return "\n".join(lines)


def format_statistics(data: dict) -> str:
    closed = [t for t in data.get("trades", [])
              if t["status"] == "CLOSED" and t.get("result_points") is not None]

    if not closed:
        return ("📊 Закрытых сделок ещё нет.\n\n"
                "Закрывай сделки через `/zakryt <номер> <пунктов>`")

    total = len(closed)
    wins  = [t for t in closed if t["result_points"] > 0]
    losses = [t for t in closed if t["result_points"] <= 0]

    winrate    = len(wins) / total * 100
    avg_win    = sum(t["result_points"] for t in wins) / len(wins) if wins else 0
    avg_loss   = abs(sum(t["result_points"] for t in losses) / len(losses)) if losses else 0
    rr         = avg_win / avg_loss if avg_loss > 0 else float("inf")
    gross_p    = sum(t["result_points"] for t in wins)
    gross_l    = abs(sum(t["result_points"] for t in losses))
    pf         = gross_p / gross_l if gross_l > 0 else float("inf")
    total_pts  = sum(t["result_points"] for t in closed)

    # Серии
    max_w = max_l = cur_w = cur_l = 0
    for t in closed:
        if t["result_points"] > 0:
            cur_w += 1; cur_l = 0; max_w = max(max_w, cur_w)
        else:
            cur_l += 1; cur_w = 0; max_l = max(max_l, cur_l)

    lines = ["📊 *СТАТИСТИКА ТОРГОВЛИ XAUUSD*\n",
             f"*Всего сделок:* {total}",
             f"*Прибыльных:* {len(wins)} | *Убыточных:* {len(losses)}",
             f"*Winrate:* {winrate:.1f}%",
             "",
             f"*Средняя прибыль:* +{avg_win:.1f} пп",
             f"*Средний убыток:* -{avg_loss:.1f} пп",
             f"*Средний R:R:* 1:{rr:.2f}",
             f"*Профит-фактор:* {pf:.2f}",
             "",
             f"*Итого:* {'+' if total_pts > 0 else ''}{total_pts:.0f} пп",
             f"*Серия побед (макс):* {max_w}",
             f"*Серия потерь (макс):* {max_l}",
             "\n*Оценка:*"]

    if winrate >= 55 and pf >= 1.5:
        lines.append("✅ Стратегия прибыльная — хорошие показатели")
    elif pf >= 1.2:
        lines.append("⚡ Стратегия работает — есть куда расти")
    elif pf < 1.0:
        lines.append("❌ Убыточная стратегия — пересмотри подход")
    else:
        lines.append("🟡 На грани окупаемости — улучшай R:R")

    return "\n".join(lines)


# ── /kod — генерация MQL4 ─────────────────────────────────────────────────────

def generate_mql4(description: str) -> str:
    short_desc = description[:60]
    return f"""```mql4
//+------------------------------------------------------------------+
//| Expert Advisor: {short_desc}
//| Инструмент: XAUUSD  |  Сгенерировано Гавриком
//+------------------------------------------------------------------+
#property strict

input double LotSize     = 0.01;    // Лот
input int    StopLoss    = 200;     // Стоп-лосс, пунктов
input int    TakeProfit  = 400;     // Тейк-профит, пунктов
input int    MagicNumber = 99001;   // Магический номер

bool IsOrderOpen() {{
   for(int i = OrdersTotal()-1; i >= 0; i--)
      if(OrderSelect(i, SELECT_BY_POS, MODE_TRADES) &&
         OrderMagicNumber() == MagicNumber &&
         OrderSymbol() == Symbol()) return true;
   return false;
}}

// === СИГНАЛ: {description} ===
// Замени эту функцию своей логикой
double GetSignal() {{
   double ma_fast      = iMA(NULL,0,8, 0,MODE_EMA,PRICE_CLOSE,0);
   double ma_slow      = iMA(NULL,0,21,0,MODE_EMA,PRICE_CLOSE,0);
   double ma_fast_prev = iMA(NULL,0,8, 0,MODE_EMA,PRICE_CLOSE,1);
   double ma_slow_prev = iMA(NULL,0,21,0,MODE_EMA,PRICE_CLOSE,1);
   if(ma_fast >  ma_slow && ma_fast_prev <= ma_slow_prev) return  1;
   if(ma_fast <  ma_slow && ma_fast_prev >= ma_slow_prev) return -1;
   return 0;
}}

void OpenOrder(int type) {{
   double price = (type==OP_BUY) ? Ask : Bid;
   double sl = (type==OP_BUY) ? price-StopLoss*Point : price+StopLoss*Point;
   double tp = (type==OP_BUY) ? price+TakeProfit*Point : price-TakeProfit*Point;
   int ticket = OrderSend(Symbol(),type,LotSize,price,3,sl,tp,"GavrikEA",MagicNumber,0,clrBlue);
   if(ticket < 0) Print("Ошибка: ", GetLastError());
}}

void OnTick() {{
   if(IsOrderOpen()) return;
   double sig = GetSignal();
   if(sig >  0) OpenOrder(OP_BUY);
   if(sig < 0) OpenOrder(OP_SELL);
}}

int  OnInit()   {{ Print("EA запущен: ", Symbol()); return INIT_SUCCEEDED; }}
void OnDeinit(const int r) {{ Print("EA остановлен."); }}
```"""


# ── /baktest — анализ бэктеста ────────────────────────────────────────────────

async def analyze_backtest(results_text: str) -> str:
    lines = ["📈 *АНАЛИЗ БЭКТЕСТА XAUUSD*\n",
             f"*Входные данные:* _{results_text[:250]}_\n"]

    issues = []
    recs   = []
    text   = results_text.lower()

    # winrate
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*%', results_text)
    if m:
        wr = float(m.group(1).replace(",", "."))
        if wr < 40:
            issues.append(f"⚠️ Низкий winrate {wr:.0f}% — теряешь больше половины сделок")
            recs  += ["• Торгуй только по направлению дневного тренда",
                      "• Добавь фильтр по RSI или MA на старшем ТФ"]
        elif wr > 75:
            issues.append(f"⚠️ Winrate {wr:.0f}% очень высок — проверь R:R, возможно тейк слишком маленький")

    # drawdown
    if any(w in text for w in ["просадк", "drawdown", " dd "]):
        issues.append("⚠️ Обнаружена просадка — ключевой риск")
        recs  += ["• Допустимая просадка для XAUUSD: до 15% депозита",
                  "• Если > 20% — сократи лот вдвое"]

    # few trades
    if any(w in text for w in ["мало", "редко", "few", "нет сделок"]):
        issues.append("⚠️ Мало сделок — статистика ненадёжна (нужно 100+)")
        recs.append("• Увеличь тестовый период или переходи на меньший ТФ")

    lines.append("*Найденные проблемы:*")
    lines += issues if issues else ["✅ Критических проблем в описании не выявлено."]

    lines.append("\n*Рекомендации:*")
    if recs:
        lines += recs
    else:
        lines += ["• Протестируй стратегию минимум на 2-х годах данных (2022–2024)",
                  "• Включи реальный спред XAUUSD (~30 пп) в расчёт",
                  "• Проверь результат на out-of-sample периоде (20% данных отдельно)",
                  "• Оптимальный R:R для XAUUSD: 1:1.5 – 1:3"]

    lines += ["\n*Правила валидного бэктеста:*",
              "• 100+ сделок",
              "• 1–2 года истории",
              "• Спред и комиссии включены",
              "• Out-of-sample проверка",
              "\n_Отправь конкретные цифры (winrate, drawdown, R:R) для детального анализа._"]

    return "\n".join(lines)


# ── Автоалерт за 15 минут до новостей ────────────────────────────────────────

_alerted_events: set[str] = set()  # предотвращаем повторные алерты


async def check_news_alerts(bot, owner_id: int) -> None:
    """Проверяет события ближайших 15 минут и шлёт алерт."""
    from gold_news import fetch_forex_factory_events, _is_gold_relevant

    now = datetime.now(timezone.utc)
    alert_window_start = now + timedelta(minutes=10)
    alert_window_end   = now + timedelta(minutes=20)

    try:
        async with aiohttp.ClientSession() as session:
            events = await fetch_forex_factory_events(session)
    except Exception:
        return

    for ev in events:
        if ev.get("impact") != "high":
            continue
        if not _is_gold_relevant(ev["title"], ev.get("currency", "")):
            continue

        event_time = ev["time"]
        if not (alert_window_start <= event_time <= alert_window_end):
            continue

        event_key = f"{ev['title']}_{event_time.isoformat()}"
        if event_key in _alerted_events:
            continue
        _alerted_events.add(event_key)

        mins_left = int((event_time - now).total_seconds() / 60)
        time_str  = event_time.strftime("%H:%M UTC")

        text = (
            f"⚡ *АЛЕРТ: ВАЖНАЯ НОВОСТЬ ЧЕРЕЗ {mins_left} МИН*\n\n"
            f"🔴 *{ev['title']}*\n"
            f"🕐 {time_str}\n"
            f"💱 {ev.get('currency', 'USD')}\n\n"
            f"Золото может сильно двинуться! "
            f"Закрой или защити открытые позиции."
        )
        try:
            await bot.send_message(chat_id=owner_id, text=text, parse_mode="Markdown")
        except Exception:
            pass
