import logging
from google.cloud import logging as cloud_logging
from config import settings

def setup_logging():
    if settings.ENVIRONMENT != "development":
        client = cloud_logging.Client(project=settings.GOOGLE_CLOUD_PROJECT)
        client.setup_logging()
    
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger("keralty-agent")

logger = setup_logging()
