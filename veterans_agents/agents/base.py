from anthropic import Anthropic


class BaseAgent:
    name: str = "agent"
    system_prompt: str = ""

    def __init__(self, client: Anthropic, model: str = "claude-haiku-4-5-20251001"):
        self.client = client
        self.model = model

    def run(self, task: str, context: str = "") -> str:
        user_content = task
        if context:
            user_content = f"Дополнительный контекст:\n{context}\n\nЗадача:\n{task}"

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        return response.content[0].text
