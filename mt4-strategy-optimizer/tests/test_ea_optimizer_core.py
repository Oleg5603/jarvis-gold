from datetime import date
from pathlib import Path

from ea_optimizer_lab.core import SetParameter, build_mt4_config, install_best_set, prepare_portable_mt4, read_set, safe_export, save_manifest, write_tester_ini


def test_set_round_trip_and_backup(tmp_path: Path):
    source = tmp_path / "source.set"
    source.write_text("; header\nFast=5||1||1||20||Y\nUseFilter=true\n", encoding="utf-8")
    comments, params = read_set(source)
    assert params[0] == SetParameter("Fast", "5", "1", "1", "20", True)
    target = tmp_path / "result.set"
    safe_export(source, target, comments, params)
    assert not target.read_bytes().startswith((b"\xff\xfe", b"\xfe\xff"))
    assert b"Fast=5||1||1||20||Y" in target.read_bytes()
    assert b"\r\r\n" not in target.read_bytes()
    _, restored = read_set(target)
    assert restored == params
    backup = safe_export(source, target, comments, params)
    assert backup and backup.exists()


def test_manifest_contains_hashes(tmp_path: Path):
    terminal = tmp_path / "terminal.exe"
    expert = tmp_path / "ea.ex4"
    preset = tmp_path / "ea.set"
    for path in (terminal, expert, preset):
        path.write_bytes(path.name.encode())
    output = tmp_path / "manifest.json"
    save_manifest(output, terminal=terminal, expert=expert, source_set=preset,
                  symbol="XAUUSD", timeframe="H1", parameters=[SetParameter("Risk", "1")])
    text = output.read_text(encoding="utf-8")
    assert '"terminal_sha256"' in text
    assert '"expert_sha256"' in text


def test_build_mt4_config_contains_interval_and_optimization(tmp_path: Path):
    output = tmp_path / "test.ini"
    build_mt4_config(output, expert_name="MyEA", preset_name="trial.set", symbol="XAUUSD",
                     timeframe="M15", model=0, spread=15, deposit=10000,
                     date_from=date(2025, 1, 1), date_to=date(2025, 4, 1),
                     optimize=True, report=tmp_path / "report.htm")
    text = output.read_text(encoding="utf-8")
    assert "TestFromDate=2025.01.01" in text
    assert "TestToDate=2025.04.01" in text
    assert "TestOptimization=true" in text
    assert "[Tester]" not in text
    assert "TestReport=report.htm" in text


def test_build_mt4_config_supports_cyrillic_expert(tmp_path: Path):
    output=tmp_path/"cyrillic.ini"
    build_mt4_config(output,expert_name="МА2МА",preset_name="test.set",symbol="XAUUSD",timeframe="M1",
                     model=2,spread=330,deposit=1000,date_from=date(2025,1,1),date_to=date(2026,1,1),optimize=True,report=tmp_path/"report.htm")
    assert "МА2МА" in output.read_text(encoding="cp1251")


def test_write_tester_ini_enables_native_mt4_optimization_ranges(tmp_path: Path):
    output = tmp_path / "MyEA.ini"
    write_tester_ini(output, [
        SetParameter("FAST", "7", "4", "1", "10", True),
        SetParameter("USE_FILTER", "true"),
    ], 1000)
    text = output.read_text(encoding="cp1251")
    assert "FAST,F=1" in text
    assert "FAST,1=4\nFAST,2=1\nFAST,3=10" in text.replace("\r\n", "\n")
    assert "USE_FILTER=1" in text
    assert "USE_FILTER,F=0" in text


def test_prepare_portable_mt4_copies_program_and_data(tmp_path: Path):
    program, data, target = tmp_path / "program", tmp_path / "data", tmp_path / "portable"
    program.mkdir(); data.mkdir()
    (program / "terminal.exe").write_bytes(b"terminal")
    (data / "MQL4" / "Experts").mkdir(parents=True)
    (data / "MQL4" / "Experts" / "ea.ex4").write_bytes(b"ea")
    terminal = prepare_portable_mt4(program, data, target)
    assert terminal.is_file()
    assert (target / "MQL4" / "Experts" / "ea.ex4").is_file()
    assert (target / "EA_OPTIMIZER_TEST_TERMINAL.txt").is_file()


def test_install_best_set_creates_backup_and_audit(tmp_path: Path):
    target = tmp_path / "EA_BEST.set"
    target.write_text("FAST=5\n", encoding="utf-8")
    audit = tmp_path / "audit.jsonl"
    backup = install_best_set(target, [], [SetParameter("FAST", "7")], audit, "EA", "pass-2")
    assert backup and backup.exists()
    assert read_set(target)[1][0].value == "7"
    assert '"source_run": "pass-2"' in audit.read_text(encoding="utf-8")
