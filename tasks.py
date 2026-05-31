import json
from pathlib import Path
from datetime import datetime, timezone

TASKS_FILE = Path("/root/telegram-bot/tasks_data.json")

PRIORITY_LABELS = {
    "high":   "🔴 Высокий",
    "medium": "🟡 Средний",
    "low":    "🟢 Низкий",
}
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}

PRIORITY_MAP = {
    "1": "high",    "высокий": "high",    "высок": "high",   "high": "high",
    "2": "medium",  "средний": "medium",  "средн": "medium", "medium": "medium",
    "3": "low",     "низкий": "low",      "низк": "low",     "low": "low",
}

DATE_FORMATS = [
    "%d.%m.%Y %H:%M",
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
]


def load_tasks() -> dict:
    if TASKS_FILE.exists():
        try:
            return json.loads(TASKS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"tasks": [], "next_id": 1}


def save_tasks(data: dict) -> None:
    TASKS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_deadline(text: str) -> datetime | None:
    text = text.strip()
    if text.lower() in ("нет", "no", "-", ""):
        return None
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def add_task(data: dict, text: str, priority: str = "medium", deadline: datetime | None = None) -> dict:
    task = {
        "id": data["next_id"],
        "text": text,
        "priority": priority,
        "deadline": deadline.isoformat() if deadline else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "done": False,
    }
    data["tasks"].append(task)
    data["next_id"] += 1
    return task


def get_active_tasks(data: dict) -> list:
    tasks = [t for t in data["tasks"] if not t["done"]]

    def sort_key(t):
        prio = PRIORITY_ORDER.get(t["priority"], 1)
        if t["deadline"]:
            dl = datetime.fromisoformat(t["deadline"])
            if dl.tzinfo is None:
                dl = dl.replace(tzinfo=timezone.utc)
            ts = dl.timestamp()
        else:
            ts = float("inf")
        return (prio, ts)

    return sorted(tasks, key=sort_key)


def mark_done(data: dict, task_id: int) -> dict | None:
    for t in data["tasks"]:
        if t["id"] == task_id and not t["done"]:
            t["done"] = True
            return t
    return None


def delete_task(data: dict, task_id: int) -> bool:
    before = len(data["tasks"])
    data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
    return len(data["tasks"]) < before


def _deadline_str(t: dict) -> str:
    if not t["deadline"]:
        return ""
    dl = datetime.fromisoformat(t["deadline"])
    if dl.tzinfo is None:
        dl = dl.replace(tzinfo=timezone.utc)
    base = f"\n   📅 {dl.strftime('%d.%m.%Y %H:%M')}"
    diff = (dl - datetime.now(timezone.utc)).total_seconds()
    if diff < 0:
        base += " ⚠️ просрочено"
    elif diff < 3600:
        base += f" (через {int(diff/60)} мин)"
    elif diff < 86400:
        base += f" (через {int(diff/3600)} ч)"
    return base


def format_task(t: dict, num: int | None = None) -> str:
    prio = PRIORITY_LABELS.get(t["priority"], "🟡 Средний")
    prefix = f"{num}. " if num is not None else ""
    return f"{prefix}*#{t['id']}* {prio}\n   {t['text']}{_deadline_str(t)}"


def format_task_list(data: dict) -> str:
    tasks = get_active_tasks(data)
    if not tasks:
        return "📋 Нет активных задач.\nДобавь: `/zadacha Текст задачи`"
    lines = ["📋 *Список задач:*\n"]
    for i, t in enumerate(tasks, 1):
        lines.append(format_task(t, i))
    return "\n\n".join(lines)


def format_reminder(data: dict) -> str | None:
    tasks = get_active_tasks(data)
    if not tasks:
        return None
    now = datetime.now(timezone.utc)
    high = [t for t in tasks if t["priority"] == "high"]
    overdue = []
    for t in tasks:
        if t["deadline"]:
            dl = datetime.fromisoformat(t["deadline"])
            if dl.tzinfo is None:
                dl = dl.replace(tzinfo=timezone.utc)
            if dl < now:
                overdue.append(t)

    lines = ["⏰ *Напоминание о задачах*\n"]
    lines.append(f"Активных задач: *{len(tasks)}*")
    if high:
        lines.append(f"🔴 Высокий приоритет: *{len(high)}*")
    if overdue:
        lines.append(f"⚠️ Просрочено: *{len(overdue)}*")
    lines.append("\n*Ближайшие задачи:*")
    for t in tasks[:5]:
        lines.append(format_task(t))
    if len(tasks) > 5:
        lines.append(f"_...ещё {len(tasks) - 5}_ → /zadachi")
    else:
        lines.append("\nПолный список → /zadachi")
    return "\n".join(lines)
