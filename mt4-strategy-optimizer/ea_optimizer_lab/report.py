from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


@dataclass
class OptimizationResult:
    pass_no: int
    profit: float
    trades: int
    profit_factor: float
    drawdown_pct: float
    inputs: dict[str, str]

    @property
    def score(self) -> float:
        if self.trades < 10 or self.drawdown_pct >= 70:
            return float("-inf")
        return self.profit * min(self.profit_factor, 5.0) / max(self.drawdown_pct, 1.0)


@dataclass
class BacktestSummary:
    profit: float
    trades: int
    profit_factor: float
    drawdown_pct: float

    @property
    def passed(self) -> bool:
        return self.profit > 0 and self.trades >= 10 and self.profit_factor >= 1.1 and self.drawdown_pct < 40


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[tuple[list[str], str]] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.title = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr":
            self.row, self.title = [], attrs.get("title", "")
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []
            self.title += " " + attrs.get("title", "")

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(" ".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append((self.row, self.title.strip()))
            self.row = None


def _number(value: str) -> float:
    cleaned = value.replace("\xa0", "").replace(" ", "").replace("%", "").replace(",", ".")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", cleaned)
    if not match:
        raise ValueError(value)
    return float(match.group())


def _inputs(text: str) -> dict[str, str]:
    return {name: value for name, value in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^;,\s]+)", text)}


def _decode_mt4_report(path: Path) -> str:
    raw = path.read_bytes()
    encodings = ("utf-16",) if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else ("utf-8-sig", "cp1251", "latin-1")
    for encoding in encodings:
        try:
            return raw.decode(encoding)
        except UnicodeError:
            continue
    raise ValueError("Не удалось прочитать отчёт MT4")


def parse_optimization_report(path: Path) -> list[OptimizationResult]:
    text = _decode_mt4_report(path)
    parser = _TableParser()
    parser.feed(text)
    results: list[OptimizationResult] = []
    for cells, title in parser.rows:
        if len(cells) < 7:
            continue
        try:
            pass_no = int(_number(cells[0]))
            results.append(OptimizationResult(pass_no, _number(cells[1]), int(_number(cells[2])),
                                              _number(cells[3]), _number(cells[6]), _inputs(title)))
        except (ValueError, OverflowError):
            continue
    if not results:
        raise ValueError("В отчёте не найдены проходы оптимизации")
    return sorted(results, key=lambda item: item.score, reverse=True)


def parse_backtest_report(path: Path) -> BacktestSummary:
    text = _decode_mt4_report(path)
    parser = _TableParser()
    parser.feed(text)
    pairs: dict[str, str] = {}
    for cells, _ in parser.rows:
        for index in range(len(cells) - 1):
            key = cells[index].strip().rstrip(":").lower()
            if key in ("total net profit", "чистая прибыль", "profit factor", "профит-фактор",
                       "total trades", "всего сделок", "relative drawdown", "относительная просадка"):
                pairs[key] = cells[index + 1]
    def pick(*keys: str) -> str:
        for key in keys:
            if key in pairs:
                return pairs[key]
        raise ValueError(f"В отчёте нет показателя: {keys[0]}")
    try:
        return BacktestSummary(
            _number(pick("total net profit", "чистая прибыль")),
            int(_number(pick("total trades", "всего сделок"))),
            _number(pick("profit factor", "профит-фактор")),
            _number(pick("relative drawdown", "относительная просадка")),
        )
    except ValueError:
        # Some MT4 builds write already-corrupted Cyrillic labels (������), so
        # decoding cannot recover their names. The standard report table keeps
        # a stable layout; use it only when its trade header is unambiguous.
        header = next((index for index, (cells, _) in enumerate(parser.rows)
                       if "S / L" in cells and "T / P" in cells), None)
        if header is None or header < 11:
            raise
        net_row = parser.rows[header - 11][0]
        factor_row = parser.rows[header - 10][0]
        drawdown_row = parser.rows[header - 9][0]
        trades_row = parser.rows[header - 7][0]
        if min(len(net_row), len(factor_row), len(drawdown_row), len(trades_row)) < 2:
            raise
        return BacktestSummary(
            _number(net_row[1]),
            int(_number(trades_row[1])),
            _number(factor_row[1]),
            _number(drawdown_row[-1]),
        )
