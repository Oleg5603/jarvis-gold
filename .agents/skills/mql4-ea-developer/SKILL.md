---
name: mql4-ea-developer
description: Develop, repair, and review MetaTrader 4 Expert Advisors and indicators in MQL4, including parameters, order logic, compilation diagnostics, and safe tester integration.
---

# MQL4 EA Developer

Build or modify `.mq4` sources and produce a compilable `.ex4` only when the local MetaEditor/compiler is available.

## Workflow

1. Inspect source, inputs, symbol/timeframe assumptions, broker digit handling, and tester logs before changing behavior.
2. Preserve the strategy specification. Do not invent trading rules or silently rename/remove `input` parameters.
3. Separate signal generation, position sizing, order execution, and position management so each can be tested.
4. Handle 3/5-digit quotes, lot step and limits, stop level, spread, slippage, duplicate orders, Magic Number, and error codes.
5. Compile with warnings treated as defects; report compiler/source paths, errors, warnings, and output artifact.
6. Test in Strategy Tester before proposing use. Never enable live trading or place real orders without explicit authorization.

## Parameter rules

- Infer relationships only from documented strategy logic or source code.
- Do **not** impose `FAST < MID < SLOW` or any other ordering by default.
- Reject only invalid platform values or explicit strategy constraints; explain every rejected combination.
- Keep risk-based lot sizing separate from fixed-lot mode.

## Deliverable

Return changed files, compile status, assumptions, known limitations, and the exact next test. Never claim profitability from compilation or one backtest.
