"""Per-model ADK Runner factory.

One Runner (and one full agent tree) per selected chat model, built lazily and
cached — ADK exposes no per-request model override on run_async/RunConfig, so
model selection means selecting a Runner.

Two invariants keep conversations coherent across model switches:
- ALL runners share ONE FirestoreSessionService instance, and
- every App uses the same name ("agents"),
so a session's history/state is found by whichever runner handles the turn.
"""

from google.adk.runners import Runner
from google.adk.apps import App

from agents.orchestrator import build_agent_tree
from services.adk_session_service import FirestoreSessionService
from services.model_registry import DEFAULT_MODEL_KEY, get_spec, make_adk_model

_session_service = FirestoreSessionService()
_runners: dict = {}


def get_runner(model_key: str = DEFAULT_MODEL_KEY) -> Runner:
    spec = get_spec(model_key)
    if spec.key not in _runners:
        _runners[spec.key] = Runner(
            app=App(name="agents", root_agent=build_agent_tree(make_adk_model(spec))),
            session_service=_session_service,
        )
    return _runners[spec.key]


# Back-compat: module-level default runner (Gemini) for existing importers.
runner = get_runner()
app = runner.app
