import google.auth
from google.cloud import aiplatform
from config import settings

def init_vertex_ai():
    if settings.USE_VERTEX_AI:
        credentials, project = google.auth.default()
        aiplatform.init(
            project=settings.GOOGLE_CLOUD_PROJECT or project,
            location=settings.GOOGLE_CLOUD_REGION,
            credentials=credentials
        )

# Typical usage would be wrapping GenerativeModel or other specific Vertex services
# not already covered by the ADK framework.
class VertexAIService:
    @staticmethod
    def get_grounding_tool():
        # Used by the agent if search grounding is enabled
        from vertexai.preview.generative_models import Tool, grounding
        if settings.SEARCH_GROUNDING_ENABLED:
            return Tool.from_google_search_retrieval(grounding.GoogleSearchRetrieval())
        return None
