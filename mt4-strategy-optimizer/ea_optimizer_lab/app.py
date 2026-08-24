from __future__ import annotations

import os
import ctypes
import subprocess
import sys
import time
import json
from dataclasses import asdict
import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .core import SetParameter, build_mt4_config, install_best_set, prepare_portable_mt4, read_set, safe_export, save_manifest, write_tester_ini
from .report import BacktestSummary, OptimizationResult, parse_backtest_report, parse_optimization_report
from .validation import stability_neighbours
from .storage import HistoryStore

try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("OlegTools.MT4Optimizer")
except Exception:
    pass

DEFAULT_MT4 = Path(r"C:\Program Files (x86)\NMarkets Limited MT4 Terminal\terminal.exe")
DEFAULT_DATA = Path(os.environ.get("APPDATA", "")) / "MetaQuotes" / "Terminal" / "8C90EA2342AB06D2F18007B06632DE4B"

def parse_user_date(value: str) -> date:
    value=value.strip()
    for fmt in ("%Y-%m-%d","%d.%m.%Y"):
        try:
            if fmt=="%Y-%m-%d": return date.fromisoformat(value)
            from datetime import datetime
            return datetime.strptime(value,fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Неверная дата «{value}». Используйте ГГГГ-ММ-ДД, например 2026-05-25")


def parse_top_n(value: str) -> int:
    try:
        count = int(value.strip())
    except ValueError as exc:
        raise ValueError("TOP должен быть целым числом от 1 до 200") from exc
    if not 1 <= count <= 200:
        raise ValueError("TOP должен быть от 1 до 200")
    return count


class OptimizerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("EA Optimizer Lab — MT4 MVP")
        self.geometry("1180x720")
        self.minsize(900, 560)
        self.comments: list[str] = []
        self.parameters: list[SetParameter] = []
        self.source_set: Path | None = None
        self.terminal = tk.StringVar(value=str(DEFAULT_MT4))
        self.expert = tk.StringVar()
        self.symbol = tk.StringVar(value="XAUUSD")
        self.timeframe = tk.StringVar(value="H1")
        today = date.today()
        self.date_from = tk.StringVar(value=(today - timedelta(days=90)).isoformat())
        self.date_to = tk.StringVar(value=today.isoformat())
        self.deposit = tk.StringVar(value="10000")
        self.spread = tk.StringVar(value="0")
        self.model = tk.StringVar(value="Every tick")
        self.optimize = tk.BooleanVar(value=True)
        self.schedule_mode = tk.StringVar(value="Выключен")
        self.schedule_time = tk.StringVar(value="09:00")
        self.top_n = tk.StringVar(value="20")
        self.top_button_text = tk.StringVar(value="TOP-20")
        self.top_n.trace_add("write", self._sync_top_label)
        self.mt4_process: subprocess.Popen | None = None
        self.started_at = 0.0
        self.results: list[OptimizationResult] = []
        self.report_path: Path | None = None
        self.forward_summary: BacktestSummary | None = None
        self.run_stage = "idle"
        self.stability_jobs: list[tuple[str, Path, Path]] = []
        self.stability_results: list[tuple[str, BacktestSummary]] = []
        self.stability_total = 0
        self.stability_passed = False
        self.store = HistoryStore(Path(__file__).parents[1] / "data" / "history.db")
        self.cycle_state={"MT4":"не подготовлен","Train":"ожидает","Forward":"ожидает","Stability":"ожидает","Лучший .set":"не создан","Установка":"не выполнена","Автоцикл":"не запускался"}
        self.status = tk.StringVar(value="Выберите советник и файл настроек .set")
        self._build()
        self._load_settings()
        self.protocol("WM_DELETE_WINDOW", self._close_app)

    def _build(self) -> None:
        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")
        self._path_row(top, 0, "MT4", self.terminal, self.pick_terminal)
        self._path_row(top, 1, "Советник", self.expert, self.pick_expert)
        ttk.Label(top, text="Символ").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(top, textvariable=self.symbol, width=18).grid(row=2, column=1, sticky="w")
        ttk.Label(top, text="Таймфрейм").grid(row=2, column=2, sticky="e", padx=(16, 6))
        ttk.Combobox(top, textvariable=self.timeframe, values=("M1", "M5", "M15", "M30", "H1", "H4", "D1"), width=8, state="readonly").grid(row=2, column=3, sticky="w")
        ttk.Button(top, text="Открыть .set", command=self.open_set).grid(row=2, column=4, padx=8)
        settings = ttk.LabelFrame(self, text="Интервал и режим тестирования", padding=8)
        settings.pack(fill="x", padx=12, pady=(0, 8))
        ttk.Label(settings, text="С").grid(row=0, column=0)
        ttk.Entry(settings, textvariable=self.date_from, width=12).grid(row=0, column=1, padx=(4, 12))
        ttk.Label(settings, text="По").grid(row=0, column=2)
        ttk.Entry(settings, textvariable=self.date_to, width=12).grid(row=0, column=3, padx=(4, 12))
        ttk.Label(settings, text="Депозит").grid(row=0, column=4)
        ttk.Entry(settings, textvariable=self.deposit, width=10).grid(row=0, column=5, padx=(4, 12))
        ttk.Label(settings, text="Спред (points)").grid(row=0, column=6)
        ttk.Entry(settings, textvariable=self.spread, width=8).grid(row=0, column=7, padx=(4, 12))
        ttk.Label(settings, text="Модель").grid(row=0, column=8)
        ttk.Combobox(settings, textvariable=self.model, values=("Every tick", "Control points", "Open prices"), width=15, state="readonly").grid(row=0, column=9, padx=4)
        ttk.Checkbutton(settings, text="Оптимизация", variable=self.optimize).grid(row=0, column=10, padx=12)
        ttk.Label(settings, text="Показывать TOP").grid(row=0, column=11)
        ttk.Combobox(settings, textvariable=self.top_n, values=("5", "10", "20", "50"), width=6).grid(row=0, column=12, padx=4)

        schedule = ttk.LabelFrame(self, text="Автоматический запуск", padding=8)
        schedule.pack(fill="x", padx=12, pady=(0, 8))
        ttk.Combobox(schedule, textvariable=self.schedule_mode, state="readonly", width=22,
                     values=("Выключен", "1 раз в сутки", "2 раза в сутки", "1 раз в неделю", "3 раза в неделю", "4 раза в неделю")).pack(side="left")
        ttk.Label(schedule, text="Время").pack(side="left", padx=(16, 4))
        ttk.Entry(schedule, textvariable=self.schedule_time, width=7).pack(side="left")
        ttk.Button(schedule, text="Сохранить расписание", command=self.save_schedule).pack(side="left", padx=12)
        ttk.Button(schedule, text="Статус авто", command=self.show_auto_status).pack(side="left", padx=4)
        ttk.Button(schedule, text="Подготовить тестовый MT4", command=self.setup_test_terminal).pack(side="left", padx=6)
        ttk.Label(schedule, text="Неделя: Пн / Пн-Ср-Пт / Пн-Вт-Чт-Сб").pack(side="left", padx=8)
        top.columnconfigure(1, weight=1)

        columns = ("name", "value", "start", "step", "stop", "optimize")
        self.table = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        labels = ("Параметр", "Значение", "Начало", "Шаг", "Конец", "Оптимизировать")
        widths = (300, 140, 120, 120, 120, 110)
        for col, label, width in zip(columns, labels, widths):
            self.table.heading(col, text=label)
            self.table.column(col, width=width, anchor="center" if col != "name" else "w")
        self.table.pack(fill="both", expand=True, padx=12)
        self.table.bind("<Double-1>", self.edit_cell)

        bottom = ttk.Frame(self, padding=12)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Сохранить проект", command=self.save_project).pack(side="left")
        ttk.Button(bottom, text="Экспортировать .set", command=self.export_set).pack(side="left", padx=8)
        ttk.Button(bottom, text="▶ Запустить MT4", command=self.start_mt4).pack(side="left", padx=16)
        ttk.Button(bottom, text="Автодиапазоны", command=self.fill_safe_ranges).pack(side="left", padx=4)
        ttk.Button(bottom, text="Открыть отчёт", command=self.open_report).pack(side="left", padx=4)
        ttk.Button(bottom, text="Проверить лучший Forward", command=self.start_forward).pack(side="left", padx=4)
        ttk.Button(bottom, text="Stability", command=self.start_stability).pack(side="left", padx=4)
        ttk.Button(bottom, text="Экспорт лучшего .set", command=self.export_best).pack(side="left", padx=4)
        ttk.Button(bottom, textvariable=self.top_button_text, command=self.show_top).pack(side="left", padx=4)
        ttk.Button(bottom, text="История", command=self.show_history).pack(side="left", padx=4)
        ttk.Button(bottom, text="Графики", command=self.show_charts).pack(side="left", padx=4)
        ttk.Button(bottom, text="Состояние цикла", command=self.show_cycle_status).pack(side="left", padx=4)
        ttk.Button(bottom, text="Установить лучший .set", command=self.apply_best).pack(side="left", padx=4)
        self.progress = ttk.Progressbar(bottom, mode="indeterminate", length=180)
        self.progress.pack(side="left", padx=8)
        ttk.Label(bottom, textvariable=self.status).pack(side="right")

    def _path_row(self, parent: ttk.Frame, row: int, label: str, variable: tk.StringVar, command) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, columnspan=3, sticky="ew", padx=6)
        ttk.Button(parent, text="Выбрать", command=command).grid(row=row, column=4)

    def _sync_top_label(self, *_args) -> None:
        value = self.top_n.get().strip()
        self.top_button_text.set(f"TOP-{value}" if value.isdigit() else "TOP")

    def pick_terminal(self) -> None:
        value = filedialog.askopenfilename(filetypes=[("MT4 terminal", "terminal.exe"), ("EXE", "*.exe")])
        if value:
            self.terminal.set(value)

    def pick_expert(self) -> None:
        initial = DEFAULT_DATA / "MQL4" / "Experts"
        value = filedialog.askopenfilename(initialdir=initial, filetypes=[("MT4 Expert", "*.ex4"), ("MQL4 source", "*.mq4")])
        if value:
            self.expert.set(value)

    def open_set(self) -> None:
        initial = DEFAULT_DATA / "MQL4" / "Presets"
        value = filedialog.askopenfilename(initialdir=initial, filetypes=[("MT4 preset", "*.set")])
        if not value:
            return
        try:
            self.comments, self.parameters = read_set(Path(value))
            self.source_set = Path(value)
            self._refresh()
            self.status.set(f"Загружено параметров: {len(self.parameters)}")
        except Exception as exc:
            messagebox.showerror("Ошибка .set", str(exc))

    def _refresh(self) -> None:
        self.table.delete(*self.table.get_children())
        for index, item in enumerate(self.parameters):
            self.table.insert("", "end", iid=str(index), values=(item.name, item.value, item.start, item.step, item.stop, "Да" if item.optimize else "Нет"))

    def fill_safe_ranges(self) -> None:
        excluded=("MAGIC","RISK","LOTS","LOT","SLIPPAGE")
        changed=0
        for item in self.parameters:
            upper=item.name.upper()
            if any(token in upper for token in excluded):
                item.optimize=False; item.start=item.step=item.stop=""; continue
            low_value=item.value.lower()
            if low_value in ("true","false"):
                item.start,item.step,item.stop,item.optimize="0","1","1",True; changed+=1; continue
            try: value=float(item.value)
            except ValueError:
                item.optimize=False; continue
            if "METHOD" in upper:
                item.start,item.step,item.stop="0","1","3"
            elif value.is_integer():
                center=int(value); item.start=str(max(1,center-max(2,round(abs(center)*.4)))); item.step="1"; item.stop=str(center+max(2,round(abs(center)*.4)))
            else:
                step=max(abs(value)*.1,.01); item.start=f"{max(0,value*.5):.6g}"; item.step=f"{step:.6g}"; item.stop=f"{value*1.5:.6g}"
            item.optimize=True; changed+=1
        self._refresh(); self.status.set(f"Автодиапазоны заполнены: {changed}; риск и MAGIC исключены")

    def edit_cell(self, event) -> None:
        row = self.table.identify_row(event.y)
        column = self.table.identify_column(event.x)
        if not row or column == "#1":
            return
        index, col_index = int(row), int(column[1:]) - 1
        item = self.parameters[index]
        attrs = ("name", "value", "start", "step", "stop", "optimize")
        attr = attrs[col_index]
        if attr == "optimize":
            item.optimize = not item.optimize
            self._refresh()
            return
        x, y, width, height = self.table.bbox(row, column)
        editor = ttk.Entry(self.table)
        editor.insert(0, str(getattr(item, attr)))
        editor.place(x=x, y=y, width=width, height=height)
        editor.focus_set()
        def commit(_event=None):
            setattr(item, attr, editor.get().strip())
            editor.destroy()
            self._refresh()
        editor.bind("<Return>", commit)
        editor.bind("<FocusOut>", commit)

    def _validate(self) -> tuple[Path, Path, Path]:
        terminal, expert = Path(self.terminal.get()), Path(self.expert.get())
        if not terminal.is_file():
            raise ValueError("Не найден terminal.exe")
        if not expert.is_file():
            raise ValueError("Выберите советник .ex4")
        if self.source_set is None or not self.parameters:
            raise ValueError("Откройте файл .set")
        return terminal, expert, self.source_set

    def save_project(self) -> None:
        try:
            terminal, expert, source = self._validate()
            target = filedialog.asksaveasfilename(defaultextension=".json", initialfile="experiment.json", filetypes=[("Manifest", "*.json")])
            if target:
                save_manifest(Path(target), terminal=terminal, expert=expert, source_set=source, symbol=self.symbol.get().strip(), timeframe=self.timeframe.get(), parameters=self.parameters)
                self.status.set(f"Проект сохранён: {target}")
        except Exception as exc:
            messagebox.showerror("Проект не сохранён", str(exc))

    def export_set(self) -> None:
        try:
            self._validate()
            target = filedialog.asksaveasfilename(defaultextension=".set", initialfile="optimized.set", filetypes=[("MT4 preset", "*.set")])
            if target:
                backup = safe_export(self.source_set, Path(target), self.comments, self.parameters)
                suffix = f"; backup: {backup.name}" if backup else ""
                self.status.set(f".set сохранён: {target}{suffix}")
        except Exception as exc:
            messagebox.showerror("Экспорт не выполнен", str(exc))

    def start_mt4(self) -> None:
        try:
            terminal, config, started, finished = self._prepare_run()
            isolated = (terminal.parent / "EA_OPTIMIZER_TEST_TERMINAL.txt").exists()
            args = [str(terminal)]
            if isolated:
                args.append("/portable")
            args.append(str(config.resolve()))
            self.mt4_process = subprocess.Popen(args, cwd=str(terminal.parent))
            self.run_stage = "train"
            self.cycle_state["Train"]="выполняется"
            self.started_at = time.monotonic()
            self.progress.start(12)
            self.status.set(f"MT4 запущен; период {started} — {finished}")
            self.after(1000, self._poll_process)
        except Exception as exc:
            messagebox.showerror("MT4 не запущен", str(exc))

    def _prepare_run(self) -> tuple[Path, Path, date, date]:
        terminal, expert, source = self._validate()
        if self.optimize.get() and not any(item.optimize for item in self.parameters):
            raise ValueError("Оптимизация включена, но ни один параметр не отмечен «Да». Задайте диапазон и дважды нажмите «Нет».")
        incomplete=[item.name for item in self.parameters if item.optimize and not (item.start and item.step and item.stop)]
        if self.optimize.get() and incomplete:
            shown=", ".join(incomplete[:6])+("…" if len(incomplete)>6 else "")
            raise ValueError(f"Не заполнены Начало/Шаг/Конец: {shown}")
        started, finished = parse_user_date(self.date_from.get()), parse_user_date(self.date_to.get())
        isolated = (terminal.parent / "EA_OPTIMIZER_TEST_TERMINAL.txt").exists()
        data_dir = terminal.parent if isolated else DEFAULT_DATA
        preset_dir = data_dir / "tester"
        run_dir = Path(__file__).parents[1] / "runs"
        run_dir.mkdir(exist_ok=True)
        preset = preset_dir / "EA_Optimizer_Lab.set"
        safe_export(source, preset, self.comments, self.parameters)
        write_tester_ini(preset_dir / f"{expert.stem}.ini", self.parameters, int(self.deposit.get()))
        report = terminal.parent / "latest-report.htm"
        self.report_path = report
        config = run_dir / "latest-test.ini"
        model = {"Every tick": 0, "Control points": 1, "Open prices": 2}[self.model.get()]
        train_end = started + (finished - started) * 7 // 10 if self.optimize.get() else finished
        build_mt4_config(config, expert_name=expert.stem, preset_name=preset.name,
                         symbol=self.symbol.get().strip(), timeframe=self.timeframe.get(),
                         model=model, spread=int(self.spread.get()), deposit=int(self.deposit.get()),
                         date_from=started, date_to=train_end, optimize=self.optimize.get(), report=report)
        return terminal, config, started, finished

    def setup_test_terminal(self) -> None:
        try:
            source_terminal = Path(self.terminal.get())
            if not source_terminal.is_file():
                raise ValueError("Не найден исходный terminal.exe")
            target = Path(__file__).parents[1] / "runtime" / "mt4-terminal"
            self.status.set("Копирование MT4 и истории…")
            self.update_idletasks()
            terminal = prepare_portable_mt4(source_terminal.parent, DEFAULT_DATA, target)
            self.terminal.set(str(terminal))
            self.cycle_state["MT4"]="готов"
            self.status.set("Тестовый MT4 подготовлен и выбран")
            messagebox.showinfo("Готово", f"Тестовый MT4 создан:\n{terminal}\n\nОн изолирован от торгового терминала.")
        except Exception as exc:
            messagebox.showerror("Тестовый MT4 не подготовлен", str(exc))

    def _poll_process(self) -> None:
        if self.mt4_process is None:
            return
        elapsed = int(time.monotonic() - self.started_at)
        if self.mt4_process.poll() is None:
            self.status.set(f"MT4 работает: {elapsed // 60:02d}:{elapsed % 60:02d}")
            self.after(1000, self._poll_process)
        else:
            self.progress.stop()
            if self.report_path and self.report_path.exists():
                try:
                    if self.run_stage == "forward":
                        self.forward_summary = parse_backtest_report(self.report_path)
                        state = "ПРОЙДЕН" if self.forward_summary.passed else "НЕ ПРОЙДЕН"
                        self.cycle_state["Forward"]=state.lower()
                        self.store.add_validation(self.symbol.get(), self.timeframe.get(), Path(self.expert.get()).name,
                                                  "forward", self.forward_summary, "passed" if self.forward_summary.passed else "failed")
                        self.status.set(f"Forward {state}: PF {self.forward_summary.profit_factor:.2f}, DD {self.forward_summary.drawdown_pct:.1f}%")
                    elif self.run_stage == "stability":
                        summary = parse_backtest_report(self.report_path)
                        label = getattr(self, "current_stability_label", "variant")
                        self.stability_results.append((label, summary))
                        self.mt4_process = None
                        self._launch_stability_next()
                        return
                    else:
                        self._load_results(self.report_path)
                except Exception as exc:
                    self.status.set(f"MT4 завершён, отчёт не разобран: {exc}")
            else:
                self.status.set(f"MT4 завершён без отчёта; код {self.mt4_process.returncode}")
            self.mt4_process = None

    def start_stability(self) -> None:
        try:
            if not self.results or not self.results[0].inputs:
                raise ValueError("Сначала выполните Train-оптимизацию")
            variants = stability_neighbours(self.parameters, self.results[0].inputs)
            if not variants:
                raise ValueError("Нет параметров с включённой оптимизацией и ненулевым шагом")
            terminal, expert, _ = self._validate()
            started, finished = parse_user_date(self.date_from.get()), parse_user_date(self.date_to.get())
            split = started + (finished - started) * 7 // 10
            isolated = (terminal.parent / "EA_OPTIMIZER_TEST_TERMINAL.txt").exists()
            data_dir = terminal.parent if isolated else DEFAULT_DATA
            run_dir = Path(__file__).parents[1] / "runs" / "stability"
            run_dir.mkdir(parents=True, exist_ok=True)
            model = {"Every tick": 0, "Control points": 1, "Open prices": 2}[self.model.get()]
            self.stability_jobs, self.stability_results = [], []
            for index, (label, params) in enumerate(variants, 1):
                preset = data_dir / "tester" / f"EA_Stability_{index}.set"
                report, config = terminal.parent / f"stability-report-{index}.htm", run_dir / f"test-{index}.ini"
                safe_export(self.source_set, preset, self.comments, params)
                build_mt4_config(config, expert_name=expert.stem, preset_name=preset.name,
                                 symbol=self.symbol.get().strip(), timeframe=self.timeframe.get(), model=model,
                                 spread=int(self.spread.get()), deposit=int(self.deposit.get()),
                                 date_from=split + timedelta(days=1), date_to=finished, optimize=False, report=report)
                self.stability_jobs.append((label, config, report))
            self.stability_total = len(self.stability_jobs)
            self.run_stage = "stability"
            self.cycle_state["Stability"]="выполняется"
            self._launch_stability_next()
        except Exception as exc:
            messagebox.showerror("Stability не запущен", str(exc))

    def _launch_stability_next(self) -> None:
        if not self.stability_jobs:
            passed = sum(summary.passed for _, summary in self.stability_results)
            total = len(self.stability_results)
            ratio = passed / total if total else 0
            self.stability_passed = ratio >= .7
            self.cycle_state["Stability"]="пройден" if self.stability_passed else "не пройден"
            self.progress.stop()
            self.run_stage = "idle"
            self.status.set(f"Stability: {passed}/{total} соседей, {'ПРОЙДЕН' if ratio >= .7 else 'НЕ ПРОЙДЕН'}")
            self.store.add_validation(self.symbol.get(), self.timeframe.get(), Path(self.expert.get()).name,
                                      "stability", None, "passed" if ratio >= .7 else "failed",
                                      {"passed": passed, "total": total, "ratio": ratio})
            messagebox.showinfo("Stability завершён", f"Успешных соседей: {passed} из {total}\nТребование: не менее 70%")
            return
        terminal = Path(self.terminal.get())
        label, config, report = self.stability_jobs.pop(0)
        args = [str(terminal)]
        if (terminal.parent / "EA_OPTIMIZER_TEST_TERMINAL.txt").exists(): args.append("/portable")
        args.append(str(config.resolve()))
        self.current_stability_label, self.report_path = label, report
        self.mt4_process = subprocess.Popen(args, cwd=str(terminal.parent))
        self.started_at = time.monotonic(); self.progress.start(12); self.after(1000, self._poll_process)
        done = self.stability_total - len(self.stability_jobs)
        self.status.set(f"Stability {done}/{self.stability_total}: {label}")

    def start_forward(self) -> None:
        try:
            if not self.results or not self.results[0].inputs:
                raise ValueError("Сначала завершите Train-оптимизацию и загрузите её отчёт")
            terminal, expert, source = self._validate()
            started, finished = parse_user_date(self.date_from.get()), parse_user_date(self.date_to.get())
            split = started + (finished - started) * 7 // 10
            data_dir = terminal.parent if (terminal.parent / "EA_OPTIMIZER_TEST_TERMINAL.txt").exists() else DEFAULT_DATA
            preset = data_dir / "tester" / "EA_Optimizer_Forward.set"
            best = self.results[0]
            params = [SetParameter(item.name, best.inputs.get(item.name, item.value)) for item in self.parameters]
            safe_export(source, preset, self.comments, params)
            run_dir = Path(__file__).parents[1] / "runs"
            report, config = terminal.parent / "forward-report.htm", run_dir / "forward-test.ini"
            model = {"Every tick": 0, "Control points": 1, "Open prices": 2}[self.model.get()]
            build_mt4_config(config, expert_name=expert.stem, preset_name=preset.name,
                             symbol=self.symbol.get().strip(), timeframe=self.timeframe.get(), model=model,
                             spread=int(self.spread.get()), deposit=int(self.deposit.get()),
                             date_from=split + timedelta(days=1), date_to=finished, optimize=False, report=report)
            args = [str(terminal)]
            if data_dir == terminal.parent: args.append("/portable")
            args.append(str(config.resolve()))
            self.report_path, self.run_stage = report, "forward"
            self.mt4_process = subprocess.Popen(args, cwd=str(terminal.parent))
            self.started_at = time.monotonic(); self.progress.start(12); self.after(1000, self._poll_process)
            self.status.set(f"Forward запущен: {split + timedelta(days=1)} — {finished}")
        except Exception as exc:
            messagebox.showerror("Forward не запущен", str(exc))

    def open_report(self) -> None:
        terminal=Path(self.terminal.get())
        expected=terminal.parent/"latest-report.htm"
        if expected.exists():
            try:
                self._load_results(expected); return
            except Exception as exc:
                messagebox.showerror("Отчёт не прочитан", str(exc)); return
        value = filedialog.askopenfilename(initialdir=terminal.parent if terminal.parent.exists() else Path(__file__).parents[1] / "runs",
                                           filetypes=[("MT4 report", "*.htm *.html")])
        if value:
            try:
                self._load_results(Path(value))
            except Exception as exc:
                messagebox.showerror("Отчёт не прочитан", str(exc))

    def _load_results(self, path: Path) -> None:
        self.results = parse_optimization_report(path)
        self.cycle_state["Train"]="завершён"
        self.store.add_optimization(self.symbol.get(), self.timeframe.get(), Path(self.expert.get()).name, self.results)
        best = self.results[0]
        self.status.set(f"Проходов: {len(self.results)}; лучший #{best.pass_no}, Score {best.score:.2f}")
        messagebox.showinfo("Оптимизация завершена",
                            f"Проходов: {len(self.results)}\nЛучший: #{best.pass_no}\nПрибыль: {best.profit:.2f}\nPF: {best.profit_factor:.2f}\nDD: {best.drawdown_pct:.2f}%")

    def export_best(self) -> None:
        if not self.results:
            messagebox.showwarning("Нет результатов", "Сначала завершите оптимизацию или откройте её отчёт")
            return
        if self.forward_summary is None or not self.forward_summary.passed:
            if not messagebox.askyesno("Forward не пройден", "Лучший набор не прошёл Forward-проверку. Всё равно экспортировать?"):
                return
        best = self.results[0]
        if not best.inputs:
            messagebox.showerror("Нет параметров", "MT4 не включил параметры прохода в HTML-отчёт")
            return
        updated = [SetParameter(item.name, best.inputs.get(item.name, item.value), item.start, item.step, item.stop, False)
                   for item in self.parameters]
        target = filedialog.asksaveasfilename(defaultextension=".set", initialfile="BEST.set",
                                               filetypes=[("MT4 preset", "*.set")])
        if target:
            backup = safe_export(self.source_set, Path(target), self.comments, updated)
            self.cycle_state["Лучший .set"]="создан"
            self.status.set(f"Лучший .set сохранён: {target}" + (f"; backup {backup.name}" if backup else ""))

    def show_top(self) -> None:
        try: count=parse_top_n(self.top_n.get())
        except ValueError as exc: messagebox.showerror("Неверный TOP", str(exc)); return
        if not self.results:
            messagebox.showwarning(f"TOP-{count}", "Сначала загрузите отчёт оптимизации"); return
        window=tk.Toplevel(self); window.title(f"TOP-{count} параметров"); window.geometry("900x500")
        cols=("pass","score","profit","trades","pf","dd","inputs"); table=ttk.Treeview(window,columns=cols,show="headings")
        for col,title,width in zip(cols,("Pass","Score","Profit","Trades","PF","DD %","Inputs"),(60,90,90,70,70,70,420)):
            table.heading(col,text=title); table.column(col,width=width)
        for result in self.results[:count]:
            inputs="; ".join(f"{k}={v}" for k,v in result.inputs.items())
            table.insert("","end",values=(result.pass_no,f"{result.score:.2f}",f"{result.profit:.2f}",result.trades,f"{result.profit_factor:.2f}",f"{result.drawdown_pct:.2f}",inputs))
        table.pack(fill="both",expand=True,padx=8,pady=8)

    def show_history(self) -> None:
        window=tk.Toplevel(self); window.title("История запусков"); window.geometry("1000x450")
        cols=("date","stage","status","symbol","tf","expert","details"); table=ttk.Treeview(window,columns=cols,show="headings")
        for col,title,width in zip(cols,("Дата UTC","Этап","Статус","Символ","TF","Советник","Детали"),(180,90,90,90,55,180,300)):
            table.heading(col,text=title); table.column(col,width=width)
        for row in self.store.recent_runs(): table.insert("","end",values=row)
        table.pack(fill="both",expand=True,padx=8,pady=8)

    def show_charts(self) -> None:
        if not self.results:
            messagebox.showwarning("Графики", "Сначала загрузите отчёт оптимизации"); return
        try: count=parse_top_n(self.top_n.get())
        except ValueError as exc: messagebox.showerror("Неверный TOP", str(exc)); return
        window=tk.Toplevel(self); window.title("Отчёт оптимизации"); window.geometry("1000x650")
        canvas=tk.Canvas(window,bg="white"); canvas.pack(fill="both",expand=True)
        top=self.results[:count]; width=920; left=60; chart_top=70; chart_height=360
        finite=[r.score for r in top if r.score != float("-inf")]
        max_score=max(finite,default=1); max_profit=max((abs(r.profit) for r in top),default=1)
        canvas.create_text(500,25,text=f"TOP-{count}: Score и прибыль",font=("Segoe UI",16,"bold"))
        bar=max(12,int(width/max(len(top),1))-8)
        for index,result in enumerate(top):
            x=left+index*(width/max(len(top),1))
            score=0 if result.score==float("-inf") else max(result.score,0)
            score_h=chart_height*score/max_score if max_score else 0
            profit_h=chart_height*max(result.profit,0)/max_profit if max_profit else 0
            canvas.create_rectangle(x,chart_top+chart_height-score_h,x+bar/2,chart_top+chart_height,fill="#2563eb",outline="")
            canvas.create_rectangle(x+bar/2,chart_top+chart_height-profit_h,x+bar,chart_top+chart_height,fill="#16a34a",outline="")
            canvas.create_text(x+bar/2,chart_top+chart_height+18,text=str(result.pass_no),angle=45,anchor="nw",font=("Segoe UI",8))
        canvas.create_line(left,chart_top+chart_height,left+width,chart_top+chart_height,fill="#555")
        canvas.create_rectangle(60,500,75,515,fill="#2563eb",outline=""); canvas.create_text(85,507,text="Score",anchor="w")
        canvas.create_rectangle(150,500,165,515,fill="#16a34a",outline=""); canvas.create_text(175,507,text="Прибыль",anchor="w")
        best=top[0]; summary=f"Лучший проход #{best.pass_no}   Profit {best.profit:.2f}   PF {best.profit_factor:.2f}   DD {best.drawdown_pct:.2f}%   Trades {best.trades}"
        canvas.create_text(60,550,text=summary,anchor="w",font=("Segoe UI",11,"bold"))
        if self.forward_summary:
            forward=self.forward_summary; state="ПРОЙДЕН" if forward.passed else "НЕ ПРОЙДЕН"
            canvas.create_text(60,585,text=f"Forward {state}: Profit {forward.profit:.2f}, PF {forward.profit_factor:.2f}, DD {forward.drawdown_pct:.2f}%, Trades {forward.trades}",anchor="w",fill="#166534" if forward.passed else "#b91c1c",font=("Segoe UI",11))

    def show_cycle_status(self) -> None:
        window=tk.Toplevel(self); window.title("Состояние полного цикла"); window.geometry("620x430")
        ttk.Label(window,text="MT4 Strategy Optimizer",font=("Segoe UI",16,"bold")).pack(anchor="w",padx=20,pady=(18,10))
        frame=ttk.Frame(window,padding=12); frame.pack(fill="both",expand=True)
        green=("готов","завершён","пройден","выполнена","создан")
        for row,(stage,state) in enumerate(self.cycle_state.items()):
            ttk.Label(frame,text=stage,width=18,font=("Segoe UI",11,"bold")).grid(row=row,column=0,sticky="w",pady=7)
            color="#b91c1c" if "не пройден" in state else "#15803d" if any(word in state for word in green) else "#1d4ed8" if "выполняется" in state else "#555"
            tk.Label(frame,text=state,fg=color,font=("Segoe UI",11)).grid(row=row,column=1,sticky="w",pady=7)
        ttk.Label(window,text="Порядок: Train → Forward → Stability → экспорт → установка",foreground="#555").pack(anchor="w",padx=20,pady=12)

    def apply_best(self) -> None:
        try:
            if not self.results or not self.results[0].inputs:
                raise ValueError("Нет лучшего набора параметров")
            if self.forward_summary is None or not self.forward_summary.passed:
                raise ValueError("Лучший набор не прошёл Forward")
            if not self.stability_passed:
                raise ValueError("Лучший набор не прошёл Stability")
            expert = Path(self.expert.get()).stem
            target = DEFAULT_DATA / "MQL4" / "Presets" / f"{expert}_BEST.set"
            best = self.results[0]
            params = [SetParameter(item.name, best.inputs.get(item.name, item.value)) for item in self.parameters]
            if not messagebox.askyesno("Установить лучший .set",
                                       f"Установить подтверждённые параметры для {expert}?\n\n{target}\n\nСуществующий файл будет сохранён в backup."):
                return
            audit = Path(__file__).parents[1] / "data" / "install-audit.jsonl"
            backup = install_best_set(target, self.comments, params, audit, expert, f"pass-{best.pass_no}")
            self.cycle_state["Установка"]="выполнена"
            self.status.set(f"Лучший .set установлен: {target.name}")
            messagebox.showinfo("Установлено",
                                f"Файл установлен:\n{target}\n\nВ MT4 откройте свойства советника (F7) → Загрузить → {target.name}"
                                + (f"\n\nBackup: {backup.name}" if backup else ""))
        except Exception as exc:
            messagebox.showerror("Установка запрещена", str(exc))

    def save_schedule(self) -> None:
        try:
            terminal, config, _, _ = self._prepare_run()
            hour, minute = map(int, self.schedule_time.get().split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError
            mode = self.schedule_mode.get()
            runner = Path(__file__).parents[1] / "run_scheduled.pyw"
            if not (terminal.parent / "EA_OPTIMIZER_TEST_TERMINAL.txt").exists():
                raise RuntimeError("Для автозапуска сначала подготовьте тестовый MT4")
            run_dir=Path(__file__).parents[1]/"runs"; job_path=run_dir/"auto-job.json"
            expert=Path(self.expert.get()); started=parse_user_date(self.date_from.get()); finished=parse_user_date(self.date_to.get())
            job={"terminal":str(terminal),"train_config":str(config),"train_report":str(terminal.parent/"latest-report.htm"),"status":str(run_dir/"auto-status.json"),
                 "source_set":str(self.source_set),"expert_name":expert.stem,"symbol":self.symbol.get().strip(),"timeframe":self.timeframe.get(),
                 "model":{"Every tick":0,"Control points":1,"Open prices":2}[self.model.get()],"spread":int(self.spread.get()),"deposit":int(self.deposit.get()),
                 "date_from":started.isoformat(),"date_to":finished.isoformat(),"comments":self.comments,"parameters":[asdict(p) for p in self.parameters]}
            job_path.write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding="utf-8")
            command = f'"{sys.executable.replace("python.exe", "pythonw.exe")}" "{runner}" "{job_path}"'
            self._delete_tasks()
            specs = []
            if mode == "1 раз в сутки": specs = [("DAILY", "", hour, minute)]
            elif mode == "2 раза в сутки": specs = [("DAILY", "", hour, minute), ("DAILY", "", (hour + 12) % 24, minute)]
            elif mode == "1 раз в неделю": specs = [("WEEKLY", "MON", hour, minute)]
            elif mode == "3 раза в неделю": specs = [("WEEKLY", "MON,WED,FRI", hour, minute)]
            elif mode == "4 раза в неделю": specs = [("WEEKLY", "MON,TUE,THU,SAT", hour, minute)]
            elif mode == "Выключен":
                self.status.set("Автозапуск выключен")
                return
            for index, (frequency, days, h, m) in enumerate(specs, 1):
                args = ["schtasks", "/Create", "/F", "/TN", f"EA Optimizer Lab {index}", "/TR", command,
                        "/SC", frequency, "/ST", f"{h:02d}:{m:02d}"]
                if days:
                    args.extend(["/D", days])
                result = subprocess.run(args, capture_output=True, text=True)
                if result.returncode:
                    details = (result.stderr or "").strip() or (result.stdout or "").strip()
                    raise RuntimeError(details or f"Планировщик Windows вернул код {result.returncode}")
            self.status.set(f"Расписание сохранено: {mode}")
            self.cycle_state["Автоцикл"]=f"расписание: {mode}"
        except ValueError:
            messagebox.showerror("Расписание", "Время укажите как ЧЧ:ММ")
        except Exception as exc:
            messagebox.showerror("Расписание не сохранено", str(exc))

    def show_auto_status(self) -> None:
        path=Path(__file__).parents[1]/"runs"/"auto-status.json"
        if not path.exists():
            messagebox.showinfo("Автоцикл", "Автоматических запусков ещё не было"); return
        try:
            data=json.loads(path.read_text(encoding="utf-8"))
            self.cycle_state["Автоцикл"]=f"{data.get('stage','?')}: {data.get('state','?')}"
            messagebox.showinfo("Автоцикл", "\n".join(f"{key}: {value}" for key,value in data.items()))
        except Exception as exc:
            messagebox.showerror("Статус не прочитан", str(exc))

    @staticmethod
    def _delete_tasks() -> None:
        for index in (1, 2):
            subprocess.run(["schtasks", "/Delete", "/F", "/TN", f"EA Optimizer Lab {index}"], capture_output=True)

    def _settings_path(self) -> Path:
        return Path(__file__).parents[1]/"data"/"settings.json"

    def _save_settings(self) -> None:
        data={"terminal":self.terminal.get(),"expert":self.expert.get(),"source_set":str(self.source_set or ""),
              "symbol":self.symbol.get(),"timeframe":self.timeframe.get(),"date_from":self.date_from.get(),"date_to":self.date_to.get(),
              "deposit":self.deposit.get(),"spread":self.spread.get(),"model":self.model.get(),"optimize":self.optimize.get(),
              "schedule_mode":self.schedule_mode.get(),"schedule_time":self.schedule_time.get(),"top_n":self.top_n.get(),
              "comments":self.comments,"parameters":[asdict(item) for item in self.parameters]}
        path=self._settings_path(); path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")

    def _load_settings(self) -> None:
        path=self._settings_path()
        if not path.exists(): return
        try:
            data=json.loads(path.read_text(encoding="utf-8"))
            for variable,key in ((self.terminal,"terminal"),(self.expert,"expert"),(self.symbol,"symbol"),(self.timeframe,"timeframe"),
                                 (self.date_from,"date_from"),(self.date_to,"date_to"),(self.deposit,"deposit"),(self.spread,"spread"),
                                 (self.model,"model"),(self.schedule_mode,"schedule_mode"),(self.schedule_time,"schedule_time"),(self.top_n,"top_n")):
                if key in data: variable.set(data[key])
            self.optimize.set(bool(data.get("optimize",True)))
            self.source_set=Path(data["source_set"]) if data.get("source_set") else None
            self.comments=list(data.get("comments",[])); self.parameters=[SetParameter(**item) for item in data.get("parameters",[])]
            if self.parameters: self._refresh(); self.status.set(f"Настройки восстановлены; параметров: {len(self.parameters)}")
        except Exception as exc:
            self.status.set(f"Настройки не восстановлены: {exc}")

    def _close_app(self) -> None:
        try: self._save_settings()
        finally: self.destroy()


def main() -> None:
    OptimizerApp().mainloop()


if __name__ == "__main__":
    main()
