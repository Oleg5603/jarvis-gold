"""
Reporter Agent — итоговый отчёт команды прогрева.
Вход: warming_pipeline/sequences.json → Выход: warming_pipeline/report.json
"""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
INPUT_FILE = ROOT / "warming_pipeline" / "sequences.json"
OUTPUT_FILE = ROOT / "warming_pipeline" / "report.json"


def run():
    print("[reporter] Старт Reporter Agent", flush=True)

    if not INPUT_FILE.exists():
        print("[reporter] sequences.json не найден", flush=True)
        sys.exit(0)

    sequences = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    print(f"[reporter] Последовательностей: {len(sequences)}", flush=True)

    if not sequences:
        report = {"error": "нет данных", "generated_at": datetime.now().isoformat()}
        OUTPUT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        sys.exit(0)

    # Статистика по готовности
    urgency_counts = {"высокая": 0, "средняя": 0, "низкая": 0}
    readiness_counts = {"высокая": 0, "средняя": 0, "низкая": 0}
    sources = {}
    fallback_count = 0

    top_leads = []

    for lead in sequences:
        p = lead.get("profile", {})
        urgency = p.get("urgency", "средняя")
        readiness = p.get("readiness_to_help", "средняя")

        urgency_counts[urgency] = urgency_counts.get(urgency, 0) + 1
        readiness_counts[readiness] = readiness_counts.get(readiness, 0) + 1

        src = lead.get("source_name", "неизвестно")
        sources[src] = sources.get(src, 0) + 1

        if p.get("_fallback"):
            fallback_count += 1

        priority_score = (
            (3 if urgency == "высокая" else 1 if urgency == "средняя" else 0) +
            (3 if readiness == "высокая" else 1 if readiness == "средняя" else 0) +
            lead.get("confidence_score", 0) / 20
        )

        fc = lead.get("first_contact", {})
        top_leads.append({
            "author": lead.get("author", ""),
            "source": lead.get("source_name", ""),
            "url": lead.get("source_url", ""),
            "pain_point": p.get("pain_point", ""),
            "urgency": urgency,
            "readiness": readiness,
            "confidence_score": lead.get("confidence_score", 0),
            "first_message": fc.get("message", ""),
            "expected_response_rate": fc.get("expected_response_rate", ""),
            "total_touches": lead.get("total_touches", 6),
            "priority_score": round(priority_score, 1),
        })

    top_leads.sort(key=lambda x: x["priority_score"], reverse=True)

    ready_to_send = sum(1 for l in top_leads if l["priority_score"] >= 4)

    report = {
        "generated_at": datetime.now().isoformat(),
        "total_leads": len(sequences),
        "ready_to_send": ready_to_send,
        "scripts_written": len(sequences),
        "sequences_built": len(sequences),
        "has_api_key": fallback_count < len(sequences),
        "urgency_breakdown": urgency_counts,
        "readiness_breakdown": readiness_counts,
        "sources": sources,
        "priority_leads": top_leads[:10],
        "all_leads": top_leads,
    }

    OUTPUT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 50, flush=True)
    print(f"[reporter] ИТОГ AI-КОМАНДЫ ПРОГРЕВА", flush=True)
    print(f"  Всего лидов обработано: {len(sequences)}", flush=True)
    print(f"  Готово к отправке прямо сейчас: {ready_to_send}", flush=True)
    print(f"  Скриптов написано: {len(sequences)}", flush=True)
    print(f"  Срочность высокая: {urgency_counts.get('высокая', 0)}", flush=True)
    print(f"  Готовность высокая: {readiness_counts.get('высокая', 0)}", flush=True)
    print("\n  ТОП-3 ПРИОРИТЕТНЫХ ЛИДА:", flush=True)
    for i, lead in enumerate(top_leads[:3], 1):
        print(f"  {i}. {lead['author']} ({lead['source']}) — {lead['pain_point'][:60]}", flush=True)
        print(f"     Первое сообщение: {lead['first_message'][:80]}...", flush=True)
    print("=" * 50, flush=True)
    print(f"[reporter] Отчёт → {OUTPUT_FILE}", flush=True)


if __name__ == "__main__":
    run()
