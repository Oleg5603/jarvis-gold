# EA optimization and comparison — 2026-08-24

## Conditions

- XAUUSD M1, Open prices, spread 330 points
- Fixed 0.01 lot for comparable strategy behavior
- `123_v2` Train: 2026-03-23 to 2026-05-31
- `123_v2` Forward: 2026-06-01 to 2026-07-31
- Baseline comparison: 2026-03-23 to 2026-07-31
- MT4 warned that modelling quality was unavailable; results are suitable for screening, not deployment.

## 123_v2 optimization

MT4 completed 420 genetic passes from a declared 6720-combination search space.

Balanced Train winner (pass 375):

- FAST=4, MID=18, SLOW=10
- SL_MULT=1, TP_K=5
- Train profit: 70.30
- Train PF: 1.21
- Train trades: 302
- Train relative drawdown: 23.26%

Untouched Forward:

- Profit: -81.05
- PF: 0.58
- Trades: 165
- Relative drawdown: 81.19%

Verdict: rejected as overfit. Do not install on a live chart.

## Baseline comparison

| Expert | Profit | PF | Trades | Relative DD |
|---|---:|---:|---:|---:|
| `123.20260814-113938.bak.ex4` | -92.57 | 0.95 | 927 | 97.71% |
| `MA2MA_MID.ex4` | -293.61 | 0.78 | 449 | 98.52% |

`123.bak` is the less weak research base because its PF is closer to 1 and its loss is smaller, but both candidates are blocked from paper/live promotion by catastrophic drawdown and negative expectancy.

## Next experiment

Improve the strategy logic rather than widen parameter search: regime filter, session/spread control, symmetric entry filters, and lower turnover. Re-run Train/Forward with reliable tick data and costs before any paper test.
