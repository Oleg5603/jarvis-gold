import json
from datetime import datetime
from pathlib import Path

LEADS_FILE = Path("/root/telegram-bot/leads_data.json")

STATUS_LABELS = {
    "new":      "🆕 Новый",
    "work":     "🔄 В работе",
    "done":     "✅ Закрыт",
    "refuse":   "❌ Отказ",
}
STATUS_ALIASES = {
    "new": "new", "новый": "new", "1": "new",
    "work": "work", "работа": "work", "в работе": "work", "2": "work",
    "done": "done", "закрыт": "done", "готово": "done", "3": "done",
    "refuse": "refuse", "отказ": "refuse", "4": "refuse",
}


def load_leads() -> dict:
    if LEADS_FILE.exists():
        try:
            return json.loads(LEADS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"leads": [], "next_id": 1}


def save_leads(data: dict) -> None:
    LEADS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def add_lead(data: dict, name: str, contact: str, source: str = "") -> dict:
    lead = {
        "id": data["next_id"],
        "name": name,
        "contact": contact,
        "source": source,
        "status": "new",
        "notes": [],
        "created_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }
    data["leads"].append(lead)
    data["next_id"] += 1
    return lead


def get_lead(data: dict, lead_id: int) -> dict | None:
    for lead in data["leads"]:
        if lead["id"] == lead_id:
            return lead
    return None


def set_status(data: dict, lead_id: int, status: str) -> dict | None:
    lead = get_lead(data, lead_id)
    if lead is None:
        return None
    lead["status"] = status
    return lead


def add_note(data: dict, lead_id: int, note: str) -> dict | None:
    lead = get_lead(data, lead_id)
    if lead is None:
        return None
    lead["notes"].append({"text": note, "at": datetime.now().strftime("%d.%m %H:%M")})
    return lead


def delete_lead(data: dict, lead_id: int) -> bool:
    before = len(data["leads"])
    data["leads"] = [l for l in data["leads"] if l["id"] != lead_id]
    return len(data["leads"]) < before


def format_lead(lead: dict, short: bool = False) -> str:
    status = STATUS_LABELS.get(lead["status"], lead["status"])
    lines = [f"*#{lead['id']} {lead['name']}* — {status}"]
    lines.append(f"📞 {lead['contact']}")
    if lead.get("source"):
        lines.append(f"📌 Источник: {lead['source']}")
    lines.append(f"📅 Добавлен: {lead['created_at']}")
    if not short and lead.get("notes"):
        lines.append("📝 Заметки:")
        for n in lead["notes"]:
            lines.append(f"  • [{n['at']}] {n['text']}")
    return "\n".join(lines)


def format_leads_list(data: dict, status_filter: str | None = None) -> str:
    leads = data["leads"]
    if status_filter:
        leads = [l for l in leads if l["status"] == status_filter]
    if not leads:
        return "📋 Лидов нет."

    order = ["new", "work", "done", "refuse"]
    leads_sorted = sorted(leads, key=lambda l: order.index(l["status"]) if l["status"] in order else 9)

    lines = [f"📋 *Лиды* ({len(leads_sorted)} шт.):\n"]
    for lead in leads_sorted:
        lines.append(format_lead(lead, short=True))
        lines.append("")
    return "\n".join(lines).strip()


def format_leads_stats(data: dict) -> str:
    leads = data["leads"]
    total = len(leads)
    if total == 0:
        return "📊 Лидов пока нет."
    counts = {s: 0 for s in STATUS_LABELS}
    for l in leads:
        if l["status"] in counts:
            counts[l["status"]] += 1
    closed = counts["done"]
    conversion = round(closed / total * 100) if total else 0
    lines = [
        "📊 *Статистика лидов*\n",
        f"Всего: *{total}*",
        f"🆕 Новых: {counts['new']}",
        f"🔄 В работе: {counts['work']}",
        f"✅ Закрыто: {counts['done']}",
        f"❌ Отказов: {counts['refuse']}",
        f"\nКонверсия: *{conversion}%*",
    ]
    return "\n".join(lines)
