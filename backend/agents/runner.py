from google.adk.runners import Runner
from google.adk.apps import App
from google.adk.sessions import InMemorySessionService
from agents.orchestrator import orchestrator_agent
from config import settings

app = App(
    name="agents",
    root_agent=orchestrator_agent
)

# For now we use InMemorySessionService. 
# We can switch to FirestoreSessionService later if we build it out fully.
runner = Runner(
    app=app,
    session_service=InMemorySessionService()
)
