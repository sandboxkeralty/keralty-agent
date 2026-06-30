from googleapiclient.discovery import build
import google.auth

def get_slides_service():
    credentials, _ = google.auth.default()
    return build('slides', 'v1', credentials=credentials)

class SlidesService:
    @staticmethod
    def create_presentation(title: str) -> str:
        service = get_slides_service()
        body = {'title': title}
        presentation = service.presentations().create(body=body).execute()
        return presentation.get('presentationId')
        
    @staticmethod
    def create_slide(presentation_id: str, title: str, subtitle: str = "") -> str:
        service = get_slides_service()
        requests = [
            {
                'createSlide': {
                    'objectId': f"slide_{title.replace(' ', '_').lower()}",
                    'slideLayoutReference': {
                        'predefinedLayout': 'TITLE_AND_BODY'
                    }
                }
            }
        ]
        
        # In a complete implementation, we'd find the generated placeholders
        # and insert the title/subtitle. For the prototype, we just create the slide.
        response = service.presentations().batchUpdate(
            presentationId=presentation_id, body={'requests': requests}).execute()
        
        return response.get('replies')[0].get('createSlide').get('objectId')
