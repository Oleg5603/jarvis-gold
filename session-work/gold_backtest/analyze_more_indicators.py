"""
Анализ 8 новых кандидатов-индикаторов для стратегии MA2_ATRRise (XAUUSD H1).
Продолжение analyze_atrrise_losses.py: та же логика привязки сделки к бару
входа, но новый набор индикаторов (MACD, Stochastic, CCI, Williams %R,
ADX-slope, дистанция от SMA200, ATR-тренд, тело/диапазон свечи).
Не меняет strategy.py/backtest.py/analyze_atrrise_losses.py — отдельный скрипт.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from hst_parser import read_hst
from strategy import Params
from backtest import run_variant
import indicators as ind

HOUR_EXCLUDE = {3, 8, 10, 11, 13, 20}  # из прежнего отчёта (in-sample, unvalidated)


def main():
    df, info = read_hst(r"C:\Users\HP\mt4_backtest\history\NMarkets-Demo\XAUUSD60.hst")
    print(f"Data range: {df['time'].min()} -> {df['time'].max()}, bars={len(df)}")

    p = Params(fast=9, mid=30, atr_rise_bars=2, atr_period=14,
               sl_mult=1.0, be_trig_mult=1.5, use_atr_filter=True)
    trades, m = run_variant(df, p, "atrrise")
    print(f"trades={m.total_trades} net_profit={m.net_profit:.2f} pf={m.profit_factor:.2f}")

    out = df.copy().reset_index(drop=True)

    # 1. MACD
    macd_line, macd_sig, macd_hist = ind.macd(out["close"], 12, 26, 9)
    out["macd_hist"] = macd_hist

    # 2. Stochastic
    stoch_k, stoch_d = ind.stochastic(out["high"], out["low"], out["close"], 14, 3)
    out["stoch_k"] = stoch_k
    out["stoch_d"] = stoch_d
    out["stoch_k_minus_d"] = stoch_k - stoch_d

    # 3. CCI
    out["cci20"] = ind.cci(out["high"], out["low"], out["close"], 20)

    # 4. Williams %R
    out["willr14"] = ind.williams_r(out["high"], out["low"], out["close"], 14)

    # 5. ADX slope (direction over last 3-4 bars)
    adx14 = ind.adx(out["high"], out["low"], out["close"], 14)
    out["adx14"] = adx14
    out["adx_slope3"] = adx14 - adx14.shift(3)
    out["adx_slope4"] = adx14 - adx14.shift(4)

    # 6. Distance from SMA200, %
    sma200 = ind.sma(out["close"], 200)
    out["dist_sma200_pct"] = (out["close"] - sma200) / sma200 * 100.0

    # 7. ATR trend (rising/falling vs its value N bars ago)
    atr14 = ind.atr(out["high"], out["low"], out["close"], 14)
    out["atr14"] = atr14
    out["atr_chg5_pct"] = (atr14 - atr14.shift(5)) / atr14.shift(5) * 100.0
    out["atr_chg10_pct"] = (atr14 - atr14.shift(10)) / atr14.shift(10) * 100.0

    # 8. Body/range ratio of entry bar and 2-3 bars before
    brr = ind.body_range_ratio(out["open"], out["high"], out["low"], out["close"])
    out["brr0"] = brr
    out["brr_avg3"] = brr.rolling(3, min_periods=3).mean()  # entry bar + 2 before (avg incl. entry)
    out["brr_prev1"] = brr.shift(1)
    out["brr_prev2"] = brr.shift(2)
    out["brr_avg_prev3"] = (brr.shift(1) + brr.shift(2) + brr.shift(3)) / 3.0  # 3 bars strictly before entry

    out["hour"] = pd.to_datetime(out["time"]).dt.hour

    time_to_idx = pd.Series(out.index.values, index=pd.to_datetime(out["time"]))
    time_to_idx = time_to_idx[~time_to_idx.index.duplicated(keep="first")]

    def idx_for(t):
        ts = pd.Timestamp(t)
        if ts in time_to_idx.index:
            return int(time_to_idx.loc[ts])
        pos = time_to_idx.index.searchsorted(ts)
        pos = min(pos, len(time_to_idx) - 1)
        return int(time_to_idx.iloc[pos])

    cols = ["macd_hist", "stoch_k", "stoch_d", "stoch_k_minus_d", "cci20", "willr14",
            "adx_slope3", "adx_slope4", "dist_sma200_pct", "atr_chg5_pct", "atr_chg10_pct",
            "brr0", "brr_avg3", "brr_prev1", "brr_prev2", "brr_avg_prev3", "hour"]

    rows = []
    for tr in trades:
        i = idx_for(tr.entry_time)
        row = {"entry_time": tr.entry_time, "side": tr.side, "pnl": tr.pnl}
        for c in cols:
            row[c] = out[c].iloc[i]
        rows.append(row)

    tdf = pd.DataFrame(rows)
    tdf.to_csv(r"C:\Users\HP\Documents\Project\session-work\gold_backtest\atrrise_trades_more_indicators.csv", index=False)

    winners = tdf[tdf["pnl"] > 0].copy()
    losers = tdf[tdf["pnl"] < 0].copy()
    print(f"\ntotal={len(tdf)} winners={len(winners)} losers={len(losers)}")

    def summarize(col):
        print(f"-- {col} -- winners: mean={winners[col].mean():.4f} median={winners[col].median():.4f} "
              f"| losers: mean={losers[col].mean():.4f} median={losers[col].median():.4f}")

    print("\n===== DISTRIBUTIONS =====")
    for c in cols[:-1]:
        summarize(c)

    def sim_filter(mask_fn, label):
        keep = tdf.apply(mask_fn, axis=1)
        kept = tdf[keep]
        removed_losers = len(losers) - len(kept[kept["pnl"] < 0])
        removed_winners = len(winners) - len(kept[kept["pnl"] > 0])
        gp = kept.loc[kept["pnl"] > 0, "pnl"].sum()
        gl = kept.loc[kept["pnl"] < 0, "pnl"].sum()
        pf = gp / abs(gl) if gl < 0 else (np.inf if gp > 0 else 0.0)
        net = kept["pnl"].sum()
        print(f"[{label}] trades={len(kept)} removed_losers={removed_losers} removed_winners={removed_winners} "
              f"net={net:.2f} pf={pf:.2f}")
        return kept, net, pf, removed_losers, removed_winners

    baseline_net = tdf["pnl"].sum()
    gp0 = winners["pnl"].sum(); gl0 = losers["pnl"].sum()
    baseline_pf = gp0/abs(gl0)
    print(f"\n===== BASELINE ===== net={baseline_net:.2f} pf={baseline_pf:.2f} trades={len(tdf)}")

    print("\n===== 1. MACD histogram =====")
    for thr in [0, -0.05, 0.05]:
        sim_filter(lambda r, t=thr: r["macd_hist"] > t, f"macd_hist>{thr}")
    for thr in [0, 0.05, -0.05]:
        sim_filter(lambda r, t=thr: r["macd_hist"] < t, f"macd_hist<{thr}")
    # side-aligned: buy needs macd_hist>0, sell needs macd_hist<0
    sim_filter(lambda r: (r["side"] == "buy" and r["macd_hist"] > 0) or (r["side"] == "sell" and r["macd_hist"] < 0),
               "macd_hist aligned with side")

    print("\n===== 2. Stochastic =====")
    for lo, hi in [(20, 80), (30, 70), (10, 90)]:
        sim_filter(lambda r, lo=lo, hi=hi: lo <= r["stoch_k"] <= hi, f"stoch_k in [{lo},{hi}]")
    sim_filter(lambda r: r["stoch_k_minus_d"] > 0, "stoch_k>stoch_d")
    sim_filter(lambda r: (r["side"] == "buy" and r["stoch_k_minus_d"] > 0) or (r["side"] == "sell" and r["stoch_k_minus_d"] < 0),
               "stoch_k vs d aligned with side")

    print("\n===== 3. CCI =====")
    for thr in [100, 50, -50, -100]:
        sim_filter(lambda r, t=thr: r["cci20"] > t, f"cci20>{thr}")
        sim_filter(lambda r, t=thr: r["cci20"] < t, f"cci20<{thr}")
    sim_filter(lambda r: (r["side"] == "buy" and r["cci20"] > 0) or (r["side"] == "sell" and r["cci20"] < 0),
               "cci20 aligned with side")

    print("\n===== 4. Williams %R =====")
    for thr in [-20, -50, -80]:
        sim_filter(lambda r, t=thr: r["willr14"] > t, f"willr14>{thr}")
    for thr in [-20, -50, -80]:
        sim_filter(lambda r, t=thr: r["willr14"] < t, f"willr14<{thr}")

    print("\n===== 5. ADX slope =====")
    for col in ["adx_slope3", "adx_slope4"]:
        sim_filter(lambda r, c=col: r[c] > 0, f"{col}>0 (rising)")
        sim_filter(lambda r, c=col: r[c] < 0, f"{col}<0 (falling)")
        for thr in [1, 2]:
            sim_filter(lambda r, c=col, t=thr: r[c] > t, f"{col}>{thr}")

    print("\n===== 6. Distance from SMA200 % =====")
    for thr in [0.5, 1, 2, 3]:
        sim_filter(lambda r, t=thr: abs(r["dist_sma200_pct"]) < t, f"|dist_sma200_pct|<{thr}")
        sim_filter(lambda r, t=thr: abs(r["dist_sma200_pct"]) > t, f"|dist_sma200_pct|>{thr}")
    sim_filter(lambda r: (r["side"] == "buy" and r["dist_sma200_pct"] > 0) or (r["side"] == "sell" and r["dist_sma200_pct"] < 0),
               "dist_sma200 aligned with side (trend-following)")

    print("\n===== 7. ATR trend =====")
    for col in ["atr_chg5_pct", "atr_chg10_pct"]:
        sim_filter(lambda r, c=col: r[c] > 0, f"{col}>0 (expanding)")
        sim_filter(lambda r, c=col: r[c] < 0, f"{col}<0 (contracting)")
        for thr in [10, 20]:
            sim_filter(lambda r, c=col, t=thr: r[c] > t, f"{col}>{thr}")

    print("\n===== 8. Body/range ratio =====")
    for col in ["brr0", "brr_avg3", "brr_avg_prev3"]:
        for thr in [0.3, 0.5, 0.7]:
            sim_filter(lambda r, c=col, t=thr: r[c] > t, f"{col}>{thr}")
            sim_filter(lambda r, c=col, t=thr: r[c] < t, f"{col}<{thr}")

    # ---- stacking check for any promising filter with hour-exclusion ----
    print("\n===== HOUR EXCLUSION baseline (from prior report) =====")
    hour_kept, hour_net, hour_pf, hrl, hrw = sim_filter(lambda r: r["hour"] not in HOUR_EXCLUDE, "hour_exclusion")

    print("\n===== STACK CANDIDATES (best from each family) x hour exclusion =====")
    stack_candidates = {
        "macd_hist aligned with side": lambda r: (r["side"] == "buy" and r["macd_hist"] > 0) or (r["side"] == "sell" and r["macd_hist"] < 0),
        "stoch_k vs d aligned with side": lambda r: (r["side"] == "buy" and r["stoch_k_minus_d"] > 0) or (r["side"] == "sell" and r["stoch_k_minus_d"] < 0),
        "cci20 aligned with side": lambda r: (r["side"] == "buy" and r["cci20"] > 0) or (r["side"] == "sell" and r["cci20"] < 0),
        "adx_slope3>0": lambda r: r["adx_slope3"] > 0,
        "dist_sma200 aligned with side": lambda r: (r["side"] == "buy" and r["dist_sma200_pct"] > 0) or (r["side"] == "sell" and r["dist_sma200_pct"] < 0),
        "atr_chg5_pct>0": lambda r: r["atr_chg5_pct"] > 0,
        "brr0>0.5": lambda r: r["brr0"] > 0.5,
    }
    for label, fn in stack_candidates.items():
        combo_fn = lambda r, fn=fn: fn(r) and (r["hour"] not in HOUR_EXCLUDE)
        sim_filter(combo_fn, f"STACK: {label} + hour_exclusion")


if __name__ == "__main__":
    main()
