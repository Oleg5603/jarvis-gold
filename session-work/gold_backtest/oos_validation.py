"""
Out-of-sample валидация двух фильтров входа для MA2_ATRRise:
  1. hour-exclusion (исключить часы входа 03,08,10,11,13,20 servertime)
  2. stochastic %K extreme (входить только если %K<20 или %K>80 на баре входа)
  3. combined (оба вместе)
против baseline (без фильтра).

Делим полную историю на TRAIN (2004-2018) и TEST (2019-2026), считаем
метрики раздельно на каждой половине БЕЗ переподбора порогов/часов.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from hst_parser import read_hst
from strategy import Params
from backtest import run_variant
import indicators as ind

WORST_HOURS = {13, 10, 20, 11, 3, 8}
P = Params(fast=9, mid=30, atr_rise_bars=2, atr_period=14,
           sl_mult=1.0, be_trig_mult=1.5, use_atr_filter=True)


def metrics_from_pnls(pnls: np.ndarray) -> dict:
    n = len(pnls)
    if n == 0:
        return dict(trades=0, net=0.0, pf=float("nan"), win_rate=float("nan"))
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gp = wins.sum() if len(wins) else 0.0
    gl = losses.sum() if len(losses) else 0.0
    pf = (gp / abs(gl)) if gl < 0 else (np.inf if gp > 0 else 0.0)
    wr = 100.0 * len(wins) / n
    net = pnls.sum()
    return dict(trades=n, net=net, pf=pf, win_rate=wr)


def build_trade_table(df: pd.DataFrame):
    """Запускает baseline atrrise-стратегию на df, возвращает DataFrame
    сделок с entry_time, pnl, hour, stoch_k (на баре входа)."""
    trades, m = run_variant(df, P, "atrrise")
    out = df.copy().reset_index(drop=True)
    out["hour"] = pd.to_datetime(out["time"]).dt.hour
    stoch_k, _ = ind.stochastic(out["high"], out["low"], out["close"], 14, 3)
    out["stoch_k"] = stoch_k

    time_to_idx = pd.Series(out.index.values, index=pd.to_datetime(out["time"]))
    time_to_idx = time_to_idx[~time_to_idx.index.duplicated(keep="first")]

    def idx_for(t):
        ts = pd.Timestamp(t)
        if ts in time_to_idx.index:
            return int(time_to_idx.loc[ts])
        pos = time_to_idx.index.searchsorted(ts)
        pos = min(pos, len(time_to_idx) - 1)
        return int(time_to_idx.iloc[pos])

    rows = []
    for tr in trades:
        i = idx_for(tr.entry_time)
        rows.append(dict(entry_time=tr.entry_time, pnl=tr.pnl,
                          hour=out["hour"].iloc[i], stoch_k=out["stoch_k"].iloc[i]))
    return pd.DataFrame(rows)


def run_period(df_period: pd.DataFrame, label: str) -> dict:
    tdf = build_trade_table(df_period)
    results = {}
    results["baseline"] = metrics_from_pnls(tdf["pnl"].to_numpy())

    hour_mask = ~tdf["hour"].isin(WORST_HOURS)
    results["hour_excl"] = metrics_from_pnls(tdf.loc[hour_mask, "pnl"].to_numpy())

    stoch_mask = (tdf["stoch_k"] < 20) | (tdf["stoch_k"] > 80)
    results["stoch_extreme"] = metrics_from_pnls(tdf.loc[stoch_mask, "pnl"].to_numpy())

    combo_mask = hour_mask & stoch_mask
    results["combined"] = metrics_from_pnls(tdf.loc[combo_mask, "pnl"].to_numpy())

    print(f"\n===== {label} ===== (total base trades in period={len(tdf)})")
    for k, v in results.items():
        print(f"  {k:15s} trades={v['trades']:4d} net={v['net']:8.2f} pf={v['pf']:.2f} win_rate={v['win_rate']:.1f}%")
    return results


def main():
    df, info = read_hst(r"C:\Users\HP\mt4_backtest\history\NMarkets-Demo\XAUUSD60.hst")
    df["time"] = pd.to_datetime(df["time"])
    print(f"Full data range: {df['time'].min()} -> {df['time'].max()}, bars={len(df)}")

    train = df[(df["time"] >= "2004-01-01") & (df["time"] < "2019-01-01")].reset_index(drop=True)
    test = df[(df["time"] >= "2019-01-01") & (df["time"] < "2026-12-31")].reset_index(drop=True)
    print(f"TRAIN: {train['time'].min()} -> {train['time'].max()}, bars={len(train)}")
    print(f"TEST : {test['time'].min()} -> {test['time'].max()}, bars={len(test)}")

    res_train = run_period(train, "TRAIN 2004-2018")
    res_test = run_period(test, "TEST 2019-2026")

    print("\n\n===== SUMMARY TABLE =====")
    print(f"{'variant':15s} {'period':6s} {'trades':>7s} {'net':>9s} {'pf':>6s} {'win%':>6s}")
    for period, res in (("TRAIN", res_train), ("TEST", res_test)):
        for k, v in res.items():
            print(f"{k:15s} {period:6s} {v['trades']:7d} {v['net']:9.2f} {v['pf']:6.2f} {v['win_rate']:6.1f}")

    import json
    out = {"train": res_train, "test": res_test}
    with open(r"C:\Users\HP\Documents\Project\session-work\gold_backtest\oos_results.json", "w") as f:
        json.dump(out, f, indent=2, default=lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else str(o))


if __name__ == "__main__":
    main()
