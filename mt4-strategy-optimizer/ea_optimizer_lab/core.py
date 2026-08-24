from __future__ import annotations

import hashlib
import json
import shutil
from datetime import date
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class SetParameter:
    name: str
    value: str
    start: str = ""
    step: str = ""
    stop: str = ""
    optimize: bool = False


def read_set(path: Path) -> tuple[list[str], list[SetParameter]]:
    raw = path.read_bytes()
    text = None
    encodings = ("utf-16",) if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else ("utf-8-sig", "cp1251", "latin-1")
    for encoding in encodings:
        try:
            text = raw.decode(encoding)
            break
        except UnicodeError:
            continue
    if text is None:
        raise ValueError("Не удалось определить кодировку .set")

    comments: list[str] = []
    parameters: list[SetParameter] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(";") or "=" not in line:
            comments.append(line)
            continue
        name, payload = line.split("=", 1)
        fields = payload.split("||")
        parameters.append(SetParameter(
            name=name.strip(),
            value=fields[0].strip(),
            start=fields[1].strip() if len(fields) > 1 else "",
            step=fields[2].strip() if len(fields) > 2 else "",
            stop=fields[3].strip() if len(fields) > 3 else "",
            optimize=(fields[4].strip().upper() == "Y") if len(fields) > 4 else False,
        ))
    if not parameters:
        raise ValueError("В .set не найдены параметры")
    return comments, parameters


def write_set(path: Path, comments: list[str], parameters: list[SetParameter]) -> None:
    lines = [*comments]
    for item in parameters:
        if any(token in item.name for token in ("=", "\r", "\n")):
            raise ValueError(f"Недопустимое имя параметра: {item.name!r}")
        if item.start or item.step or item.stop or item.optimize:
            payload = "||".join((item.value, item.start, item.step, item.stop, "Y" if item.optimize else "N"))
        else:
            payload = item.value
        lines.append(f"{item.name}={payload}")
    path.parent.mkdir(parents=True, exist_ok=True)
    # This MT4 build saves and loads tester presets as Windows ANSI.  UTF-16
    # presets are silently ignored during command-line runs, leaving every
    # optimization flag disabled and producing a single pass.
    try:
        path.write_bytes(("\r\n".join(lines) + "\r\n").encode("cp1251"))
    except UnicodeEncodeError as exc:
        raise ValueError("MT4 поддерживает в .set только латиницу или кириллицу Windows-1251") from exc


def write_tester_ini(path: Path, parameters: list[SetParameter], deposit: int) -> None:
    """Write the native MT4 tester state, including optimization flags."""
    def mt4_value(value: str) -> str:
        lowered = value.strip().lower()
        if lowered == "true":
            return "1"
        if lowered == "false":
            return "0"
        return value.strip()

    lines = [
        "<common>", "positions=2", f"deposit={deposit}", "currency=USD",
        "fitnes=0", "genetic=1", "</common>", "", "<inputs>",
    ]
    for item in parameters:
        value = mt4_value(item.value)
        enabled = item.optimize and bool(item.start and item.step and item.stop)
        lines.extend((
            f"{item.name}={value}",
            f"{item.name},F={'1' if enabled else '0'}",
            f"{item.name},1={mt4_value(item.start) if enabled else value}",
            f"{item.name},2={mt4_value(item.step) if enabled else '0'}",
            f"{item.name},3={mt4_value(item.stop) if enabled else '0'}",
        ))
    lines.extend(("</inputs>", ""))
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_bytes("\r\n".join(lines).encode("cp1251"))
    except UnicodeEncodeError as exc:
        raise ValueError("MT4 поддерживает в tester.ini только Windows-1251") from exc


def safe_export(source: Path, target: Path, comments: list[str], parameters: list[SetParameter]) -> Path | None:
    backup = None
    if target.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = target.with_name(f"{target.stem}.{stamp}.bak{target.suffix}")
        shutil.copy2(target, backup)
    write_set(target, comments, parameters)
    return backup


def install_best_set(target: Path, comments: list[str], parameters: list[SetParameter],
                     audit_path: Path, expert: str, source_run: str) -> Path | None:
    """Install a validated preset with backup and an append-only audit record."""
    backup = safe_export(target if target.exists() else target, target, comments, parameters)
    record = {
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "expert": expert,
        "target": str(target),
        "backup": str(backup) if backup else None,
        "source_run": source_run,
        "sha256": file_sha256(target),
    }
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    return backup


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_portable_mt4(source_program: Path, source_data: Path, target: Path) -> Path:
    """Create an isolated MT4 copy without touching the trading installation."""
    if not (source_program / "terminal.exe").is_file():
        raise ValueError("В исходной папке не найден terminal.exe")
    target.mkdir(parents=True, exist_ok=True)
    for item in source_program.iterdir():
        destination = target / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)
    for name in ("config", "history", "MQL4", "tester"):
        source = source_data / name
        if source.exists():
            shutil.copytree(source, target / name, dirs_exist_ok=True)
    marker = target / "EA_OPTIMIZER_TEST_TERMINAL.txt"
    marker.write_text("Изолированная копия MT4 для тестирования. Не использовать для реальной торговли.\n", encoding="utf-8")
    return target / "terminal.exe"


def save_manifest(path: Path, *, terminal: Path, expert: Path, source_set: Path,
                  symbol: str, timeframe: str, parameters: list[SetParameter]) -> None:
    manifest = {
        "schema": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "terminal": str(terminal),
        "terminal_sha256": file_sha256(terminal),
        "expert": str(expert),
        "expert_sha256": file_sha256(expert),
        "source_set": str(source_set),
        "source_set_sha256": file_sha256(source_set),
        "symbol": symbol,
        "timeframe": timeframe,
        "parameters": [asdict(item) for item in parameters],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def build_mt4_config(path: Path, *, expert_name: str, preset_name: str, symbol: str,
                     timeframe: str, model: int, spread: int, deposit: int,
                     date_from: date, date_to: date, optimize: bool, report: Path) -> None:
    if date_from >= date_to:
        raise ValueError("Дата начала должна быть раньше даты окончания")
    if deposit <= 0 or spread < 0:
        raise ValueError("Проверьте депозит и спред")
    values = {
        "TestExpert": expert_name,
        "TestExpertParameters": preset_name,
        "TestSymbol": symbol,
        "TestPeriod": timeframe,
        "TestModel": str(model),
        "TestSpread": str(spread),
        "TestOptimization": "true" if optimize else "false",
        "TestDateEnable": "true",
        "TestFromDate": date_from.strftime("%Y.%m.%d"),
        "TestToDate": date_to.strftime("%Y.%m.%d"),
        "TestReport": report.name,
        "TestReplaceReport": "true",
        "TestShutdownTerminal": "true",
        "TestDeposit": str(deposit),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    # MT4 uses flat Test* keys. A [Tester] section makes it ignore the run.
    try:
        path.write_text("; EA Optimizer Lab MT4 startup\n" + "\n".join(f"{key}={value}" for key, value in values.items()) + "\n", encoding="cp1251")
    except UnicodeEncodeError as exc:
        raise ValueError("MT4 поддерживает в путях и названиях только латиницу или кириллицу Windows-1251") from exc
