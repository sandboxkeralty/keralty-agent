import uuid
from google.adk.tools import ToolContext
from config import settings


async def image_generate(prompt: str, tool_context: ToolContext = None) -> dict:
    """Generates an image using Vertex AI Imagen 3 and uploads it to GCS.

    Args:
        prompt: Text description of the image to generate.
    """
    try:
        import vertexai
        from vertexai.preview.vision_models import ImageGenerationModel
        from google.cloud import storage

        vertexai.init(project=settings.GOOGLE_CLOUD_PROJECT, location=settings.GOOGLE_CLOUD_REGION)

        model = ImageGenerationModel.from_pretrained(settings.IMAGEN_MODEL)
        result = model.generate_images(prompt=prompt, number_of_images=1)

        if not result.images:
            return {"status": "error", "error": "No images generated"}

        image_bytes = result.images[0]._image_bytes

        blob_name = f"images/{uuid.uuid4()}.png"
        client = storage.Client(project=settings.GOOGLE_CLOUD_PROJECT)
        bucket = client.bucket(settings.GCS_BUCKET)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(image_bytes, content_type="image/png")
        blob.make_public()

        public_url = blob.public_url
        return {"status": "success", "image_url": public_url, "gcs_path": f"gs://{settings.GCS_BUCKET}/{blob_name}"}

    except Exception as e:
        print(f"[image_generate] Error: {e}")
        return {"status": "error", "error": str(e), "image_url": "https://via.placeholder.com/1024x768?text=Image+Generation+Failed"}
