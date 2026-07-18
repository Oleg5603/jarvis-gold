"""Grid search только для MA2_ATRRise (4-й вариант), без повторного
перебора baseline/adx/no_atr (уже сделан ранее и сохранён в CSV)."""
from hst_parser import read_hst
from strategy import Params
import indicators as ind
from optimize import optimize_atrrise, top_tables

df, info = read_hst(r"C:\Users\HP\mt4_backtest\history\NMarkets-Demo\XAUUSD60.hst")
default_p = Params()
print("Precomputing shared ATR(14) cache...")
atr_cache = ind.atr(df["high"], df["low"], df["close"], default_p.atr_period)

res = optimize_atrrise(df, atr_cache)
res.to_csv("opt_results_atrrise.csv", index=False)

top_p, top_pf = top_tables(res)
print("\n=== atrrise: TOP-5 by net_profit ===")
print(top_p.to_string(index=False))
print("\n=== atrrise: TOP-5 by profit_factor ===")
print(top_pf.to_string(index=False))
