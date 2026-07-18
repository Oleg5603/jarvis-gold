"""
Парсер бинарных файлов истории котировок MetaTrader 4 (.hst).

MT4 хранит историю цен в бинарном формате. Файл состоит из заголовка
(header) и последовательности записей-баров (record) фиксированного
размера. Формат записи зависит от версии файла:

  - версия 400 (старый формат): запись 44 байта
        time(int32) open(double) low(double) high(double)
        close(double) volume(double)
  - версия 401 (новый формат, используется в этом проекте): запись 60 байт
        time(int64) open(double) high(double) low(double)
        close(double) tick_volume(int64) spread(int32) real_volume(int64)

Заголовок (header) всегда 148 байт независимо от версии.
Мы читаем поле version из первых 4 байт файла и выбираем нужный
struct-формат автоматически (не жёстко "предполагаем" версию).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HEADER_SIZE = 148

# struct-форматы записей по версии файла
_RECORD_FMT_400 = "<i4d d"  # placeholder, собирается вручную ниже
_REC_400_STRUCT = struct.Struct("<i5d")   # time,open,low,high,close,volume = 4+5*8 = 44 bytes
_REC_401_STRUCT = struct.Struct("<q4d qiq")  # time,O,H,L,C,tick_vol,spread,real_vol = 8+32+8+4+8=60


@dataclass
class HstInfo:
    version: int
    symbol: str
    period_minutes: int
    digits: int
    record_size: int
    n_records: int


def _read_header(f) -> HstInfo:
    raw = f.read(HEADER_SIZE)
    if len(raw) < HEADER_SIZE:
        raise ValueError("Файл слишком короткий для заголовка .hst (меньше 148 байт)")
    version = struct.unpack_from("<i", raw, 0)[0]
    # copyright: 64 bytes @4, symbol: 12 bytes @68, period: int @80,
    # digits: int @84, timesign: int @88, last_sync: int @92
    symbol_raw = raw[68:80]
    symbol = symbol_raw.split(b"\x00", 1)[0].decode("ascii", errors="replace")
    period = struct.unpack_from("<i", raw, 80)[0]
    digits = struct.unpack_from("<i", raw, 84)[0]

    if version == 400:
        rec_size = _REC_400_STRUCT.size
    elif version == 401:
        rec_size = _REC_401_STRUCT.size
    else:
        raise ValueError(
            f"Неподдерживаемая версия .hst файла: {version}. "
            "Поддерживаются только 400 и 401."
        )

    return HstInfo(version=version, symbol=symbol, period_minutes=period,
                    digits=digits, record_size=rec_size, n_records=0)


def read_hst(path: str | Path) -> tuple[pd.DataFrame, HstInfo]:
    """Читает .hst файл целиком и возвращает (DataFrame, HstInfo).

    DataFrame имеет колонки: time (datetime64, UTC-naive, как хранит MT4),
    open, high, low, close, volume — индекс по времени, отсортирован по
    возрастанию.
    """
    path = Path(path)
    with open(path, "rb") as f:
        info = _read_header(f)
        body = f.read()

    rec_size = info.record_size
    n = len(body) // rec_size
    remainder = len(body) % rec_size
    if remainder != 0:
        # обрежем хвост неполной записи (не должно происходить в норме)
        body = body[: n * rec_size]

    times = [None] * n
    opens = [0.0] * n
    highs = [0.0] * n
    lows = [0.0] * n
    closes = [0.0] * n
    vols = [0.0] * n

    if info.version == 401:
        st = _REC_401_STRUCT
        for i in range(n):
            t, o, h, l, c, tick_vol, spread, real_vol = st.unpack_from(body, i * rec_size)
            times[i] = t
            opens[i] = o
            highs[i] = h
            lows[i] = l
            closes[i] = c
            vols[i] = float(tick_vol)
    else:  # version 400
        st = _REC_400_STRUCT
        for i in range(n):
            t, o, l, h, c, v = st.unpack_from(body, i * rec_size)
            times[i] = t
            opens[i] = o
            highs[i] = h
            lows[i] = l
            closes[i] = c
            vols[i] = v

    df = pd.DataFrame({
        "time": pd.to_datetime(times, unit="s", utc=True).tz_localize(None),
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": vols,
    })
    df = df.sort_values("time").drop_duplicates(subset="time").reset_index(drop=True)
    info.n_records = len(df)
    return df, info


if __name__ == "__main__":
    p = r"C:\Users\HP\mt4_backtest\history\NMarkets-Demo\XAUUSD60.hst"
    df, info = read_hst(p)
    print(info)
    print(df.head())
    print(df.tail())
    print("Bars:", len(df))
    print("Range:", df["time"].min(), "->", df["time"].max())
    # sanity check on prices
    print(df[["open", "high", "low", "close"]].describe())
