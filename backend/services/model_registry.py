"""Chat model registry for the multi-LLM picker.

Registry KEYS (e.g. "claude-sonnet") are the stable contract carried by the
frontend picker, ChatRequest.model and session state — never raw provider ids
(those live in config and can be env-corrected without touching clients).

Gemini is the default and always available. Claude/OpenAI models appear only
when their API key is configured — the picker never offers a dead model.
The whole agent tree runs the selected model (product decision), except
WebSearchAgent which stays pinned to Gemini (google_search is Gemini-only).
"""

from dataclasses import dataclass
from typing import List, Optional, Union

from config import settings

DEFAULT_MODEL_KEY = "gemini"


@dataclass(frozen=True)
class ModelSpec:
    key: str            # stable picker id
    provider: str       # "google" | "anthropic" | "openai"
    display_name: str
    model_id: str       # provider API id (empty for the Gemini default: the
                        # agent tree keeps its per-agent flash/pro tier strings)


def _all_specs() -> List[ModelSpec]:
    s = settings
    return [
        ModelSpec("gemini", "google", "Gemini", ""),
        ModelSpec("claude-fable", "anthropic", "Claude Fable", s.MODEL_ID_CLAUDE_FABLE),
        ModelSpec("claude-opus", "anthropic", "Claude Opus", s.MODEL_ID_CLAUDE_OPUS),
        ModelSpec("claude-sonnet", "anthropic", "Claude Sonnet", s.MODEL_ID_CLAUDE_SONNET),
        ModelSpec("claude-haiku", "anthropic", "Claude Haiku", s.MODEL_ID_CLAUDE_HAIKU),
        ModelSpec("openai-sol", "openai", "OpenAI Sol", s.MODEL_ID_OPENAI_SOL),
        ModelSpec("openai-terra", "openai", "OpenAI Terra", s.MODEL_ID_OPENAI_TERRA),
        ModelSpec("openai-luna", "openai", "OpenAI Luna", s.MODEL_ID_OPENAI_LUNA),
        ModelSpec("openai-gpt55", "openai", "OpenAI GPT 5.5", s.MODEL_ID_OPENAI_GPT55),
    ]


def _provider_available(provider: str) -> bool:
    if provider == "google":
        return True
    if provider == "anthropic":
        return bool(settings.ANTHROPIC_API_KEY)
    if provider == "openai":
        return bool(settings.OPENAI_API_KEY)
    return False


def available_models() -> List[ModelSpec]:
    return [m for m in _all_specs() if _provider_available(m.provider)]


def get_spec(key: Optional[str]) -> ModelSpec:
    """Resolves a picker key to its spec. Unknown or key-less models fall back
    to the Gemini default with a warning — a stale frontend or a removed key
    must degrade, never break a chat turn."""
    wanted = (key or DEFAULT_MODEL_KEY).strip().lower()
    for m in _all_specs():
        if m.key == wanted:
            if _provider_available(m.provider):
                return m
            print(f"[model_registry] model '{wanted}' unavailable (no API key) — using default")
            break
    else:
        if wanted != DEFAULT_MODEL_KEY:
            print(f"[model_registry] unknown model key '{wanted}' — using default")
    return _all_specs()[0]


def make_adk_model(spec: ModelSpec) -> Union[str, object, None]:
    """Returns what agents.orchestrator.build_agent_tree expects as `model`:
    None for the Gemini default (agents keep their per-tier model strings),
    or a LiteLlm instance for Anthropic/OpenAI (LiteLLM reads the provider
    key from os.environ)."""
    if spec.provider == "google":
        return None
    from google.adk.models.lite_llm import LiteLlm
    kwargs = {}
    if spec.provider == "openai" and spec.model_id.startswith("gpt-5.6"):
        # OpenAI (observed live 2026-07-17): gpt-5.6 reasoning models reject
        # function tools on /v1/chat/completions unless reasoning_effort is
        # explicitly "none" (400 otherwise — the family reasons by default).
        # Every agent carries at least transfer_to_agent, so without this the
        # whole tree is unusable on these models. ADK's LiteLlm forwards extra
        # kwargs to litellm.acompletion via _additional_args.
        kwargs["reasoning_effort"] = "none"
    return LiteLlm(model=f"{spec.provider}/{spec.model_id}", **kwargs)
