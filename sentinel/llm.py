"""The LLM: choose it with one setting, and the agent loop that lets it use tools."""
import json
import time

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from . import config


def groq_llm():
    from langchain_groq import ChatGroq
    return ChatGroq(model=config.GROQ_MODEL, api_key=config.GROQ_API_KEY, temperature=0, max_retries=1, timeout=60)


def get_llm():
    """Return a chat model, or None when there is no API key (offline mode)."""
    if config.LLM_PROVIDER == "gemini" and config.GOOGLE_API_KEY:
        from langchain_google_genai import ChatGoogleGenerativeAI

        def gemini(model):
            return ChatGoogleGenerativeAI(model=model, google_api_key=config.GOOGLE_API_KEY, temperature=0,
                                          max_retries=1, timeout=60)   # a slow answer -> we retry, then the backups
        # Busy model (503)? LangChain tries the backups in order: Gemini Lite, then Groq (if there is a Groq key).
        backups = [gemini(config.GEMINI_BACKUP_MODEL)] + ([groq_llm()] if config.GROQ_API_KEY else [])
        return gemini(config.GEMINI_MODEL).with_fallbacks(backups)

    if config.LLM_PROVIDER == "groq" and config.GROQ_API_KEY:
        return groq_llm()

    if config.LLM_PROVIDER == "openai" and config.OPENAI_API_KEY:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o-mini", api_key=config.OPENAI_API_KEY, temperature=0)

    return None


def text_of(message):
    """The answer text. Newer Gemini models can return a list of parts instead of one string."""
    content = message.content
    if isinstance(content, list):
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return content


def models_in(llm):
    """The main model and its backups, in order (a plain model is just [model])."""
    return [llm.runnable, *llm.fallbacks] if hasattr(llm, "fallbacks") else [llm]


def ask(llm, messages):
    """Ask the LLM. Slow or busy? Wait a little and ask the SAME question once more."""
    try:
        return llm.invoke(messages)
    except Exception:
        time.sleep(config.LLM_RETRY_WAIT)
        return llm.invoke(messages)


def investigate(model, system_prompt, task, tools, answer_shape, max_steps):
    """One investigation with ONE model: it calls tools until it has enough evidence, then answers."""
    tools_by_name = {t.name: t for t in tools}
    model_with_tools = model.bind_tools(tools)
    messages = [SystemMessage(system_prompt), HumanMessage(task)]
    steps = []

    for _ in range(max_steps):
        reply = ask(model_with_tools, messages)        # the LLM decides: call tools, or stop
        messages.append(reply)
        if not reply.tool_calls:
            break
        for call in reply.tool_calls:                  # run every tool it asked for, give back the result
            tool = tools_by_name.get(call["name"])
            try:
                result = str(tool.invoke(call["args"])) if tool else f"Unknown tool {call['name']}"
            except Exception as error:                 # a broken tool must not break the agent
                result = f"Tool error: {error}"
            steps.append({"tool": call["name"], "input": call["args"], "result": result[:600]})
            messages.append(ToolMessage(result, tool_call_id=call["id"]))

    # Final answer in a fixed shape, from the evidence it collected
    evidence = "\n".join(f"- {s['tool']}({json.dumps(s['input'], ensure_ascii=False)}) -> {s['result']}" for s in steps)
    final = [SystemMessage(system_prompt),
             HumanMessage(f"{task}\n\nEvidence you collected with your tools:\n{evidence or '- (no tools used)'}\n\n"
                          "Now give your final answer. Use only the evidence above, never invent numbers.")]
    return ask(model.with_structured_output(answer_shape), final), steps


def run_agent(llm, system_prompt, task, tools, answer_shape, max_steps=None):
    """The AI agent: the LLM decides which tools to call, reads the results, and decides again.

    If the model stops in the middle (slow, busy): it asks the same step again (ask).
    If it still fails: the backup model starts the investigation again from the beginning.
    If every model fails: the error goes up and the agent answers with the rules.
    Returns (answer, steps). `steps` = the agent's thinking: which tool, with which input, what came back.
    """
    for model in models_in(llm):
        try:
            return investigate(model, system_prompt, task, tools, answer_shape, max_steps or config.AGENT_MAX_STEPS)
        except Exception as error:
            last_error = error
    raise last_error
