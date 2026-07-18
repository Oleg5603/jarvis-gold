"""
Анализ убыточных сделок стратегии MA2_ATRRise (variant='atrrise').
Не меняет strategy.py/backtest.py — отдельный скрипт-анализ.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from hst_parser import read_hst
from strategy import Params
from backtest import run_variant
import indicators as ind


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def bb_width(close: pd.Series, period: int = 20, k: float = 2.0) -> pd.Series:
    ma = close.rolling(period, min_periods=period).mean()
    sd = close.rolling(period, min_periods=period).std()
    upper = ma + k * sd
    lower = ma - k * sd
    return (upper - lower) / ma


def main():
    df, info = read_hst(r"C:\Users\HP\mt4_backtest\history\NMarkets-Demo\XAUUSD60.hst")
    print(f"Data range: {df['time'].min()} -> {df['time'].max()}, bars={len(df)}")

    p = Params(fast=9, mid=30, atr_rise_bars=2, atr_period=14,
               sl_mult=1.0, be_trig_mult=1.5, use_atr_filter=True)

    trades, m = run_variant(df, p, "atrrise")
    print(f"\n=== atrrise (FAST=9 MID=30 ARB=2 ATRp=14 SL=1.0 BE=1.5 filter=True) ===")
    print(f"trades={m.total_trades} win_rate={m.win_rate:.1f}% net_profit={m.net_profit:.2f} "
          f"profit_factor={m.profit_factor:.2f} max_dd={m.max_drawdown:.2f}")

    # ---- indicators over same price series ----
    out = df.copy().reset_index(drop=True)
    out["adx14"] = ind.adx(out["high"], out["low"], out["close"], 14)
    out["rsi14"] = rsi(out["close"], 14)
    out["atr14"] = ind.atr(out["high"], out["low"], out["close"], 14)
    out["atr_pct"] = out["atr14"].rank(pct=True)
    out["bbw"] = bb_width(out["close"], 20, 2.0)
    out["bbw_pct"] = out["bbw"].rank(pct=True)
    out["hour"] = pd.to_datetime(out["time"]).dt.hour
    out["dow"] = pd.to_datetime(out["time"]).dt.dayofweek  # 0=Mon

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
        bars_open = None
        if tr.exit_time is not None:
            j = idx_for(tr.exit_time)
            bars_open = j - i
        rows.append({
            "entry_time": tr.entry_time, "side": tr.side, "entry_price": tr.entry_price,
            "exit_time": tr.exit_time, "exit_price": tr.exit_price,
            "exit_reason": tr.exit_reason, "pnl": tr.pnl, "bars_open": bars_open,
            "adx14": out["adx14"].iloc[i], "rsi14": out["rsi14"].iloc[i],
            "atr14": out["atr14"].iloc[i], "atr_pct": out["atr_pct"].iloc[i],
            "bbw_pct": out["bbw_pct"].iloc[i],
            "hour": out["hour"].iloc[i], "dow": out["dow"].iloc[i],
        })

    tdf = pd.DataFrame(rows)
    tdf.to_csv(r"C:\Users\HP\Documents\Project\session-work\gold_backtest\atrrise_trades_annotated.csv", index=False)

    losers = tdf[tdf["pnl"] < 0].copy()
    winners = tdf[tdf["pnl"] > 0].copy()
    print(f"\ntotal={len(tdf)} winners={len(winners)} losers={len(losers)}")

    def summarize(col):
        print(f"\n-- {col} --")
        print(f"winners: mean={winners[col].mean():.3f} median={winners[col].median():.3f}")
        print(f"losers : mean={losers[col].mean():.3f} median={losers[col].median():.3f}")

    for col in ["adx14", "rsi14", "atr_pct", "bbw_pct", "bars_open"]:
        summarize(col)

    print("\n-- exit_reason distribution --")
    print("winners:\n", winners["exit_reason"].value_counts())
    print("losers:\n", losers["exit_reason"].value_counts())

    print("\n-- hour distribution (winners vs losers), % --")
    wh = (winners["hour"].value_counts(normalize=True) * 100).sort_index()
    lh = (losers["hour"].value_counts(normalize=True) * 100).sort_index()
    hcmp = pd.DataFrame({"winners_%": wh, "losers_%": lh}).fillna(0.0)
    print(hcmp)

    print("\n-- day of week distribution (0=Mon) --")
    wd = (winners["dow"].value_counts(normalize=True) * 100).sort_index()
    ld = (losers["dow"].value_counts(normalize=True) * 100).sort_index()
    dcmp = pd.DataFrame({"winners_%": wd, "losers_%": ld}).fillna(0.0)
    print(dcmp)

    # quartiles of adx14 among ALL trades, % of losers vs winners in bottom quartile
    q1 = tdf["adx14"].quantile(0.25)
    q3 = tdf["adx14"].quantile(0.75)
    print(f"\nADX quartiles across trades: Q1={q1:.2f} Q3={q3:.2f}")
    print(f"losers in bottom ADX quartile: {(losers['adx14'] < q1).mean()*100:.1f}%")
    print(f"winners in bottom ADX quartile: {(winners['adx14'] < q1).mean()*100:.1f}%")

    # ---- Filter simulation helper ----
    def sim_filter(mask_col_fn, label):
        keep = tdf.apply(mask_col_fn, axis=1)
        kept = tdf[keep]
        removed_losers = len(losers) - len(kept[kept["pnl"] < 0])
        removed_winners = len(winners) - len(kept[kept["pnl"] > 0])
        gp = kept.loc[kept["pnl"] > 0, "pnl"].sum()
        gl = kept.loc[kept["pnl"] < 0, "pnl"].sum()
        pf = gp / abs(gl) if gl < 0 else (np.inf if gp > 0 else 0.0)
        print(f"\n[{label}] trades kept={len(kept)} (removed losers={removed_losers}, "
              f"removed winners={removed_winners}) net={kept['pnl'].sum():.2f} pf={pf:.2f} "
              f"win_rate={100*len(kept[kept['pnl']>0])/len(kept):.1f}%")
        return kept

    print("\n\n===== FILTER CANDIDATES =====")
    print(f"baseline (no filter): net={tdf['pnl'].sum():.2f} pf={m.profit_factor:.2f} "
          f"trades={len(tdf)} win_rate={m.win_rate:.1f}%")

    for thr in [15, 18, 20, 22, 25]:
        sim_filter(lambda r, t=thr: r["adx14"] >= t, f"ADX>={thr}")

    for lo, hi in [(0.1, 0.9), (0.15, 0.85), (0.2, 0.8)]:
        sim_filter(lambda r, lo=lo, hi=hi: lo <= r["bbw_pct"] <= hi, f"bbw_pct in [{lo},{hi}]")

    for lo, hi in [(0.1, 0.9), (0.2, 0.8)]:
        sim_filter(lambda r, lo=lo, hi=hi: lo <= r["atr_pct"] <= hi, f"atr_pct in [{lo},{hi}]")

    # hour exclusion candidates: find hours with worst pnl
    hour_pnl = tdf.groupby("hour")["pnl"].agg(["sum", "count", "mean"]).sort_values("sum")
    print("\n-- PnL by hour (sorted worst first) --")
    print(hour_pnl)

    worst_hours = hour_pnl[hour_pnl["sum"] < 0].index.tolist()
    sim_filter(lambda r, wh=set(worst_hours): r["hour"] not in wh, f"exclude hours {worst_hours}")

    dow_pnl = tdf.groupby("dow")["pnl"].agg(["sum", "count", "mean"]).sort_values("sum")
    print("\n-- PnL by day of week --")
    print(dow_pnl)

    # consecutive-loss cooldown simulation
    def sim_cooldown(n_losses, cooldown_trades):
        kept_rows = []
        streak = 0
        skip_remaining = 0
        for _, r in tdf.sort_values("entry_time").iterrows():
            if skip_remaining > 0:
                skip_remaining -= 1
                continue
            kept_rows.append(r)
            if r["pnl"] < 0:
                streak += 1
                if streak >= n_losses:
                    skip_remaining = cooldown_trades
                    streak = 0
            else:
                streak = 0
        kept = pd.DataFrame(kept_rows)
        gp = kept.loc[kept["pnl"] > 0, "pnl"].sum()
        gl = kept.loc[kept["pnl"] < 0, "pnl"].sum()
        pf = gp / abs(gl) if gl < 0 else (np.inf if gp > 0 else 0.0)
        print(f"\n[cooldown after {n_losses} losses, skip {cooldown_trades}] trades={len(kept)} "
              f"net={kept['pnl'].sum():.2f} pf={pf:.2f} win_rate={100*len(kept[kept['pnl']>0])/len(kept):.1f}%")
        return kept

    for nl, cd in [(2, 1), (2, 2), (3, 1), (3, 2)]:
        sim_cooldown(nl, cd)


if __name__ == "__main__":
    main()
