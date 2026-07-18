"""
Дополнительные индикаторы-кандидаты для фильтра входа MA2_ATRRise (вариант atrrise).
Продолжение analyze_atrrise_losses.py: та же выборка сделок, те же данные,
добавляем 8 новых индикаторов на баре входа и тестируем каждый как бинарный
фильтр входа (macd, stochastic, cci, williams_r, body_range_ratio реализованы
в indicators.py; adx-slope, sma200-distance, atr-trend считаем прямо здесь).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from hst_parser import read_hst
from strategy import Params
from backtest import run_variant
import indicators as ind


def main():
    df, info = read_hst(r"C:\Users\HP\mt4_backtest\history\NMarkets-Demo\XAUUSD60.hst")
    print(f"Data range: {df['time'].min()} -> {df['time'].max()}, bars={len(df)}")

    p = Params(fast=9, mid=30, atr_rise_bars=2, atr_period=14,
               sl_mult=1.0, be_trig_mult=1.5, use_atr_filter=True)

    trades, m = run_variant(df, p, "atrrise")
    print(f"trades={m.total_trades} net_profit={m.net_profit:.2f} pf={m.profit_factor:.2f}")

    out = df.copy().reset_index(drop=True)

    out["hour"] = pd.to_datetime(out["time"]).dt.hour

    # ---- 1. MACD histogram (12,26,9) ----
    macd_line, signal_line, macd_hist = ind.macd(out["close"], 12, 26, 9)
    out["macd_hist"] = macd_hist

    # ---- 2. Stochastic (%K14, %D3) ----
    stoch_k, stoch_d = ind.stochastic(out["high"], out["low"], out["close"], 14, 3)
    out["stoch_k"] = stoch_k
    out["stoch_d"] = stoch_d
    out["stoch_k_minus_d"] = stoch_k - stoch_d

    # ---- 3. CCI(20) ----
    out["cci20"] = ind.cci(out["high"], out["low"], out["close"], 20)

    # ---- 4. Williams %R(14) ----
    out["wr14"] = ind.williams_r(out["high"], out["low"], out["close"], 14)

    # ---- 5. ADX slope (over last 4 bars) ----
    adx14 = ind.adx(out["high"], out["low"], out["close"], 14)
    out["adx14"] = adx14
    out["adx_slope4"] = adx14 - adx14.shift(4)

    # ---- 6. Distance from SMA200, % ----
    sma200 = ind.sma(out["close"], 200)
    out["sma200"] = sma200
    out["dist_sma200_pct"] = (out["close"] - sma200) / sma200 * 100.0

    # ---- 7. ATR trend: ATR14 now vs ATR14 N bars ago, % change ----
    atr14 = ind.atr(out["high"], out["low"], out["close"], 14)
    out["atr14"] = atr14
    N = 10
    out["atr_trend"] = (atr14 - atr14.shift(N)) / atr14.shift(N) * 100.0

    # ---- 8. Candle body/range ratio, entry bar and 3 bars before ----
    brr = ind.body_range_ratio(out["open"], out["high"], out["low"], out["close"])
    out["body_ratio"] = brr
    out["body_ratio_avg4"] = brr.rolling(4, min_periods=4).mean()

    time_to_idx = pd.Series(out.index.values, index=pd.to_datetime(out["time"]))
    time_to_idx = time_to_idx[~time_to_idx.index.duplicated(keep="first")]

    def idx_for(t):
        ts = pd.Timestamp(t)
        if ts in time_to_idx.index:
            return int(time_to_idx.loc[ts])
        pos = time_to_idx.index.searchsorted(ts)
        pos = min(pos, len(time_to_idx) - 1)
        return int(time_to_idx.iloc[pos])

    cols = ["macd_hist", "stoch_k", "stoch_d", "stoch_k_minus_d", "cci20", "wr14",
            "adx14", "adx_slope4", "dist_sma200_pct", "atr_trend", "body_ratio",
            "body_ratio_avg4", "hour"]

    rows = []
    for tr in trades:
        i = idx_for(tr.entry_time)
        row = {"entry_time": tr.entry_time, "pnl": tr.pnl}
        for c in cols:
            row[c] = out[c].iloc[i]
        rows.append(row)

    tdf = pd.DataFrame(rows)
    tdf.to_csv(r"C:\Users\HP\Documents\Project\session-work\gold_backtest\atrrise_trades_more_indicators_v2.csv", index=False)

    losers = tdf[tdf["pnl"] < 0].copy()
    winners = tdf[tdf["pnl"] > 0].copy()
    n_na = tdf[cols].isna().any(axis=1).sum()
    print(f"\ntotal={len(tdf)} winners={len(winners)} losers={len(losers)} rows_with_any_NaN={n_na}")

    def summarize(col):
        print(f"\n-- {col} --")
        print(f"winners: mean={winners[col].mean():.4f} median={winners[col].median():.4f}")
        print(f"losers : mean={losers[col].mean():.4f} median={losers[col].median():.4f}")

    for col in ["macd_hist", "stoch_k", "stoch_k_minus_d", "cci20", "wr14",
                "adx_slope4", "dist_sma200_pct", "atr_trend", "body_ratio", "body_ratio_avg4"]:
        summarize(col)

    def sim_filter(mask_fn, label, base=tdf):
        keep = mask_fn(base)
        kept = base[keep]
        bl = base[base["pnl"] < 0]
        bw = base[base["pnl"] > 0]
        kl = kept[kept["pnl"] < 0]
        kw = kept[kept["pnl"] > 0]
        removed_losers = len(bl) - len(kl)
        removed_winners = len(bw) - len(kw)
        gp = kw["pnl"].sum()
        gl = kl["pnl"].sum()
        pf = gp / abs(gl) if gl < 0 else (np.inf if gp > 0 else 0.0)
        net = kept["pnl"].sum()
        print(f"[{label}] trades={len(kept)} (removed_losers={removed_losers}, removed_winners={removed_winners}) "
              f"net={net:.2f} pf={pf:.2f} win_rate={100*len(kw)/len(kept) if len(kept) else 0:.1f}%")
        return dict(label=label, trades=len(kept), removed_losers=removed_losers,
                    removed_winners=removed_winners, net=net, pf=pf, mask_fn=mask_fn)

    base_net = tdf["pnl"].sum()
    base_gp = winners["pnl"].sum()
    base_gl = losers["pnl"].sum()
    base_pf = base_gp / abs(base_gl)
    print(f"\n===== BASELINE ===== trades={len(tdf)} net={base_net:.2f} pf={base_pf:.2f}\n")

    results = {}

    print("=== 1. MACD histogram ===")
    results["macd"] = [
        sim_filter(lambda d: d["macd_hist"] > 0, "macd_hist>0"),
        sim_filter(lambda d: d["macd_hist"].abs() > tdf["macd_hist"].abs().median(), "|macd_hist|>median"),
        sim_filter(lambda d: d["macd_hist"].abs() > tdf["macd_hist"].abs().quantile(0.75), "|macd_hist|>q75"),
    ]

    print("\n=== 2. Stochastic ===")
    results["stoch"] = [
        sim_filter(lambda d: (d["stoch_k"] > 20) & (d["stoch_k"] < 80), "stoch_k in (20,80)"),
        sim_filter(lambda d: (d["stoch_k"] < 20) | (d["stoch_k"] > 80), "stoch_k extreme"),
        sim_filter(lambda d: d["stoch_k_minus_d"] > 0, "stoch_k>stoch_d"),
    ]

    print("\n=== 3. CCI ===")
    results["cci"] = [
        sim_filter(lambda d: d["cci20"].abs() < 100, "|CCI|<100"),
        sim_filter(lambda d: d["cci20"].abs() > 100, "|CCI|>100"),
        sim_filter(lambda d: d["cci20"].abs() > 150, "|CCI|>150"),
    ]

    print("\n=== 4. Williams %R ===")
    results["wr"] = [
        sim_filter(lambda d: (d["wr14"] > -80) & (d["wr14"] < -20), "WR in (-80,-20)"),
        sim_filter(lambda d: (d["wr14"] < -80) | (d["wr14"] > -20), "WR extreme"),
        sim_filter(lambda d: d["wr14"] < -50, "WR<-50"),
    ]

    print("\n=== 5. ADX slope (4 bars) ===")
    results["adx_slope"] = [
        sim_filter(lambda d: d["adx_slope4"] > 0, "ADX rising (slope4>0)"),
        sim_filter(lambda d: d["adx_slope4"] < 0, "ADX falling (slope4<0)"),
        sim_filter(lambda d: d["adx_slope4"] > 1.0, "ADX rising strongly (>1.0)"),
    ]

    print("\n=== 6. Distance from SMA200 (%) ===")
    q_abs = tdf["dist_sma200_pct"].abs()
    results["sma200"] = [
        sim_filter(lambda d: d["dist_sma200_pct"].abs() < q_abs.median(), "|dist SMA200|<median"),
        sim_filter(lambda d: d["dist_sma200_pct"].abs() > q_abs.median(), "|dist SMA200|>median"),
        sim_filter(lambda d: d["dist_sma200_pct"].abs() < q_abs.quantile(0.25), "|dist SMA200|<q25"),
    ]

    print("\n=== 7. ATR trend (%change over 10 bars) ===")
    results["atr_trend"] = [
        sim_filter(lambda d: d["atr_trend"] > 0, "ATR expanding (>0)"),
        sim_filter(lambda d: d["atr_trend"] < 0, "ATR contracting (<0)"),
        sim_filter(lambda d: d["atr_trend"] > 10, "ATR expanding strongly (>10%)"),
    ]

    print("\n=== 8. Candle body/range ratio ===")
    med_br = tdf["body_ratio"].median()
    med_br4 = tdf["body_ratio_avg4"].median()
    results["body_ratio"] = [
        sim_filter(lambda d: d["body_ratio"] > med_br, "body_ratio>median"),
        sim_filter(lambda d: d["body_ratio"] > 0.6, "body_ratio>0.6"),
        sim_filter(lambda d: d["body_ratio_avg4"] > med_br4, "avg4 body_ratio>median"),
    ]

    worst_hours = [13, 10, 20, 11, 3, 8]
    print("\n=== Hour-exclusion filter (reproduced from prior report) ===")
    hour_mask = lambda d, wh=set(worst_hours): ~d["hour"].isin(wh)
    hour_res = sim_filter(hour_mask, f"exclude hours {worst_hours}")

    print("\n\n===== SCAN FOR PROMISING CANDIDATES (net up AND pf up AND removed_losers > removed_winners) =====")
    promising = []
    for k, lst in results.items():
        for r in lst:
            if r["net"] > base_net and r["pf"] > base_pf and r["removed_losers"] > r["removed_winners"]:
                promising.append((k, r))
                print(k, r["label"], "net=", r["net"], "pf=", r["pf"])

    if promising:
        print("\n\n===== STACKING WITH HOUR FILTER =====")
        for k, r in promising:
            combo_mask = lambda d, mf=r["mask_fn"], hf=hour_mask: mf(d) & hf(d)
            sim_filter(combo_mask, f"STACK: {r['label']} + hour_exclusion")
    else:
        print("\nNo candidate met the bar. No stacking test performed.")

    print("\nDone.")


if __name__ == "__main__":
    main()
