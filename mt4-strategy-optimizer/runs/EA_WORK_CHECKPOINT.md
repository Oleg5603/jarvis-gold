# EA optimization checkpoint

Updated: 2026-08-24 Asia/Yekaterinburg

## Objective

Optimize `123_v2`, then compare `123.20260814-113938.bak.ex4` with `МА2МА mid 3.0.ex4` under identical Train/Forward conditions. Commit and push reproducible artifacts.

## Fixed experiment

- Symbol/timeframe: XAUUSD M1
- Model/spread: Open prices / 330 points
- Position size: fixed 0.01 lot for comparability
- Train: 2026-03-23 through 2026-05-31
- Forward target: 2026-06-01 through 2026-07-31
- No generic `FAST < MID < SLOW` constraint for `123_v2`
- Grid: 6720 combinations across FAST, MID, SLOW, SL_MULT, TP_K

## State

- `123_v2.mq4` compiled: 0 errors, 0 warnings.
- Smoke test completed and report created.
- Train optimization configuration prepared: `runs/123_v2-optimize.ini`.
- Train complete: MT4 produced 420 genetic passes from the 6720-combination search space.
- Best balanced Train candidate: pass 375, FAST=4, MID=18, SLOW=10, SL_MULT=1, TP_K=5; profit 70.30, PF 1.21, 302 trades, DD 23.26%.
- Forward completed: profit -81.05, PF 0.58, 165 trades, DD 81.19%; candidate rejected as overfit.
- Baseline comparison completed on 2026-03-23..2026-07-31:
  - `123.20260814-113938.bak`: profit -92.57, PF 0.95, 927 trades, DD 97.71%.
  - `MA2MA_MID`: profit -293.61, PF 0.78, 449 trades, DD 98.52%.
- Research preference: `123.bak` is less weak, but both are blocked from paper/live use.
- Reports and reproducible configs are present under the runtime root and `runs/`.
- Next tomorrow: improve strategy logic and data quality; do not widen optimization until Forward behavior improves.

## Safety

Only the portable tester terminal is used. Live AutoTrading and chart settings are not modified.
