class LLMClient:
    def __init__(self, response: str):
        self.response = response
        self.calls = 0

    def complete(self, prompt: str, timeout_seconds: float) -> str:
        self.calls += 1
        assert "pr-1" not in prompt
        return self.response