"""
Перебор параметров (grid search / сетевой перебор) FAST x SLOW x MID для
каждого из 3 вариантов стратегии, с отбором топ-5 по чистой прибыли и
топ-5 по профит-фактору. Комбинации с малым числом сделок (<20) помечаются
как overfitting-risk (риск переобучения — результат мог получиться случайно
на малой выборке и не будет статистически значим/надёжен в будущем).
"""
from __future__ import annotations

import itertools
import time

import pandas as pd

from backtest import run_variant
from hst_parser import read_hst
from strategy import Params
import indicators as ind

MIN_TRADES_RELIABLE = 20

FAST_RANGE = range(3, 16, 1)      # 3..15
SLOW_RANGE = range(20, 46, 5)     # 20,25,...,45
MID_RANGE = range(10, 31, 5)      # 10,15,...,30

# --- MA2_ATRRise grid ---
ATRRISE_FAST_RANGE = range(3, 16, 1)     # 3..15
ATRRISE_MID_RANGE = range(10, 31, 5)     # 10,15,...,30
ATRRISE_RISE_BARS_RANGE = range(2, 9, 1)  # 2..8


def valid_combo(fast: int, slow: int, mid: int) -> bool:
    return fast < mid < slow


def valid_combo_atrrise(fast: int, mid: int) -> bool:
    return fast < mid


def optimize_atrrise(df: pd.DataFrame, atr_cache: pd.Series | None = None) -> pd.DataFrame:
    rows = []
    combos = [
        (f, m, rb)
        for f, m, rb in itertools.product(ATRRISE_FAST_RANGE, ATRRISE_MID_RANGE, ATRRISE_RISE_BARS_RANGE)
        if valid_combo_atrrise(f, m)
    ]
    t0 = time.time()
    for fast, mid, rise_bars in combos:
        p = Params(fast=fast, mid=mid, atr_rise_bars=rise_bars, use_atr_filter=True)
        _, m = run_variant(df, p, "atrrise", atr_cache)
        rows.append({
            "fast": fast, "mid": mid, "atr_rise_bars": rise_bars,
            "trades": m.total_trades, "win_rate": m.win_rate,
            "net_profit": m.net_profit, "profit_factor": m.profit_factor,
            "max_dd": m.max_drawdown,
        })
    elapsed = time.time() - t0
    print(f"[atrrise] {len(combos)} combos in {elapsed:.1f}s")
    return pd.DataFrame(rows)


def optimize_variant(df: pd.DataFrame, variant: str,
                      atr_cache: pd.Series | None = None,
                      adx_cache: pd.Series | None = None) -> pd.DataFrame:
    rows = []
    combos = [
        (f, s, m)
        for f, s, m in itertools.product(FAST_RANGE, SLOW_RANGE, MID_RANGE)
        if valid_combo(f, s, m)
    ]
    t0 = time.time()
    for idx, (fast, slow, mid) in enumerate(combos):
        p = Params(fast=fast, slow=slow, mid=mid)
        _, m = run_variant(df, p, variant, atr_cache, adx_cache)
        rows.append({
            "fast": fast, "slow": slow, "mid": mid,
            "trades": m.total_trades, "win_rate": m.win_rate,
            "net_profit": m.net_profit, "profit_factor": m.profit_factor,
            "max_dd": m.max_drawdown,
        })
    elapsed = time.time() - t0
    print(f"[{variant}] {len(combos)} combos in {elapsed:.1f}s")
    return pd.DataFrame(rows)


def top_tables(res: pd.DataFrame, n: int = 5):
    res = res.copy()
    res["reliable"] = res["trades"] >= MIN_TRADES_RELIABLE
    top_profit = res.sort_values("net_profit", ascending=False).head(n)
    top_pf = res[res["profit_factor"] < float("inf")].sort_values("profit_factor", ascending=False).head(n)
    return top_profit, top_pf


if __name__ == "__main__":
    df, info = read_hst(r"C:\Users\HP\mt4_backtest\history\NMarkets-Demo\XAUUSD60.hst")
    default_p = Params()
    print("Precomputing shared ATR(14)/ADX(14) caches...")
    atr_cache = ind.atr(df["high"], df["low"], df["close"], default_p.atr_period)
    adx_cache = ind.adx(df["high"], df["low"], df["close"], default_p.adx_period)

    all_results = {}
    for variant in ("baseline", "adx", "no_atr"):
        ac = atr_cache if variant in ("baseline", "adx") else None
        dc = adx_cache if variant == "adx" else None
        res = optimize_variant(df, variant, ac, dc)
        all_results[variant] = res
        res.to_csv(f"opt_results_{variant}.csv", index=False)
        top_p, top_pf = top_tables(res)
        print(f"\n=== {variant}: TOP-5 by net_profit ===")
        print(top_p.to_string(index=False))
        print(f"\n=== {variant}: TOP-5 by profit_factor ===")
        print(top_pf.to_string(index=False))
