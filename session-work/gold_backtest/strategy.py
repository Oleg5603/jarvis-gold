"""
Побарная (bar-by-bar) симуляция трёх вариантов стратегии MA2MA_MID,
портированных с MQL4-исходников:

  1. baseline  — MA2MA_MID.mq4       : SMA FAST/SLOW кроссовер + MID-фильтр
                                        направления + ATR-фильтр входа +
                                        SL/TP/безубыток (breakeven) на ATR.
  2. adx       — MA2MA_MID_ADX.mq4   : то же + вход разрешён только если
                                        ADX(14) строго растёт 4 закрытых бара подряд.
  3. no_atr    — MA2MA_MID_NOATR.mq4 : тот же вход (кроссовер + MID-фильтр),
                                        БЕЗ ATR-риска: нет SL/TP/БУ, выход
                                        только по противоположному кроссоверу.
  4. atrrise   — MA2_ATRRise.mq4     : SMA FAST/MID кроссовер (2 MA, без
                                        SLOW и без MID-фильтра направления),
                                        вход разрешён опционально (USE_ATR_FILTER)
                                        только если ATR строго растёт последние
                                        atr_rise_bars закрытых баров. SL/безубыток
                                        на ATR, ТЕЙК-ПРОФИТА НЕТ — выход только по
                                        обратному кроссоверу. См. run_backtest_atrrise().

Логика "bar-by-bar", а не векторизованная, потому что есть состояние,
зависящее от истории пути (path-dependent state): открыта ли позиция,
сработал ли перевод в безубыток (breakeven) для текущей сделки, и т.д.
Всё это невозможно корректно посчитать одной векторной операцией.

Все сигналы читаются со СЛЕДУЮЩЕГО после закрытия бара (эквивалент
MQL4-кода, где OnTick() на новом баре читает Close[1], MAFast(1)/(2)
и т.д. — то есть индикаторы уже закрытых баров, без заглядывания вперёд
(no look-ahead)).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

import indicators as ind


@dataclass
class Trade:
    side: str  # "buy" / "sell"
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: pd.Timestamp | None = None
    exit_price: float | None = None
    exit_reason: str | None = None  # "cross", "sl", "tp", "eod"
    pnl: float | None = None


@dataclass
class Params:
    fast: int = 8
    slow: int = 30
    mid: int = 20
    atr_period: int = 14
    atr_min: float = 0.5
    sl_mult: float = 1.0
    be_trig_mult: float = 1.5
    tp_k: float = 3.0
    tp_base: float = 4.5
    adx_period: int = 14
    # --- MA2_ATRRise (4-й вариант) ---
    atr_rise_bars: int = 4
    use_atr_filter: bool = True


def _prepare_indicators(df: pd.DataFrame, p: Params, need_atr: bool, need_adx: bool,
                         atr_cache: pd.Series | None = None,
                         adx_cache: pd.Series | None = None) -> pd.DataFrame:
    out = df.copy().reset_index(drop=True)
    out["ma_fast"] = ind.sma(out["close"], p.fast)
    out["ma_slow"] = ind.sma(out["close"], p.slow)
    out["ma_mid"] = ind.sma(out["close"], p.mid)
    if need_atr:
        out["atr"] = atr_cache if atr_cache is not None else ind.atr(out["high"], out["low"], out["close"], p.atr_period)
    if need_adx:
        out["adx"] = adx_cache if adx_cache is not None else ind.adx(out["high"], out["low"], out["close"], p.adx_period)
    return out


def _cross_signals(out: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """crossUp/crossDn эквивалентны MQL4:
    fastPrev<=slowPrev & fastCur>slowCur (crossUp), проверяется на баре i
    для fastCur=ma_fast[i-1], slowCur=ma_slow[i-1] (последний закрытый бар),
    fastPrev/slowPrev = сдвиг ещё на 1 назад — т.е. i-2.
    Сигнал "виден" и торгуется НА баре i (открытие по цене этого бара),
    так же как в MT4 OnTick() на новом баре i использует shift=1,2
    (предыдущие закрытые бары), и открывает сделку по текущей рыночной цене.
    Мы аппроксимируем цену исполнения как open бара i (первая доступная
    цена после того, как сигнал стал известен).
    """
    fast = out["ma_fast"].to_numpy()
    slow = out["ma_slow"].to_numpy()
    n = len(out)
    cross_up = np.zeros(n, dtype=bool)
    cross_dn = np.zeros(n, dtype=bool)
    # i индексирует бар исполнения; fastCur/slowCur = i-1 (last closed), prev = i-2
    for i in range(2, n):
        fc, sc = fast[i - 1], slow[i - 1]
        fp, sp = fast[i - 2], slow[i - 2]
        if np.isnan(fc) or np.isnan(sc) or np.isnan(fp) or np.isnan(sp):
            continue
        if fp <= sp and fc > sc:
            cross_up[i] = True
        elif fp >= sp and fc < sc:
            cross_dn[i] = True
    return cross_up, cross_dn


def run_backtest(df: pd.DataFrame, p: Params, variant: str = "baseline",
                  atr_cache: pd.Series | None = None,
                  adx_cache: pd.Series | None = None) -> list[Trade]:
    """variant: 'baseline' | 'adx' | 'no_atr'

    atr_cache/adx_cache: опционально — предрассчитанные серии ATR/ADX
    (т.к. в переборе параметров atr_period/adx_period фиксированы и не
    зависят от fast/slow/mid, их можно посчитать один раз и переиспользовать
    для всех комбинаций — сильно ускоряет optimize.py).
    """
    need_atr = variant in ("baseline", "adx")
    need_adx = variant == "adx"
    out = _prepare_indicators(df, p, need_atr, need_adx, atr_cache, adx_cache)
    cross_up, cross_dn = _cross_signals(out)

    n = len(out)
    times = out["time"].to_numpy()
    opens = out["open"].to_numpy()
    highs = out["high"].to_numpy()
    lows = out["low"].to_numpy()
    mid = out["ma_mid"].to_numpy()
    close_prev = out["close"].to_numpy()  # close[i-1] used via shift below
    atr_arr = out["atr"].to_numpy() if need_atr else None
    adx_arr = out["adx"].to_numpy() if need_adx else None

    trades: list[Trade] = []
    position = None  # dict with side, entry_price, sl, tp, be_done, trade(Trade)

    def adx_rising(i: int) -> bool:
        # использует ADX закрытых баров i-1..i-4 (аналог ADXNow(1..4) в MQL4,
        # где shift=1 = последний закрытый бар относительно текущего OnTick)
        if i - 4 < 0:
            return False
        a0 = adx_arr[i - 1]
        a1 = adx_arr[i - 2]
        a2 = adx_arr[i - 3]
        a3 = adx_arr[i - 4]
        if any(np.isnan(x) for x in (a0, a1, a2, a3)):
            return False
        return a3 < a2 < a1 < a0

    for i in range(2, n):
        bar_open = opens[i]
        bar_high = highs[i]
        bar_low = lows[i]
        bar_time = times[i]

        # 1) Внутрибарное управление открытой позицией: SL/TP/breakeven
        #    (только для вариантов с ATR-риском). Проверяем ДО обработки
        #    нового сигнала кроссовера на этом же баре — так же, как в MQL4
        #    ManageBreakeven вызывается каждый тик до проверки нового бара,
        #    но SL/TP исполняет сам брокер по мере движения цены внутри бара.
        if position is not None and need_atr:
            side = position["side"]
            atr_now = atr_arr[i]
            if not position["be_done"] and not np.isnan(atr_now):
                entry = position["entry_price"]
                if side == "buy" and (bar_high - entry) >= p.be_trig_mult * atr_now:
                    position["sl"] = entry
                    position["be_done"] = True
                elif side == "sell" and (entry - bar_low) >= p.be_trig_mult * atr_now:
                    position["sl"] = entry
                    position["be_done"] = True

            sl, tp = position["sl"], position["tp"]
            exit_price = None
            exit_reason = None
            if side == "buy":
                if sl is not None and bar_low <= sl:
                    exit_price, exit_reason = sl, ("be" if position["be_done"] and sl == position["entry_price"] else "sl")
                elif tp is not None and bar_high >= tp:
                    exit_price, exit_reason = tp, "tp"
            else:
                if sl is not None and bar_high >= sl:
                    exit_price, exit_reason = sl, ("be" if position["be_done"] and sl == position["entry_price"] else "sl")
                elif tp is not None and bar_low <= tp:
                    exit_price, exit_reason = tp, "tp"

            if exit_price is not None:
                tr: Trade = position["trade"]
                tr.exit_time = bar_time
                tr.exit_price = exit_price
                tr.exit_reason = exit_reason
                sign = 1.0 if side == "buy" else -1.0
                tr.pnl = sign * (exit_price - tr.entry_price)
                trades.append(tr)
                position = None

        # 2) Сигнал кроссовера
        if cross_up[i] or cross_dn[i]:
            close_c = close_prev[i - 1]
            m = mid[i - 1]
            if np.isnan(m):
                continue

            allow_atr = True
            if need_atr:
                a = atr_arr[i - 1]
                allow_atr = (not np.isnan(a)) and (a >= p.atr_min)

            if cross_up[i]:
                # закрыть SELL если открыт
                if position is not None and position["side"] == "sell":
                    tr = position["trade"]
                    tr.exit_time = bar_time
                    tr.exit_price = bar_open
                    tr.exit_reason = "cross"
                    tr.pnl = -1.0 * (bar_open - tr.entry_price)
                    trades.append(tr)
                    position = None

                dir_ok = close_c > m
                adx_ok = adx_rising(i) if need_adx else True
                if position is None and allow_atr and dir_ok and adx_ok:
                    entry_price = bar_open
                    tr = Trade(side="buy", entry_time=bar_time, entry_price=entry_price)
                    pos = {"side": "buy", "entry_price": entry_price, "be_done": False, "trade": tr}
                    if need_atr:
                        a = atr_arr[i - 1]
                        dist = p.sl_mult * a
                        tp_dist = max(p.tp_k * a, p.tp_base)
                        pos["sl"] = entry_price - dist
                        pos["tp"] = entry_price + tp_dist
                    else:
                        pos["sl"] = None
                        pos["tp"] = None
                    position = pos

            elif cross_dn[i]:
                if position is not None and position["side"] == "buy":
                    tr = position["trade"]
                    tr.exit_time = bar_time
                    tr.exit_price = bar_open
                    tr.exit_reason = "cross"
                    tr.pnl = 1.0 * (bar_open - tr.entry_price)
                    trades.append(tr)
                    position = None

                dir_ok = close_c < m
                adx_ok = adx_rising(i) if need_adx else True
                if position is None and allow_atr and dir_ok and adx_ok:
                    entry_price = bar_open
                    tr = Trade(side="sell", entry_time=bar_time, entry_price=entry_price)
                    pos = {"side": "sell", "entry_price": entry_price, "be_done": False, "trade": tr}
                    if need_atr:
                        a = atr_arr[i - 1]
                        dist = p.sl_mult * a
                        tp_dist = max(p.tp_k * a, p.tp_base)
                        pos["sl"] = entry_price + dist
                        pos["tp"] = entry_price - tp_dist
                    else:
                        pos["sl"] = None
                        pos["tp"] = None
                    position = pos

    # закрыть последнюю открытую позицию по последней цене (конец истории)
    if position is not None:
        tr = position["trade"]
        tr.exit_time = times[-1]
        tr.exit_price = out["close"].iloc[-1]
        tr.exit_reason = "eod"
        sign = 1.0 if position["side"] == "buy" else -1.0
        tr.pnl = sign * (tr.exit_price - tr.entry_price)
        trades.append(tr)

    return trades


def _cross_signals_2ma(fast: np.ndarray, mid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Кроссовер FAST/MID (2 MA, без SLOW) — тот же shift-конвенция, что и
    _cross_signals: сигнал на баре i использует fastCur/midCur = i-1,
    fastPrev/midPrev = i-2 (последние закрытые бары)."""
    n = len(fast)
    cross_up = np.zeros(n, dtype=bool)
    cross_dn = np.zeros(n, dtype=bool)
    for i in range(2, n):
        fc, mc = fast[i - 1], mid[i - 1]
        fp, mp = fast[i - 2], mid[i - 2]
        if np.isnan(fc) or np.isnan(mc) or np.isnan(fp) or np.isnan(mp):
            continue
        if fp <= mp and fc > mc:
            cross_up[i] = True
        elif fp >= mp and fc < mc:
            cross_dn[i] = True
    return cross_up, cross_dn


