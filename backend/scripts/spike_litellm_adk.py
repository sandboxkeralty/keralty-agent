"""SPIKE (Feature 2 hard gate): does ADK 2.3.0 + LiteLLM support our tree?

Verifies, on a minimal 2-agent tree running a non-Gemini model:
  (a) the auto-injected transfer_to_agent fires parent -> child
  (b) a custom function tool round-trips
  (c) an instruction with the optional placeholder {writing_style?} resolves
  (d) streaming events flow through run_async
Also prints the exception type/shape LiteLLM raises so _is_quota_error can be
tuned (routers/chat.py).

Run INSIDE the prod image (py3.11, google-adk==2.3.0) — the local venv is an
older ADK on py3.9 and proves nothing:

  docker build --platform linux/amd64 -t spike ./backend
  docker run --rm --platform linux/amd64 -e ANTHROPIC_API_KEY=sk-... \
      spike python scripts/spike_litellm_adk.py anthropic/claude-haiku-4-5-20251001
  docker run --rm --platform linux/amd64 -e OPENAI_API_KEY=sk-... \
      spike python scripts/spike_litellm_adk.py openai/<confirmed-id>

Pass = all four criteria print OK. Any failure halts Feature 2 for redesign.
"""

import asyncio
import sys

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


def get_office_temperature(city: str) -> dict:
    """Returns the current office temperature for a city (spike test tool)."""
    return {"status": "success", "city": city, "temperature_c": 21.5}


def build(model_str: str) -> Runner:
    model = LiteLlm(model=model_str)
    child = Agent(
        name="FacilitiesAgent",
        model=model,
        instruction=(
            "Eres el agente de instalaciones. Cuando te pregunten por la temperatura "
            "de una oficina usa la herramienta get_office_temperature y responde con "
            "el valor.\n{writing_style?}"
        ),
        description="Handles office/facilities questions like office temperature.",
        tools=[get_office_temperature],
    )
    parent = Agent(
        name="RootAgent",
        model=model,
        instruction=(
            "Eres el orquestador. NO respondas tú mismo preguntas de instalaciones "
            "(temperatura de oficinas): transfiérelas al FacilitiesAgent.\n"
            "{writing_style?}"
        ),
        description="Root agent that delegates facilities questions.",
        sub_agents=[child],
    )
    return Runner(app=App(name="spike", root_agent=parent),
                  session_service=InMemorySessionService())


async def main(model_str: str) -> None:
    runner = build(model_str)
    await runner.session_service.create_session(
        app_name="spike", user_id="spike-user", session_id="s1",
        state={"writing_style": ""},  # (c): placeholder must resolve, not KeyError
    )

    events = []
    transferred = False
    tool_ran = False
    text = ""
    try:
        async for event in runner.run_async(
            new_message=types.Content(role="user", parts=[types.Part(
                text="¿Cuál es la temperatura de la oficina de Bogotá?")]),
            session_id="s1", user_id="spike-user",
        ):
            events.append(event)
            try:
                for call in event.get_function_calls() or []:
                    if call.name == "transfer_to_agent":
                        transferred = True
                    if call.name == "get_office_temperature":
                        tool_ran = True
            except Exception:
                pass
            content = getattr(event, "content", None)
            for p in (getattr(content, "parts", None) or []):
                if p.text:
                    text += p.text
    except Exception as e:
        print(f"\nEXCEPTION during run: {type(e).__module__}.{type(e).__name__}: {e}")
        print("(capture this shape for _is_quota_error if it's a rate limit)")
        raise

    print(f"\n=== SPIKE RESULTS for {model_str} ===")
    print(f"(a) transfer_to_agent fired : {'OK' if transferred else 'FAIL'}")
    print(f"(b) custom tool round-trip  : {'OK' if tool_ran else 'FAIL'}")
    print(f"(c) {{writing_style?}} resolved: OK (no KeyError — run completed)")
    print(f"(d) streaming events        : {'OK' if len(events) > 1 else 'FAIL'} ({len(events)} events)")
    print(f"final text: {text[:200]}")
    ok = transferred and tool_ran and len(events) > 1 and "21.5" in text
    print(f"\nGATE: {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else
                     "anthropic/claude-haiku-4-5-20251001"))
