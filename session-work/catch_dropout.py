"""
catch_dropout.py — следит за net_monitor_log.txt, и как только видит новую
строку "НАЧАЛО ОБРЫВА" по этапу Claude API, немедленно снимает tracert к
api.anthropic.com (по IPv4, чтобы не упереться в отсутствие IPv6-маршрута)
и сохраняет результат с таймкодом рядом. Работает в фоне, не завершается сам.
"""
import subprocess
import time
import os
import datetime

LOG_FILE = r"C:\Users\HP\Documents\Project\net-monitor\net_monitor_log.txt"
OUT_DIR = r"C:\Users\HP\Documents\Project\session-work\dropout_traces"
TARGET = "api.anthropic.com"

os.makedirs(OUT_DIR, exist_ok=True)


def tail_new_lines(f, seen_size):
    f.seek(seen_size)
    lines = f.readlines()
    return lines, f.tell()


def run_capture(reason_line: str):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(OUT_DIR, f"trace_{ts}.txt")
    with open(out_path, "w", encoding="utf-8") as out:
        out.write(f"Триггер: {reason_line}\n")
        out.write(f"Время захвата: {datetime.datetime.now()}\n\n")
        out.write("=== tracert -4 api.anthropic.com ===\n")
        out.flush()
        try:
            tr = subprocess.run(
                ["tracert", "-4", "-w", "800", "-h", "20", TARGET],
                capture_output=True, text=True, timeout=40,
                encoding="cp866", errors="replace",
            )
            out.write(tr.stdout + tr.stderr)
        except Exception as e:
            out.write(f"tracert failed: {e}\n")
        out.write("\n=== curl -4 -v (timing) ===\n")
        out.flush()
        try:
            cu = subprocess.run(
                ["curl", "-4", "-v", "--max-time", "10",
                 "-w", "\\nconnect=%{time_connect} tls=%{time_appconnect} total=%{time_total}\\n",
                 f"https://{TARGET}/"],
                capture_output=True, text=True, timeout=15,
            )
            out.write(cu.stdout + cu.stderr)
        except Exception as e:
            out.write(f"curl failed: {e}\n")
    print(f"[{datetime.datetime.now()}] Захват сохранён: {out_path}")


def main():
    print("Слежу за", LOG_FILE, "— жду 'НАЧАЛО ОБРЫВА' по Claude API...")
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        f.seek(0, os.SEEK_END)
        pos = f.tell()
        while True:
            lines, pos = tail_new_lines(f, pos)
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if "НАЧАЛО ОБРЫВА" in line and "Claude API" in line:
                    print(f"[{datetime.datetime.now()}] Обнаружен обрыв, снимаю трассу...")
                    run_capture(line)
            time.sleep(2)


if __name__ == "__main__":
    main()