def run_backtest_atrrise(df: pd.DataFrame, p: Params,
                          atr_cache: pd.Series | None = None) -> list[Trade]:
    """MA2_ATRRise.mq4: SMA FAST/MID кроссовер (2 MA, без SLOW/MID-фильтра
    направления, без ADX). Вход разрешён, если (не USE_ATR_FILTER) ИЛИ ATR
    строго растёт последние atr_rise_bars закрытых баров. Выход — только по
    обратному кроссоверу (нет TP). Риск: SL = sl_mult*ATR, безубыток
    (breakeven) при профите >= be_trig_mult*ATR.

    ATR-рост проверяется как в MQL4 AtrRising(): ATRNow(shift) для
    shift = atr_rise_bars downto 1, сравнивается с prev = ATRNow(atr_rise_bars+1),
    т.е. используются только закрытые бары относительно бара исполнения i
    (shift=1 соответствует индексу i-1, shift=k -> индекс i-k).
    """
    out = df.copy().reset_index(drop=True)
    out["ma_fast"] = ind.sma(out["close"], p.fast)
    out["ma_mid"] = ind.sma(out["close"], p.mid)
    out["atr"] = atr_cache if atr_cache is not None else ind.atr(out["high"], out["low"], out["close"], p.atr_period)

    fast = out["ma_fast"].to_numpy()
    mid = out["ma_mid"].to_numpy()
    atr_arr = out["atr"].to_numpy()
    cross_up, cross_dn = _cross_signals_2ma(fast, mid)

    n = len(out)
    times = out["time"].to_numpy()
    opens = out["open"].to_numpy()
    highs = out["high"].to_numpy()
    lows = out["low"].to_numpy()

    def atr_rising(i: int) -> bool:
        # shift=1..atr_rise_bars -> индексы i-1..i-atr_rise_bars; prev = i-(atr_rise_bars+1)
        k = p.atr_rise_bars
        if i - (k + 1) < 0:
            return False
        prev = atr_arr[i - (k + 1)]
        if np.isnan(prev):
            return False
        for shift in range(k, 0, -1):
            cur = atr_arr[i - shift]
            if np.isnan(cur) or cur <= prev:
                return False
            prev = cur
        return True

    trades: list[Trade] = []
    position = None  # dict: side, entry_price, sl, be_done, trade

    for i in range(2, n):
        bar_open = opens[i]
        bar_high = highs[i]
        bar_low = lows[i]
        bar_time = times[i]

        # 1) внутрибарный breakeven/SL для открытой позиции
        if position is not None:
            side = position["side"]
            atr_now = atr_arr[i]
            if not position["be_done"] and not np.isnan(atr_now):
                entry = position["entry_price"]
                if side == "buy" and (bar_high - entry) >= p.be_trig_mult * atr_now:
                    position["sl"] = entry
                    position["be_done"] = True
                elif side == "sell" and (entry - bar_low) >= p.be_trig_mult * atr_now:
                    position["sl"] = entry
                    position["be_done"] = True

            sl = position["sl"]
            exit_price = None
            exit_reason = None
            if side == "buy":
                if sl is not None and bar_low <= sl:
                    exit_price = sl
                    exit_reason = "be" if position["be_done"] and sl == position["entry_price"] else "sl"
            else:
                if sl is not None and bar_high >= sl:
                    exit_price = sl
                    exit_reason = "be" if position["be_done"] and sl == position["entry_price"] else "sl"

            if exit_price is not None:
                tr: Trade = position["trade"]
                tr.exit_time = bar_time
                tr.exit_price = exit_price
                tr.exit_reason = exit_reason
                sign = 1.0 if side == "buy" else -1.0
                tr.pnl = sign * (exit_price - tr.entry_price)
                trades.append(tr)
                position = None

        # 2) сигнал кроссовера
        if cross_up[i] or cross_dn[i]:
            a = atr_arr[i - 1]
            if np.isnan(a) or a <= 0:
                continue
            atr_ok = (not p.use_atr_filter) or atr_rising(i)

            if cross_up[i]:
                if position is not None and position["side"] == "sell":
                    tr = position["trade"]
                    tr.exit_time = bar_time
                    tr.exit_price = bar_open
                    tr.exit_reason = "cross"
                    tr.pnl = -1.0 * (bar_open - tr.entry_price)
                    trades.append(tr)
                    position = None

                if position is None and atr_ok:
                    entry_price = bar_open
                    tr = Trade(side="buy", entry_time=bar_time, entry_price=entry_price)
                    dist = p.sl_mult * a
                    position = {
                        "side": "buy", "entry_price": entry_price, "be_done": False,
                        "trade": tr, "sl": entry_price - dist,
                    }

            elif cross_dn[i]:
                if position is not None and position["side"] == "buy":
                    tr = position["trade"]
                    tr.exit_time = bar_time
                    tr.exit_price = bar_open
                    tr.exit_reason = "cross"
                    tr.pnl = 1.0 * (bar_open - tr.entry_price)
                    trades.append(tr)
                    position = None

                if position is None and atr_ok:
                    entry_price = bar_open
                    tr = Trade(side="sell", entry_time=bar_time, entry_price=entry_price)
                    dist = p.sl_mult * a
                    position = {
                        "side": "sell", "entry_price": entry_price, "be_done": False,
                        "trade": tr, "sl": entry_price + dist,
                    }

    if position is not None:
        tr = position["trade"]
        tr.exit_time = times[-1]
        tr.exit_price = out["close"].iloc[-1]
        tr.exit_reason = "eod"
        sign = 1.0 if position["side"] == "buy" else -1.0
        tr.pnl = sign * (tr.exit_price - tr.entry_price)
        trades.append(tr)

    return trades
