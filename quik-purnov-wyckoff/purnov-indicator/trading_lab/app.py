"""Purnov Trading Lab: local-only trade training and journal application."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
TRANSCRIPTS = Path(os.environ.get("PURNOV_TRANSCRIPTS", r"D:\Олег_Диск\Пурнов_Расшифровка"))
TRADES_FILE = DATA / "trades.json"
MOEX_FRAGMENTS_FILE = DATA / "moex_fragments.json"

SETUPS = [
    {
        "id": "level-reaction",
        "name": "Реакция цены от уровня",
        "context": "Есть заранее отмеченный уровень и понятное направление старшего контекста.",
        "checks": ["Уровень отмечен до входа", "Есть реакция цены", "Стоп понятен до входа", "Риск укладывается в лимит"],
        "source": "Урок 3 · Сигналы, поиск точек входа · 02:05",
    },
    {
        "id": "effort-result",
        "name": "Усилие и результат",
        "context": "Оцениваются спред бара, объём, прогресс и результат у уровня.",
        "checks": ["Есть уровень", "Сопоставлены объём и спред", "Есть прогресс/отсутствие прогресса", "Вход не делается посреди диапазона"],
        "source": "Урок 3 · Сигналы, поиск точек входа · 02:05–02:16",
    },
    {
        "id": "false-breakout",
        "name": "Ложный пробой",
        "context": "Цена выходит за уровень и возвращается; нужен подтверждённый возврат, а не догадка.",
        "checks": ["Есть заранее известный уровень", "Пробой не удержался", "Возврат подтверждён закрытием", "Стоп за экстремумом сценария"],
        "source": "Уроки по сигналам и сопровождению сделки",
    },
    {
        "id": "impulse-pullback",
        "name": "Импульс и откат",
        "context": "Вход только после оценки импульса и отката, не в погоне за свечой.",
        "checks": ["Импульс имеет результат", "Откат не сломал контекст", "Есть точка отмены", "Цель не хуже 2R"],
        "source": "Урок 3 · Сигналы, поиск точек входа",
    },
]

TRAINING_CASES = [
    {"id": "case-1", "title": "Уровень и реакция", "text": "Цена подошла к заранее отмеченному уровню. Объём вырос, но закрытие осталось внутри диапазона. Где будет вход, стоп и почему?", "outcome": "Сначала фиксируется план. Сам факт объёма — не команда на вход: нужны реакция и точка отмены."},
    {"id": "case-2", "title": "Импульс после диапазона", "text": "После узкого диапазона появился широкий бар с прогрессом. Цена уже далеко от уровня. Что проверите до входа?", "outcome": "Не догонять цену: определить уровень, допустимый откат, стоп и риск. Если стоп неясен — сделка пропускается."},
]


def load_trades() -> list[dict]:
    if not TRADES_FILE.exists():
        return []
    try:
        data = json.loads(TRADES_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_trade(raw: dict) -> dict:
    required = ("ticker", "setup", "entry", "stop", "target")
    trade = {key: str(raw.get(key, "")).strip() for key in required}
    if not all(trade.values()):
        raise ValueError("Заполните инструмент, сетап, вход, стоп и цель.")
    try:
        entry, stop, target = (float(trade[key].replace(",", ".")) for key in ("entry", "stop", "target"))
    except ValueError as exc:
        raise ValueError("Вход, стоп и цель должны быть числами.") from exc
    if entry == stop:
        raise ValueError("Стоп не может совпадать со входом.")
    trade.update({"entry": entry, "stop": stop, "target": target, "notes": str(raw.get("notes", "")).strip(), "result": str(raw.get("result", "planned")).strip(), "created_at": datetime.now(timezone.utc).isoformat()})
    trade["risk_reward"] = round(abs(target - entry) / abs(entry - stop), 2)
    trades = load_trades()
    trade["id"] = f"trade-{len(trades) + 1}-{int(datetime.now().timestamp())}"
    trades.insert(0, trade)
    TRADES_FILE.write_text(json.dumps(trades, ensure_ascii=False, indent=2), encoding="utf-8")
    return trade


def risk_plan(raw: dict) -> dict:
    def number(name: str, positive: bool = True) -> float:
        try:
            value = float(str(raw.get(name, "")).replace(",", "."))
        except ValueError as exc:
            raise ValueError(f"Поле «{name}» должно быть числом.") from exc
        if positive and value <= 0:
            raise ValueError(f"Поле «{name}» должно быть больше нуля.")
        return value
    capital, risk_pct, entry, stop = (number(k) for k in ("capital", "risk_pct", "entry", "stop"))
    max_position_pct = number("max_position_pct") if raw.get("max_position_pct") not in (None, "") else 20.0
    per_unit = abs(entry - stop)
    if per_unit == 0:
        raise ValueError("Вход и стоп не должны совпадать.")
    risk_money = capital * risk_pct / 100
    risk_quantity = int(risk_money // per_unit)
    max_quantity = int((capital * max_position_pct / 100) // entry)
    quantity = min(risk_quantity, max_quantity)
    position_value = quantity * entry
    limited_by = "лимитом позиции" if max_quantity < risk_quantity else "риском до стопа"
    return {"risk_money": round(risk_money, 2), "per_unit": round(per_unit, 4), "quantity": quantity, "position_value": round(position_value, 2), "position_pct": round(position_value / capital * 100, 2), "limited_by": limited_by, "warning": "Расчёт учебный. Проверьте лотность, комиссию и ликвидность вручную."}


TIME_RE = re.compile(r"^\[(\d{6}\.\d)\s*-\s*(\d{6}\.\d)\]\s*(.*)$")


def search_transcripts(query: str) -> list[dict]:
    words = [word.lower() for word in re.findall(r"[\wа-яё]+", query.lower(), flags=re.I) if len(word) > 2]
    if not words or not TRANSCRIPTS.exists():
        return []
    results: list[dict] = []
    for path in TRANSCRIPTS.rglob("*.txt"):
        if path.name.endswith(".partial") or path.name == "manifest.txt":
            continue
        try:
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                match = TIME_RE.match(line)
                if match and all(word in match.group(3).lower() for word in words):
                    results.append({"lesson": path.stem.replace(".flv", "").replace(".avi", ""), "time": match.group(1), "quote": match.group(3)[:360]})
                    if len(results) >= 20:
                        return results
        except OSError:
            continue
    return results


def market_fragments() -> list[dict]:
    """Return locally saved, official MOEX history for the training chart."""
    try:
        payload = json.loads(MOEX_FRAGMENTS_FILE.read_text(encoding="utf-8"))
        fragments = payload.get("fragments", [])
    except (OSError, json.JSONDecodeError):
        return []
    return fragments if isinstance(fragments, list) else []


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "web"), **kwargs)

    def send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/setups":
            return self.send_json(SETUPS)
        if parsed.path == "/api/trades":
            return self.send_json(load_trades())
        if parsed.path == "/api/trainer":
            return self.send_json(TRAINING_CASES)
        if parsed.path == "/api/market-fragments":
            return self.send_json(market_fragments())
        if parsed.path == "/api/search":
            return self.send_json(search_transcripts(parse_qs(parsed.query).get("q", [""])[0]))
        return super().do_GET()

    def do_POST(self) -> None:
        try:
            payload = self.read_json()
            if self.path == "/api/risk":
                return self.send_json(risk_plan(payload))
            if self.path == "/api/trades":
                return self.send_json(save_trade(payload), HTTPStatus.CREATED)
            self.send_json({"error": "Маршрут не найден."}, HTTPStatus.NOT_FOUND)
        except (json.JSONDecodeError, ValueError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)


if __name__ == "__main__":
    host, port = "127.0.0.1", int(os.environ.get("PORT", "8777"))
    print(f"Purnov Trading Lab: http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
