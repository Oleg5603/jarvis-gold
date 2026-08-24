---
name: ea-lab-orchestrator
description: "Coordinate EA Optimizer Lab workflows across multiple MT4 advisors: discovery, queued optimization, ranking, forward validation, SET export, and guarded chart deployment."
---

# EA Lab Orchestrator

Coordinate developer, tester, validator, and risk-review workflows while keeping state recoverable.

## Pipeline

1. Discover advisors in configured MT4 data folders and, where observable, advisors attached to charts. Distinguish detected files from confirmed attachments.
2. Let the user select advisors, symbols, timeframes, intervals, schedules, inputs, and top-candidate count.
3. Build a durable sequential queue. Persist configuration, current item, PID, timestamps, logs, reports, and status after transitions; prevent shared-terminal conflicts.
4. For each item: preflight, optimize, parse, rank, forward-test, run stability/risk gates, and export versioned `.set` files.
5. Present top N with comparable metrics and rejection reasons. Preserve raw reports and exact configuration.
6. Before applying a `.set` to a chart, show terminal/chart/EA/set targets and ask for confirmation. Prepare a template/manual action if safe chart automation is unavailable.

## Safety and correctness

- A launched terminal is not proof of a completed test; require report or journal evidence.
- Never place trades, enable AutoTrading, overwrite live charts, or copy into a live terminal without explicit authorization.
- Resume queues without duplicating completed jobs.
- Do not impose `FAST < MID < SLOW`; honor only constraints declared by the selected EA.

## Status

Expose queued, preparing, running, parsing, validating, awaiting confirmation, completed, failed, and cancelled states with progress and diagnostics.
