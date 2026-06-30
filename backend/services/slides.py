from googleapiclient.discovery import build
import google.auth

_SLIDES_SCOPES = [
    'https://www.googleapis.com/auth/presentations',
    'https://www.googleapis.com/auth/drive',
]

def get_slides_service(credentials=None):
    if credentials is None:
        credentials, _ = google.auth.default(scopes=_SLIDES_SCOPES)
    return build('slides', 'v1', credentials=credentials)

class SlidesService:
    @staticmethod
    def create_presentation(title: str, credentials=None) -> str:
        service = get_slides_service(credentials)
        presentation = service.presentations().create(body={'title': title}).execute()
        return presentation.get('presentationId')

    @staticmethod
    def create_slide(presentation_id: str, title: str, subtitle: str = "", credentials=None) -> str:
        service = get_slides_service(credentials)
        requests = [
            {
                'createSlide': {
                    'objectId': f"slide_{title.replace(' ', '_').lower()}",
                    'slideLayoutReference': {'predefinedLayout': 'TITLE_AND_BODY'}
                }
            }
        ]
        response = service.presentations().batchUpdate(
            presentationId=presentation_id, body={'requests': requests}).execute()
        return response.get('replies')[0].get('createSlide').get('objectId')
