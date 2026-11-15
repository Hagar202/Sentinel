"""A fake LLM for tests: it follows a script (tool calls, then a final answer). No API key, no internet."""
from langchain_core.messages import AIMessage


class ScriptedLLM:
    def __init__(self, tool_calls=None, answer=None, text="Fake summary."):
        self.rounds = [AIMessage("", tool_calls=[{"name": n, "args": a, "id": f"call{i}"} for i, (n, a) in enumerate(r)])
                       for r in (tool_calls or [])] + [AIMessage(text)]
        self.answer, self.text, self.prompts = answer or {}, text, []

    def bind_tools(self, tools):
        return self

    def with_structured_output(self, shape):
        llm = self

        class Structured:
            def invoke(self, messages):
                llm.prompts.append(messages)
                return shape(**llm.answer)
        return Structured()

    def invoke(self, messages):
        self.prompts.append(messages)
        return self.rounds.pop(0) if self.rounds else AIMessage(self.text)
