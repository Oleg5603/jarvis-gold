"""
Индикаторы: SMA, ATR (Wilder), ADX (Wilder) — расчёт, максимально близкий
к тому, как их считает сам MT4 (Wilder's smoothing — метод сглаживания
Уайлдера, стандарт для ATR/ADX в MetaTrader).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr


def _wilder_smooth(values: pd.Series, period: int) -> pd.Series:
    """Сглаживание Уайлдера (Wilder's smoothing): аналог экспоненциального
    среднего с alpha = 1/period, но с "затравкой" первого значения как
    простой суммой первых `period` значений (как в MT4/классическом ADX/ATR).
    """
    values = values.to_numpy(dtype=float)
    n = len(values)
    out = np.full(n, np.nan)
    if n < period:
        return pd.Series(out, index=values.__class__ is np.ndarray and range(n) or None)
    # первая точка — простая сумма first `period` valid values starting at index period-1
    first = np.nansum(values[:period])
    out[period - 1] = first
    for i in range(period, n):
        out[i] = out[i - 1] - (out[i - 1] / period) + values[i]
    return pd.Series(out)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    """ATR по Уайлдеру (Wilder), как в MT4 iATR."""
    tr = true_range(high, low, close)
    idx = tr.index
    tr = tr.reset_index(drop=True)
    smoothed_sum = _wilder_smooth(tr.fillna(0.0), period)
    atr_vals = smoothed_sum / period
    atr_vals.index = idx
    return atr_vals


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    """ADX по Уайлдеру (Wilder), как в MT4 iADX (MODE_MAIN)."""
    idx = high.index
    high = high.reset_index(drop=True)
    low = low.reset_index(drop=True)
    close = close.reset_index(drop=True)

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0))
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0))

    tr = true_range(high, low, close).fillna(0.0)

    tr_smooth = _wilder_smooth(tr, period)
    plus_dm_smooth = _wilder_smooth(plus_dm, period)
    minus_dm_smooth = _wilder_smooth(minus_dm, period)

    plus_di = 100.0 * (plus_dm_smooth / tr_smooth)
    minus_di = 100.0 * (minus_dm_smooth / tr_smooth)

    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    dx = dx.fillna(0.0)

    # ADX сам является сглаживанием Уайлдера от DX, с первой точкой —
    # простым средним первых `period` значений DX (начиная там, где DX
    # впервые определён, т.е. индекс period-1 в единицах DX)
    n = len(dx)
    adx_vals = np.full(n, np.nan)
    start = 2 * period - 2  # первый валидный DX примерно на этом индексе (period-1 для DI, +period-1 сдвиг)
    # Более простой и устойчивый способ: применим ту же _wilder_smooth к DX,
    # начиная с первого индекса, где DX не NaN/0-от-старта.
    first_valid = period  # DI начинают быть валидными с индекса period (после первого DM/TR smoothing)
    if n > first_valid + period:
        dx_slice = dx.iloc[first_valid:].reset_index(drop=True)
        adx_smoothed = _wilder_smooth(dx_slice, period)
        # adx_smoothed здесь на самом деле сумма — надо делить на period аналогично ATR
        adx_series_vals = adx_smoothed / period
        adx_vals[first_valid:first_valid + len(adx_series_vals)] = adx_series_vals.to_numpy()

    adx_out = pd.Series(adx_vals)
    adx_out.index = idx
    return adx_out


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Возвращает (macd_line, signal_line, histogram)."""
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
                k_period: int = 14, d_period: int = 3):
    """Стохастический осциллятор: %K (быстрый) и %D (сглаженный, SMA от %K)."""
    lowest_low = low.rolling(k_period, min_periods=k_period).min()
    highest_high = high.rolling(k_period, min_periods=k_period).max()
    k = 100.0 * (close - lowest_low) / (highest_high - lowest_low)
    d = k.rolling(d_period, min_periods=d_period).mean()
    return k, d


def cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
    """Commodity Channel Index."""
    tp = (high + low + close) / 3.0
    sma_tp = tp.rolling(period, min_periods=period).mean()
    mean_dev = tp.rolling(period, min_periods=period).apply(
        lambda x: np.abs(x - x.mean()).mean(), raw=True
    )
    return (tp - sma_tp) / (0.015 * mean_dev)


def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Williams %R: диапазон от -100 (перепроданность) до 0 (перекупленность)."""
    highest_high = high.rolling(period, min_periods=period).max()
    lowest_low = low.rolling(period, min_periods=period).min()
    return -100.0 * (highest_high - close) / (highest_high - lowest_low)


def body_range_ratio(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Отношение тела свечи к полному диапазону (high-low): близко к 1 —
    сильная направленная свеча, близко к 0 — доджи/нерешительность."""
    rng = (high - low).replace(0.0, np.nan)
    return (close - open_).abs() / rng
