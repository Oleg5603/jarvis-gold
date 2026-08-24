from pathlib import Path

from ea_optimizer_lab.report import parse_backtest_report, parse_optimization_report


def test_parse_and_rank_mt4_optimization_report(tmp_path: Path):
    report = tmp_path / "report.htm"
    report.write_text("""
    <table><tr><th>Pass</th><th>Profit</th><th>Total trades</th><th>Profit factor</th><th>Expected</th><th>DD</th><th>DD %</th></tr>
    <tr title="FAST=5;SLOW=20"><td>1</td><td>100</td><td>30</td><td>1.5</td><td>3</td><td>20</td><td>10%</td></tr>
    <tr title="FAST=7;SLOW=23"><td>2</td><td>180</td><td>40</td><td>2.0</td><td>4</td><td>18</td><td>8%</td></tr></table>
    """, encoding="utf-8")
    results = parse_optimization_report(report)
    assert results[0].pass_no == 2
    assert results[0].inputs == {"FAST": "7", "SLOW": "23"}


def test_parse_forward_backtest_summary(tmp_path: Path):
    report = tmp_path / "forward.htm"
    report.write_text("""<table>
    <tr><td>Total net profit:</td><td>120.50</td><td>Profit factor:</td><td>1.42</td></tr>
    <tr><td>Relative drawdown:</td><td>18.20%</td><td>Total trades:</td><td>44</td></tr>
    </table>""", encoding="utf-8")
    summary = parse_backtest_report(report)
    assert summary.passed
    assert summary.trades == 44


def test_parse_mt4_cp1251_report_without_utf16_bom(tmp_path: Path):
    report = tmp_path / "report.htm"
    html = """<html><body><div>Отчёт оптимизации</div><table>
    <tr><td>Pass</td><td>Profit</td><td>Trades</td><td>PF</td><td>Expected</td><td>DD</td><td>DD%</td></tr>
    <tr><td title="FAST=7; SLOW=23;">1</td><td>125.5</td><td>42</td><td>1.8</td><td>2.9</td><td>40</td><td>12.5</td></tr>
    </table></body></html>"""
    report.write_bytes(html.encode("cp1251"))
    results = parse_optimization_report(report)
    assert results[0].profit == 125.5
    assert results[0].inputs == {"FAST": "7", "SLOW": "23"}
