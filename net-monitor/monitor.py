"""
monitor.py — окно мониторинга цепочки интернет-сигнала.
Периодически прогоняет chain_checks.run_chain(), показывает статус каждого шага
и ведёт журнал разрывов (время + причина + этап) в таблице и в файле log.

Запуск: python monitor.py
"""
import msvcrt
import os
import queue
import sys
import threading
import time
from datetime import datetime
import tkinter as tk
from tkinter import ttk

from chain_checks import CHAIN, run_chain, find_break_point

LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".monitor.lock")


def _acquire_single_instance_lock():
    """Не даёт запустить второй экземпляр монитора — старый зависший процесс
    иначе остаётся невидимым и создаёт впечатление ложных 'падений'."""
    f = open(LOCK_FILE, "w")
    try:
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        print("Монитор уже запущен — выхожу.")
        sys.exit(1)
    return f  # держим файл открытым на всё время работы процесса

POLL_INTERVAL_SEC = 5
LOG_FILE = "net_monitor_log.txt"
FAIL_CONFIRM_COUNT = 3  # сколько подряд неудачных опросов нужно, чтобы считать это реальным обрывом
# Для Claude API порог ниже: единичный TLS-таймаут к api.anthropic.com уже мог
# оборвать чат (подтверждено логом 2026-07-12 23:35-23:38 — три одиночных сбоя
# именно на этом этапе совпали с падением чата, хотя ни один не набрал 3 подряд).
FAIL_CONFIRM_COUNT_CLAUDE_API = 1
CLAUDE_API_STEP_NAME = "Claude API (api.anthropic.com)"

OK_COLOR = "#1e7e34"
FAIL_COLOR = "#c0392b"
SKIP_COLOR = "#888888"
BG = "#1e1e1e"
FG = "#e0e0e0"


class NetMonitorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Монитор обрыва связи")
        root.configure(bg=BG)
        root.geometry("820x560")

        self.q: queue.Queue = queue.Queue()
        self.step_labels: dict[str, tuple[tk.Label, tk.Label]] = {}
        self.consecutive_fail_at: str | None = None
        self.last_break_started: datetime | None = None
        self.pending_fail_count = 0
        self.pending_break_name: str | None = None
        self.first_fail_at_time: datetime | None = None

        self._build_status_panel()
        self._build_history_panel()
        self._build_controls()

        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        self.root.after(200, self._poll_queue)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI ──────────────────────────────────────────────────────────────
    def _build_status_panel(self):
        frame = tk.Frame(self.root, bg=BG, padx=12, pady=12)
        frame.pack(fill="x")
        tk.Label(frame, text="Цепочка прохождения сигнала", bg=BG, fg=FG,
                 font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        for i, fn in enumerate(CHAIN):
            name = fn.__name__.replace("check_", "").upper()
            row = i + 1
            step_no = tk.Label(frame, text=f"{i+1}.", bg=BG, fg=FG, font=("Segoe UI", 10))
            step_no.grid(row=row, column=0, sticky="w")
            dot = tk.Label(frame, text="●", bg=BG, fg=SKIP_COLOR, font=("Segoe UI", 14))
            dot.grid(row=row, column=1, sticky="w", padx=(4, 8))
            detail = tk.Label(frame, text="ожидание проверки…", bg=BG, fg=FG,
                               font=("Consolas", 10), anchor="w", justify="left")
            detail.grid(row=row, column=2, sticky="w")
            self.step_labels[fn.__name__] = (dot, detail)

        self.status_line = tk.Label(frame, text="", bg=BG, fg=FG, font=("Segoe UI", 11, "bold"))
        self.status_line.grid(row=len(CHAIN) + 2, column=0, columnspan=3, sticky="w", pady=(10, 0))

    def _build_history_panel(self):
        frame = tk.Frame(self.root, bg=BG, padx=12, pady=8)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="Журнал разрывов (время / этап / причина / длительность)",
                 bg=BG, fg=FG, font=("Segoe UI", 11, "bold")).pack(anchor="w")

        cols = ("time", "step", "reason", "duration")
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2a2a2a", fieldbackground="#2a2a2a", foreground=FG,
                         rowheight=24, font=("Consolas", 9))
        style.configure("Treeview.Heading", background="#333", foreground=FG, font=("Segoe UI", 9, "bold"))

        self.tree = ttk.Treeview(frame, columns=cols, show="headings", height=14)
        headings = {"time": "Время начала", "step": "Этап обрыва", "reason": "Причина", "duration": "Длительность"}
        widths = {"time": 150, "step": 180, "reason": 380, "duration": 100}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c])
        self.tree.pack(fill="both", expand=True, pady=(6, 0))

    def _build_controls(self):
        frame = tk.Frame(self.root, bg=BG, padx=12, pady=8)
        frame.pack(fill="x")
        self.interval_var = tk.StringVar(value=str(POLL_INTERVAL_SEC))
        tk.Label(frame, text="Интервал опроса, сек:", bg=BG, fg=FG).pack(side="left")
        tk.Entry(frame, textvariable=self.interval_var, width=5).pack(side="left", padx=(4, 12))
        tk.Label(frame, text=f"Лог-файл: {LOG_FILE}", bg=BG, fg="#999").pack(side="left")

    # ── Фоновая проверка ──────────────────────────────────────────────
    def _worker(self):
        while self.running:
            results = run_chain()
            self.q.put(results)
            try:
                interval = max(1, int(self.interval_var.get()))
            except Exception:
                interval = POLL_INTERVAL_SEC
            time.sleep(interval)

    def _poll_queue(self):
        try:
            while True:
                results = self.q.get_nowait()
                self._update_ui(results)
        except queue.Empty:
            pass
        if self.running:
            self.root.after(300, self._poll_queue)

    def _update_ui(self, results):
        done_names = {r.name for r in results}
        ordered_fns = list(CHAIN)
        result_by_fn = {}
        ri = 0
        for fn in ordered_fns:
            step_name = fn.__name__
            if ri < len(results):
                result_by_fn[step_name] = results[ri]
                ri += 1
            else:
                result_by_fn[step_name] = None  # шаг не выполнялся (обрыв раньше)

        for fn in ordered_fns:
            dot, detail = self.step_labels[fn.__name__]
            r = result_by_fn[fn.__name__]
            if r is None:
                dot.config(fg=SKIP_COLOR)
                detail.config(text="пропущено (обрыв раньше по цепочке)", fg=SKIP_COLOR)
            elif r.ok:
                dot.config(fg=OK_COLOR)
                detail.config(text=f"{r.name}: {r.detail}", fg=FG)
            else:
                dot.config(fg=FAIL_COLOR)
                detail.config(text=f"{r.name}: {r.detail}", fg=FAIL_COLOR)

        brk = find_break_point(results)
        now = datetime.now()
        if brk is not None:
            # считаем разрыв подтверждённым только после N подряд неудачных опросов —
            # разовый лаг (например, VPN на TLS-хендшейке) не должен попадать в журнал
            if self.pending_break_name == brk.name:
                self.pending_fail_count += 1
            else:
                self.pending_break_name = brk.name
                self.pending_fail_count = 1
                self.first_fail_at_time = now
                self._log_line(f"[{now:%Y-%m-%d %H:%M:%S}] сбой (1 опрос) — этап: {brk.name} — {brk.detail}")

            confirm_threshold = (FAIL_CONFIRM_COUNT_CLAUDE_API if brk.name == CLAUDE_API_STEP_NAME
                                  else FAIL_CONFIRM_COUNT)
            if self.pending_fail_count >= confirm_threshold:
                self.status_line.config(text=f"⛔ ОБРЫВ СВЯЗИ — этап: {brk.name} — {brk.detail}", fg=FAIL_COLOR)
                if self.consecutive_fail_at is None:
                    self.consecutive_fail_at = brk.name
                    self.last_break_started = self.first_fail_at_time
                    self._log_line(f"[{self.last_break_started:%Y-%m-%d %H:%M:%S}] НАЧАЛО ОБРЫВА — этап: {brk.name} — {brk.detail}")
                    self.tree.insert("", 0, values=(self.last_break_started.strftime("%Y-%m-%d %H:%M:%S"), brk.name, brk.detail, "…"))
            else:
                self.status_line.config(
                    text=f"⚠ временный сбой (этап: {brk.name}), проверяю ещё раз…", fg="#d4a017")
        else:
            self.pending_fail_count = 0
            self.pending_break_name = None
            self.status_line.config(text="✅ Связь в норме, вся цепочка пройдена", fg=OK_COLOR)
            if self.consecutive_fail_at is not None:
                dur = now - self.last_break_started
                self._log_line(f"[{now:%Y-%m-%d %H:%M:%S}] СВЯЗЬ ВОССТАНОВЛЕНА "
                                f"(этап был: {self.consecutive_fail_at}, длительность {dur})")
                # обновить длительность в первой строке журнала
                first = self.tree.get_children()
                if first:
                    vals = list(self.tree.item(first[0], "values"))
                    vals[3] = str(dur).split(".")[0]
                    self.tree.item(first[0], values=vals)
                self.consecutive_fail_at = None
                self.last_break_started = None

    def _log_line(self, text: str):
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except Exception:
            pass

    def _on_close(self):
        self.running = False
        self.root.destroy()


if __name__ == "__main__":
    _lock_handle = _acquire_single_instance_lock()
    root = tk.Tk()
    app = NetMonitorApp(root)
    root.mainloop()
