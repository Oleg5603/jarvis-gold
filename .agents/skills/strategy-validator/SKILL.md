---
name: strategy-validator
description: Validate algorithmic trading strategies using train/forward splits, walk-forward tests, robustness checks, and anti-overfitting criteria before promotion.
---

# Strategy Validator

Evaluate robustness for the next experimental stage, not guaranteed profit.

## Protocol

1. Freeze strategy rules and candidate-generation criteria before inspecting holdout results.
2. Separate optimization from untouched forward data by time; prevent overlap and future-data leakage.
3. Rank with net result, drawdown, recovery/profit factor, trade count, period stability, and neighboring-parameter sensitivity.
4. Run walk-forward and suitable stress tests: higher costs, delayed entries, parameter perturbation, and trade-order resampling.
5. Compare with simple baselines and include costs. Flag sparse trades, single-period dependence, parameter cliffs, and implausible results.
6. Keep the number of tried variants visible and account for selection bias.

## Decision

Classify as rejected, needs more data, forward-test candidate, or paper-trading candidate. Live deployment needs a separate explicit decision.

Do not enforce `FAST < MID < SLOW` unless it is part of the strategy specification.
