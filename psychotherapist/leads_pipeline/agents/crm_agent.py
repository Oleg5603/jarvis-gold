"""
CRM Agent — финалист пайплайна.
Берёт enriched_leads.json → фильтрует → пишет ready_for_crm.json
Опционально: пушит в Google Sheets (нужны GOOGLE_SHEETS_ID + сервисный аккаунт).
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
INPUT_FILE = ROOT / "leads_pipeline" / "enriched_leads.json"
OUTPUT_FILE = ROOT / "leads_pipeline" / "ready_for_crm.json"

READINESS_SCALE = {
    (80, 100): 5,
    (65, 79):  4,
    (55, 64):  3,
    (40, 54):  2,
    (0,  39):  1,
}

DISCLAIMER = "⚠️ Лид найден в открытом публичном источнике. Человек не давал явного согласия на контакт. Рекомендуется мягкий нерекламный подход."


def score_to_readiness(score: float) -> int:
    for (lo, hi), level in READINESS_SCALE.items():
        if lo <= score <= hi:
            return level
    return 1


def format_for_crm(lead: dict) -> dict:
    score = lead.get("confidence_score", 0)
    return {
        "id": lead.get("url", "")[-20:].replace("/", "_"),
        "source_url": lead.get("url", ""),
        "source_name": lead.get("source", ""),
        "author": lead.get("author", ""),
        "quote": lead.get("quote", "")[:200],
        "created_at": lead.get("createdAt", ""),
        "intent_score": lead.get("intentScore", 0),
        "confidence_score": round(score, 1),
        "readiness_level": score_to_readiness(score),
        "status": "ожидает контакта",
        "validation_notes": lead.get("validation", {}).get("notes", ""),
        "added_to_crm": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "disclaimer": DISCLAIMER,
    }


def push_to_google_sheets(crm_leads: list[dict]) -> bool:
    sheets_id = os.environ.get("GOOGLE_SHEETS_ID")
    if not sheets_id:
        print("[crm] GOOGLE_SHEETS_ID не задан — пропуск Google Sheets", flush=True)
        return False

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        creds_file = ROOT / "leads_pipeline" / "google_creds.json"
        if not creds_file.exists():
            print("[crm] google_creds.json не найден — пропуск Google Sheets", flush=True)
            return False

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(str(creds_file), scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(sheets_id)
        ws = sh.sheet1

        if ws.row_count < 2:
            headers = ["ID", "URL", "Источник", "Автор", "Цитата", "Дата", "Интент", "Уверенность", "Готовность", "Статус", "Заметки", "Добавлен", "Дисклеймер"]
            ws.append_row(headers)

        for lead in crm_leads:
            ws.append_row([
                lead["id"], lead["source_url"], lead["source_name"],
                lead["author"], lead["quote"], lead["created_at"],
                lead["intent_score"], lead["confidence_score"],
                lead["readiness_level"], lead["status"],
                lead["validation_notes"], lead["added_to_crm"], lead["disclaimer"],
            ])

        print(f"[crm] Google Sheets: добавлено {len(crm_leads)} строк", flush=True)
        return True
    except Exception as e:
        print(f"[crm] Google Sheets ошибка: {e}", flush=True)
        return False


def run():
    print("[crm] Старт CRM Agent", flush=True)

    if not INPUT_FILE.exists():
        print("[crm] enriched_leads.json не найден — нет данных", flush=True)
        sys.exit(0)

    enriched = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    ready = [l for l in enriched if l.get("ready_for_contact", False)]
    print(f"[crm] Лидов на входе: {len(enriched)}, готовых к контакту: {len(ready)}", flush=True)

    crm_leads = [format_for_crm(l) for l in ready]

    # Сортировка: сначала самые готовые
    crm_leads.sort(key=lambda l: l["confidence_score"], reverse=True)

    OUTPUT_FILE.write_text(json.dumps(crm_leads, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[crm] Записано в {OUTPUT_FILE}", flush=True)

    # Опциональный Google Sheets
    push_to_google_sheets(crm_leads)

    # Сводка
    levels = [l["readiness_level"] for l in crm_leads]
    print(f"\n[crm] ИТОГО готово для психотерапевта: {len(crm_leads)} лидов", flush=True)
    for level in range(5, 0, -1):
        count = levels.count(level)
        bar = "█" * count
        print(f"  Готовность {level}/5: {bar} {count}", flush=True)


if __name__ == "__main__":
    run()
