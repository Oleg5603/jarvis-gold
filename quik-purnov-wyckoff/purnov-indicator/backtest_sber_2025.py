"""Reproduce PurnovContext.lua signals on MOEX SBER daily candles for 2025."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).parents[1] / "session-work" / "sber_2025_d1.json"
PERIOD = 20
TREND_PERIOD = 34
VOLUME_FACTOR = 1.35
WICK_FACTOR = 1.20
ATR_BUFFER = 0.15
MIN_SCORE = 3
COST_PER_SIDE = 0.0005  # 0.05% commission + slippage assumption


def load() -> pd.DataFrame:
    raw = json.loads(DATA.read_text(encoding="utf-8"))["candles"]
    df = pd.DataFrame(raw["data"], columns=raw["columns"])
    df["date"] = pd.to_datetime(df["begin"])
    return df.sort_values("date").reset_index(drop=True)


def signals(df: pd.DataFrame) -> pd.DataFrame:
    n = len(df)
    out = np.zeros(n, dtype=int)
    kind = np.full(n, "", dtype=object)
    score_out = np.zeros(n, dtype=int)
    tr = np.maximum(df.high-df.low, np.maximum((df.high-df.close.shift()).abs(), (df.low-df.close.shift()).abs()))
    atr = tr.rolling(14).mean()

    for i in range(max(PERIOD * 2, TREND_PERIOD * 2), n):
        prev = df.iloc[i-PERIOD:i]
        support, resistance = prev.low.min(), prev.high.max()
        avg_volume = prev.volume.mean()
        avg_range = (prev.high-prev.low).mean()
        row = df.iloc[i]
        bar_range = max(row.high-row.low, 1e-7)
        body = max(abs(row.close-row.open), bar_range*0.10)
        lower_wick = min(row.open,row.close)-row.low
        upper_wick = row.high-max(row.open,row.close)
        volume_ok = row.volume >= avg_volume*VOLUME_FACTOR
        wide = bar_range >= avg_range*1.15
        recent = df.close.iloc[i-TREND_PERIOD+1:i+1].mean()
        previous = df.close.iloc[i-TREND_PERIOD*2+1:i-TREND_PERIOD+1].mean()
        trend = 1 if recent > previous else -1 if recent < previous else 0

        spring = row.low < support and row.close > support and lower_wick >= body*WICK_FACTOR
        upthrust = row.high > resistance and row.close < resistance and upper_wick >= body*WICK_FACTOR
        joc = row.close > resistance + atr.iloc[i]*ATR_BUFFER and row.close > row.open and wide
        sow = row.close < support - atr.iloc[i]*ATR_BUFFER and row.close < row.open and wide
        buy = 2*spring + 2*joc + int(volume_ok and (spring or joc)) + int(trend >= 0 and (spring or joc))
        sell = 2*upthrust + 2*sow + int(volume_ok and (upthrust or sow)) + int(trend <= 0 and (upthrust or sow))
        if buy >= MIN_SCORE and buy > sell:
            out[i], score_out[i] = 1, buy
            kind[i] = "Spring" if spring else "JOC"
        elif sell >= MIN_SCORE and sell > buy:
            out[i], score_out[i] = -1, -sell
            kind[i] = "Upthrust" if upthrust else "SOW"

    df = df.copy()
    df["signal"], df["kind"], df["score"] = out, kind, score_out
    return df


def forward_stats(df: pd.DataFrame) -> None:
    for horizon in (1, 5, 10, 20):
        ret = df.close.shift(-horizon)/df.close-1
        rows = df.signal != 0
        directional = ret[rows] * df.loc[rows, "signal"]
        print(f"forward_{horizon}d n={directional.notna().sum()} hit={(directional>0).mean()*100:.1f}% mean={directional.mean()*100:.2f}% median={directional.median()*100:.2f}%")


def flip_strategy(df: pd.DataFrame, allow_short: bool) -> dict:
    equity, peak, max_dd = 1.0, 1.0, 0.0
    position, entry = 0, 0.0
    trades = []
    for i in range(1, len(df)):
        sig = int(df.signal.iloc[i-1])  # signal known only after previous close
        desired = sig if allow_short else (1 if sig == 1 else 0 if sig == -1 else position)
        if sig and desired != position:
            px = float(df.open.iloc[i])
            if position:
                gross = (px/entry-1)*position
                net = gross - 2*COST_PER_SIDE
                equity *= 1+net
                trades.append(net)
                peak = max(peak, equity)
                max_dd = max(max_dd, (peak-equity)/peak)
            position = desired
            entry = px if position else 0.0
    if position:
        px = float(df.close.iloc[-1])
        net = (px/entry-1)*position - 2*COST_PER_SIDE
        equity *= 1+net
        trades.append(net)
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak-equity)/peak)
    wins = sum(x > 0 for x in trades)
    return {"return": equity-1, "trades": len(trades), "win_rate": wins/len(trades) if trades else 0, "max_dd": max_dd}


def main() -> None:
    df = signals(load())
    buys, sells = int((df.signal==1).sum()), int((df.signal==-1).sum())
    print(f"bars={len(df)} from={df.date.min().date()} to={df.date.max().date()}")
    print(f"signals={buys+sells} buys={buys} sells={sells}")
    print(df.loc[df.signal!=0, ["date","kind","score","close"]].to_string(index=False))
    forward_stats(df)
    for short in (False, True):
        r = flip_strategy(df, short)
        print(f"strategy={'long_short' if short else 'long_only'} trades={r['trades']} return={r['return']*100:.2f}% win_rate={r['win_rate']*100:.1f}% max_dd={r['max_dd']*100:.2f}%")
    bh = df.close.iloc[-1]/df.open.iloc[0]-1-2*COST_PER_SIDE
    print(f"buy_hold_return={bh*100:.2f}%")


if __name__ == "__main__":
    main()
