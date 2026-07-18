"""Прогон MA2_ATRRise с параметрами по умолчанию: ATR-фильтр ON и OFF."""
from hst_parser import read_hst
from backtest import run_variant
from strategy import Params

df, info = read_hst(r"C:\Users\HP\mt4_backtest\history\NMarkets-Demo\XAUUSD60.hst")
print(f"Data range: {df['time'].min()} -> {df['time'].max()}, bars={len(df)}")

for use_filter in (True, False):
    p = Params(fast=5, mid=20, atr_period=14, atr_rise_bars=4,
               sl_mult=1.0, be_trig_mult=1.5, use_atr_filter=use_filter)
    trades, m = run_variant(df, p, "atrrise")
    label = "ATR filter ON" if use_filter else "ATR filter OFF"
    print(f"\n=== atrrise ({label}) ===")
    print(f"trades={m.total_trades} win_rate={m.win_rate:.1f}% "
          f"net_profit={m.net_profit:.2f} profit_factor={m.profit_factor:.2f} "
          f"max_dd={m.max_drawdown:.2f}")
