#!/usr/bin/env python3
"""
Система агентов ветеранской организации
Запуск: python main.py
"""
import os
import sys
from orchestrator import Orchestrator

BANNER = """
╔══════════════════════════════════════════════════════╗
║       СИСТЕМА АГЕНТОВ ВЕТЕРАНСКОЙ ОРГАНИЗАЦИИ        ║
║  admin │ social │ membership │ events │ comms         ║
╚══════════════════════════════════════════════════════╝
Введите задачу на русском языке. Команды: /выход  /агенты
"""

AGENTS_HELP = """
Доступные агенты:
  admin      — делопроизводство, протоколы, отчётность, планирование
  social     — соцпомощь, льготы, волонтёры, взаимодействие с соцзащитой
  membership — приём членов, база данных, учёт первичек
  events     — мероприятия, патриотическая работа, памятные даты
  comms      — СМИ, соцсети, рассылки, пресс-релизы

Оркестратор автоматически выбирает нужного агента.
Для прямого вызова агента: /admin <задача>
"""


def direct_agent(orchestrator: Orchestrator, line: str) -> None:
    parts = line.split(maxsplit=1)
    agent_name = parts[0].lstrip("/").lower()
    task = parts[1] if len(parts) > 1 else ""
    if not task:
        print("Укажите задачу после имени агента.")
        return
    if agent_name not in orchestrator.agents:
        print(f"Агент '{agent_name}' не найден.")
        return
    print(f"\n⚙️  [{agent_name.upper()}] обрабатывает задачу...\n")
    result = orchestrator.agents[agent_name].run(task)
    print(result)


def main():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Ошибка: переменная ANTHROPIC_API_KEY не задана.")
        sys.exit(1)

    orchestrator = Orchestrator(api_key=api_key)
    print(BANNER)

    while True:
        try:
            line = input(">> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nДо свидания!")
            break

        if not line:
            continue

        if line in ("/выход", "/exit", "/quit"):
            print("До свидания!")
            break

        if line in ("/агенты", "/agents", "/help"):
            print(AGENTS_HELP)
            continue

        # прямой вызов агента: /admin, /social, и т.д.
        known = ["admin", "social", "membership", "events", "comms"]
        first_word = line.split()[0].lstrip("/").lower()
        if line.startswith("/") and first_word in known:
            direct_agent(orchestrator, line)
            continue

        # обычный запрос через оркестратор
        result = orchestrator.run(line)
        print("\n" + "─" * 56)
        for agent_name, text in result["results"].items():
            if len(result["results"]) > 1:
                print(f"\n[{agent_name.upper()}]")
            print(text)
        print("─" * 56 + "\n")


if __name__ == "__main__":
    main()
