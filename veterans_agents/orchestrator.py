import json
import re
from anthropic import Anthropic
from agents import AdminAgent, SocialAgent, MembershipAgent, EventsAgent, CommsAgent

AGENT_MAP = {
    "admin": AdminAgent,
    "social": SocialAgent,
    "membership": MembershipAgent,
    "events": EventsAgent,
    "comms": CommsAgent,
}

AGENT_DESCRIPTIONS = {
    "admin": "делопроизводство, протоколы заседаний, отчётность, планирование работы организации",
    "social": "социальная помощь, льготы, субсидии, волонтёры, взаимодействие с соцзащитой",
    "membership": "приём членов, база данных, учёт первичек, статистика членства",
    "events": "мероприятия, памятные даты, уроки мужества, уход за захоронениями, патриотические акции",
    "comms": "пресс-релизы, посты в соцсетях, рассылки членам, работа со СМИ",
}

ROUTING_PROMPT = f"""Ты — диспетчер ветеранской организации. Определи, какой агент или агенты должны обработать запрос.

Доступные агенты:
{chr(10).join(f'- {k}: {v}' for k, v in AGENT_DESCRIPTIONS.items())}

Правила:
- Выбирай минимально необходимое количество агентов (обычно 1, редко 2)
- Если задача явно пересекает две области — включай оба агента
- Отвечай ТОЛЬКО JSON без пояснений и маркдауна

Формат ответа:
{{"agents": ["agent_name"], "reason": "одна строка — почему именно эти агенты"}}"""


class Orchestrator:
    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001"):
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.agents = {name: cls(self.client, model) for name, cls in AGENT_MAP.items()}

    def _route(self, task: str) -> tuple[list[str], str]:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=256,
            system=ROUTING_PROMPT,
            messages=[{"role": "user", "content": task}],
        )
        raw = response.content[0].text.strip()
        # strip possible markdown code fences
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        data = json.loads(raw)
        agents = [a for a in data.get("agents", []) if a in AGENT_MAP]
        if not agents:
            agents = ["admin"]
        return agents, data.get("reason", "")

    def run(self, task: str, verbose: bool = True) -> dict:
        agent_names, reason = self._route(task)

        if verbose:
            print(f"\n🔀 Оркестратор → {', '.join(agent_names)}")
            print(f"   Причина: {reason}\n")

        results = {}
        for name in agent_names:
            if verbose:
                print(f"⚙️  [{name.upper()}] обрабатывает задачу...")
            results[name] = self.agents[name].run(task)

        return {"agents": agent_names, "reason": reason, "results": results}
