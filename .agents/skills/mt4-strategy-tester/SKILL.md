---
name: mt4-strategy-tester
description: Configure and operate reproducible MetaTrader 4 strategy tests and optimizations, generate SET and INI inputs, diagnose short-lived terminal runs, and parse tester reports.
---

# MT4 Strategy Tester

Use for one-off, scheduled, or sequential testing of MT4 Expert Advisors.

## Preconditions

Resolve terminal, data directory, EA, symbol, timeframe, dates, model, spread, deposit, currency, and ranges. Confirm history exists and terminal/EA builds are compatible.

## Execution

1. Use an isolated test terminal when available; do not disturb a trading terminal.
2. Generate configuration files in the encoding and date format accepted by that MT4 build. Avoid non-ASCII paths/config values when unsupported.
3. Validate enabled ranges: start, step, and stop must be present and directionally valid. Do not impose `FAST < MID < SLOW` unless the EA requires it.
4. Launch one run at a time; record PID, start time, config, and report paths; monitor terminal and tester journals.
5. Treat exit without a report as failure. Diagnose logs/configuration instead of reporting success.
6. Parse all optimization passes and retain raw reports with normalized results.

## Progress and scheduling

Estimate progress from completed versus expected passes when possible; otherwise show running state and elapsed time. Prevent overlapping scheduled runs and persist queue/status for recovery.

## Result

Report whether the test actually ran, pass count, failures, report path, journal evidence, and reproducibility inputs.
