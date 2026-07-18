"""
Расчёт метрик по списку сделок (Trade) и запуск одного прогона бэктеста
для заданного варианта стратегии и набора параметров.

Метрики:
  - net_profit       : суммарный результат в пунктах цены (price points —
                        разница цен, т.к. фиксированный лот и нет модели
                        учёта денег per-pip)
  - total_trades     : число закрытых сделок
  - win_rate         : доля прибыльных сделок, %
  - profit_factor    : сумма прибыльных сделок / |сумма убыточных сделок|
                        (профит-фактор; >1 = стратегия в плюсе)
  - max_drawdown     : максимальная просадка (drawdown) equity-кривой
                        в пунктах цены
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from strategy import Params, Trade, run_backtest, run_backtest_atrrise


@dataclass
class Metrics:
    variant: str
    params: Params
    total_trades: int
    win_rate: float
    net_profit: float
    profit_factor: float
    max_drawdown: float
    gross_profit: float
    gross_loss: float
    avg_trade: float


def compute_metrics(trades: list[Trade], variant: str, params: Params) -> Metrics:
    if not trades:
        return Metrics(variant, params, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    pnls = np.array([t.pnl for t in trades], dtype=float)
    total_trades = len(pnls)
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    win_rate = 100.0 * len(wins) / total_trades if total_trades else 0.0
    gross_profit = wins.sum() if len(wins) else 0.0
    gross_loss = losses.sum() if len(losses) else 0.0  # negative number
    net_profit = pnls.sum()
    profit_factor = (gross_profit / abs(gross_loss)) if gross_loss < 0 else (np.inf if gross_profit > 0 else 0.0)

    equity = np.cumsum(pnls)
    running_max = np.maximum.accumulate(equity)
    drawdown = running_max - equity
    max_dd = drawdown.max() if len(drawdown) else 0.0

    avg_trade = net_profit / total_trades if total_trades else 0.0

    return Metrics(
        variant=variant, params=params, total_trades=total_trades, win_rate=win_rate,
        net_profit=net_profit, profit_factor=profit_factor, max_drawdown=max_dd,
        gross_profit=gross_profit, gross_loss=gross_loss, avg_trade=avg_trade,
    )


def run_variant(df: pd.DataFrame, params: Params, variant: str,
                 atr_cache: pd.Series | None = None,
                 adx_cache: pd.Series | None = None) -> tuple[list[Trade], Metrics]:
    if variant == "atrrise":
        trades = run_backtest_atrrise(df, params, atr_cache)
    else:
        trades = run_backtest(df, params, variant, atr_cache, adx_cache)
    metrics = compute_metrics(trades, variant, params)
    return trades, metrics


if __name__ == "__main__":
    from hst_parser import read_hst

    df, info = read_hst(r"C:\Users\HP\mt4_backtest\history\NMarkets-Demo\XAUUSD60.hst")
    print(f"Data range: {df['time'].min()} -> {df['time'].max()}, bars={len(df)}")

    default_params = Params()
    for variant in ("baseline", "adx", "no_atr"):
        trades, m = run_variant(df, default_params, variant)
        print(f"\n=== {variant} ===")
        print(f"trades={m.total_trades} win_rate={m.win_rate:.1f}% "
              f"net_profit={m.net_profit:.2f} profit_factor={m.profit_factor:.2f} "
              f"max_dd={m.max_drawdown:.2f}")
