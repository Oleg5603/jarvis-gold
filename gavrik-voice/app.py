"""Гаврик Голос — безопасный локальный голосовой помощник для Windows."""
from __future__ import annotations

import os
import re
import subprocess
import threading
import urllib.parse
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, X, Button, Entry, Frame, Label, Listbox, StringVar, Tk, messagebox

ROOT = Path(__file__).resolve().parent
VOICE_SCRIPT = ROOT / "voice_recognizer.ps1"
INK, PAPER, SAFE, CAUTION, DANGER = "#17212B", "#F5F7F8", "#1E9E78", "#D28B28", "#C84E54"


@dataclass
class Action:
    title: str
    detail: str
    kind: str
    value: str = ""
    color: str = SAFE


def normalise(text: str) -> str:
    return " ".join(text.lower().replace("ё", "е").strip().split())


def parse_command(text: str) -> Action:
    raw, command = text.strip(), normalise(text)
    if not command:
        return Action("Команда не распознана", "Скажите: «Открой браузер».", "none")
    if command.startswith(("найди файл ", "поиск файла ")):
        name = re.sub(r"^(найди файл|поиск файла)\s+", "", raw, flags=re.I).strip()
        return Action("Найти файл", f"Поищу «{name}» в Документах, Загрузках и на Рабочем столе.", "find_file", name)
    if command.startswith("открой файл "):
        return Action("Найти файл", "Покажу найденные совпадения. Файл открывается только по вашему выбору.", "find_file", raw[12:].strip())
    if command.startswith(("найди ", "поищи ")):
        query = re.sub(r"^(найди|поищи)\s+", "", raw, flags=re.I).strip()
        return Action("Найти в интернете", f"Открою поиск: {query}", "search", query)
    if command in {"покажи рабочий стол", "рабочий стол"}:
        return Action("Показать рабочий стол", "Сверну окна. Ничего не будет закрыто.", "desktop")
    if command in {"закрой окно", "закрыть окно"}:
        return Action("Закрыть активное окно", "Несохранённые изменения могут быть потеряны.", "close", color=DANGER)
    if command.startswith(("напиши ", "сообщение ", "отправь ")):
        msg = re.sub(r"^(напиши|сообщение|отправь)\s+", "", raw, flags=re.I).strip()
        return Action("Подготовить сообщение", f"Скопирую текст в буфер: «{msg}». Отправлять его будет человек.", "compose", msg, CAUTION)
    if command.startswith(("открой ", "запусти ")):
        target = re.sub(r"^(открой|запусти)\s+", "", command).strip()
        if target in {"браузер", "интернет"}:
            return Action("Открыть браузер", "Открою страницу поиска.", "url", "https://www.google.com")
        if target in {"ютуб", "youtube"}:
            return Action("Открыть YouTube", "Открою YouTube.", "url", "https://www.youtube.com")
        if target in {"телеграм", "telegram"}:
            return Action("Открыть Telegram", "Открою Telegram или его веб-версию.", "telegram")
        if target in {"ватсап", "whatsapp"}:
            return Action("Открыть WhatsApp", "Открою WhatsApp Web.", "url", "https://web.whatsapp.com")
        if "." in target and " " not in target:
            return Action("Открыть сайт", f"Открою {target}.", "url", "https://" + target)
    return Action("Не понял команду", "Примеры: «Найди файл договор», «Открой Телеграм», «Покажи рабочий стол».", "none")


def search_files(query: str) -> list[Path]:
    roots = [Path.home() / "Desktop", Path.home() / "Documents", Path.home() / "Downloads"]
    needle, result = normalise(query), []
    for root in roots:
        if not root.exists():
            continue
        for folder, _, files in os.walk(root):
            for filename in files:
                if needle in normalise(filename):
                    result.append(Path(folder) / filename)
                    if len(result) == 20:
                        return result
    return result


