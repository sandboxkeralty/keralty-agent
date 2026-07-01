from google.adk.runners import Runner
from google.adk.apps import App
from agents.orchestrator import orchestrator_agent
from services.adk_session_service import FirestoreSessionService

app = App(
    name="agents",
    root_agent=orchestrator_agent
)

runner = Runner(
    app=app,
    session_service=FirestoreSessionService()
)