class GavrikVoice:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title("Гаврик Голос")
        self.root.geometry("760x620")
        self.root.minsize(650, 520)
        self.root.configure(bg=PAPER)
        self.command, self.status = StringVar(), StringVar(value="Скажите или напишите команду")
        self.action: Action | None = None
        self.results: list[Path] = []
        self.build()

    def build(self) -> None:
        header = Frame(self.root, bg=INK, padx=28, pady=20)
        header.pack(fill=X)
        Label(header, text="Гаврик Голос", font=("Segoe UI", 26, "bold"), fg="white", bg=INK).pack(anchor="w")
        Label(header, text="Простое управление компьютером голосом", font=("Segoe UI", 12), fg="#C8D6DF", bg=INK).pack(anchor="w")
        main = Frame(self.root, bg=PAPER, padx=30, pady=22)
        main.pack(fill=BOTH, expand=True)
        Label(main, textvariable=self.status, font=("Segoe UI", 16, "bold"), fg=INK, bg=PAPER, wraplength=650, justify="left").pack(fill=X, pady=(0, 14))
        self.mic = Button(main, text="🎙  Сказать команду", command=self.listen, font=("Segoe UI", 20, "bold"), bg=SAFE, fg="white", relief="flat", pady=16)
        self.mic.pack(fill=X, pady=(0, 14))
        row = Frame(main, bg=PAPER); row.pack(fill=X, pady=(0, 15))
        Entry(row, textvariable=self.command, font=("Segoe UI", 15), relief="solid", bd=1).pack(side=LEFT, fill=X, expand=True, ipady=9)
        Button(row, text="Понять", command=self.interpret, font=("Segoe UI", 13, "bold"), bg=INK, fg="white", relief="flat", padx=18, pady=9).pack(side=RIGHT, padx=(10, 0))
        self.card = Frame(main, bg="#E3EAED", padx=20, pady=16); self.card.pack(fill=X)
        self.title = Label(self.card, text="Действие появится здесь", font=("Segoe UI", 18, "bold"), fg=INK, bg="#E3EAED", anchor="w"); self.title.pack(fill=X)
        self.detail = Label(self.card, text="", font=("Segoe UI", 12), fg="#40515D", bg="#E3EAED", anchor="w", justify="left", wraplength=650); self.detail.pack(fill=X, pady=(5, 12))
        buttons = Frame(self.card, bg="#E3EAED"); buttons.pack(fill=X)
        self.go = Button(buttons, text="Выполнить", command=self.execute, font=("Segoe UI", 14, "bold"), bg=SAFE, fg="white", relief="flat", padx=24, pady=9, state="disabled"); self.go.pack(side=LEFT)
        Button(buttons, text="Отмена", command=self.clear, font=("Segoe UI", 14), bg="white", fg=INK, relief="flat", padx=24, pady=9).pack(side=LEFT, padx=10)
        Label(main, text="Найденные файлы", font=("Segoe UI", 12, "bold"), fg=INK, bg=PAPER).pack(anchor="w", pady=(16, 5))
        self.files = Listbox(main, font=("Segoe UI", 11), height=5); self.files.pack(fill=BOTH, expand=True); self.files.bind("<Double-Button-1>", self.open_selected)
        Label(main, text="Отправка сообщений, удаление и закрытие окон — только после подтверждения.", font=("Segoe UI", 10), fg="#60717C", bg=PAPER).pack(anchor="w", pady=(7, 0))

    def listen(self) -> None:
        self.mic.configure(state="disabled", text="🎙  Слушаю до 12 секунд…")
        self.status.set("Говорите обычной фразой.")
        threading.Thread(target=self.listen_worker, daemon=True).start()

    def listen_worker(self) -> None:
        try:
            run = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(VOICE_SCRIPT)], capture_output=True, text=True, timeout=18, encoding="utf-8")
            phrase = run.stdout.strip()
            if not phrase:
                raise RuntimeError("Речь не распознана. Проверьте микрофон или напишите команду.")
            self.root.after(0, lambda: self.heard(phrase))
        except Exception as exc:
            self.root.after(0, lambda: self.voice_error(str(exc)))

    def heard(self, phrase: str) -> None:
        self.command.set(phrase); self.mic.configure(state="normal", text="🎙  Сказать команду"); self.status.set(f"Я услышал: «{phrase}»"); self.interpret()

    def voice_error(self, text: str) -> None:
        self.mic.configure(state="normal", text="🎙  Сказать команду"); self.status.set(text)

    def interpret(self) -> None:
        self.action = parse_command(self.command.get())
        self.title.configure(text=self.action.title); self.detail.configure(text=self.action.detail)
        self.go.configure(state="normal" if self.action.kind != "none" else "disabled", bg=self.action.color)

    def clear(self) -> None:
        self.action = None; self.command.set(""); self.status.set("Скажите или напишите команду"); self.title.configure(text="Действие отменено"); self.detail.configure(text="Ничего не выполнено."); self.go.configure(state="disabled")

    def execute(self) -> None:
        if not self.action: return
        a = self.action
        if a.kind == "close" and not messagebox.askyesno("Подтверждение", "Закрыть активное окно? Несохранённые изменения могут быть потеряны."): return
        if a.kind == "search": webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote_plus(a.value))
        elif a.kind == "url": webbrowser.open(a.value)
        elif a.kind == "telegram": self.open_telegram()
        elif a.kind == "desktop": subprocess.run(["powershell", "-NoProfile", "-Command", "(New-Object -ComObject Shell.Application).MinimizeAll()"], check=False)
        elif a.kind == "close": subprocess.run(["powershell", "-NoProfile", "-Command", "$w=New-Object -ComObject WScript.Shell; $w.SendKeys('%{F4}')"], check=False)
        elif a.kind == "compose": self.root.clipboard_clear(); self.root.clipboard_append(a.value); self.root.update(); self.status.set("Текст скопирован. Вставьте его в мессенджер; отправка остаётся за вами."); return
        elif a.kind == "find_file": self.show_files(a.value); return
        self.status.set("Готово: " + a.title)

    def open_telegram(self) -> None:
        paths = [Path(os.getenv("APPDATA", "")) / "Telegram Desktop" / "Telegram.exe", Path(os.getenv("LOCALAPPDATA", "")) / "Telegram Desktop" / "Telegram.exe"]
        app = next((p for p in paths if p.is_file()), None)
        os.startfile(str(app)) if app else webbrowser.open("https://web.telegram.org")

    def show_files(self, query: str) -> None:
        self.status.set("Ищу файлы…"); self.root.update(); self.results = search_files(query); self.files.delete(0, END)
        for path in self.results: self.files.insert(END, str(path))
        self.status.set(f"Найдено: {len(self.results)}. Дважды щёлкните нужный файл." if self.results else "Файлы не найдены. Уточните название.")

    def open_selected(self, _event=None) -> None:
        selected = self.files.curselection()
        if selected: os.startfile(str(self.results[selected[0]]))

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    GavrikVoice().run()
