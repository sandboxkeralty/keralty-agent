import uuid
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
    def get_presentation(presentation_id: str, credentials=None) -> dict:
        service = get_slides_service(credentials)
        return service.presentations().get(presentationId=presentation_id).execute()

    @staticmethod
    def add_slide_with_content(
        presentation_id: str,
        title: str,
        body: str,
        speaker_notes: str = "",
        credentials=None,
    ) -> str:
        """Adds a slide with TITLE_AND_BODY layout, populates title + body text.

        Returns the new slide's objectId.
        """
        service = get_slides_service(credentials)
        slide_id = f"slide_{uuid.uuid4().hex[:12]}"
        title_id = f"{slide_id}_title"
        body_id = f"{slide_id}_body"

        requests = [
            {
                'createSlide': {
                    'objectId': slide_id,
                    'slideLayoutReference': {'predefinedLayout': 'TITLE_AND_BODY'},
                    'placeholderIdMappings': [
                        {
                            'layoutPlaceholder': {'type': 'TITLE', 'index': 0},
                            'objectId': title_id,
                        },
                        {
                            'layoutPlaceholder': {'type': 'BODY', 'index': 0},
                            'objectId': body_id,
                        },
                    ],
                }
            },
            {
                'insertText': {
                    'objectId': title_id,
                    'insertionIndex': 0,
                    'text': title,
                }
            },
            {
                'insertText': {
                    'objectId': body_id,
                    'insertionIndex': 0,
                    'text': body,
                }
            },
        ]

        if speaker_notes:
            # Speaker notes live on the slide's notesPage shape
            # We add them after creating the slide in a second batch to get the notes objectId
            pass  # handled below after first batch

        service.presentations().batchUpdate(
            presentationId=presentation_id,
            body={'requests': requests},
        ).execute()

        if speaker_notes:
            SlidesService._add_speaker_notes(service, presentation_id, slide_id, speaker_notes)

        return slide_id

    @staticmethod
    def _add_speaker_notes(service, presentation_id: str, slide_id: str, notes: str) -> None:
        """Inserts speaker notes for an existing slide."""
        pres = service.presentations().get(presentationId=presentation_id).execute()
        notes_id = None
        for slide in pres.get('slides', []):
            if slide.get('objectId') == slide_id:
                notes_page = slide.get('slideProperties', {}).get('notesPage', {})
                for element in notes_page.get('pageElements', []):
                    shape = element.get('shape', {})
                    if shape.get('placeholder', {}).get('type') == 'BODY':
                        notes_id = element.get('objectId')
                        break
        if notes_id:
            service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': [{'insertText': {'objectId': notes_id, 'insertionIndex': 0, 'text': notes}}]},
            ).execute()

    @staticmethod
    def insert_image(
        presentation_id: str,
        slide_id: str,
        image_url: str,
        left_emu: int = 4_500_000,
        top_emu: int = 1_500_000,
        width_emu: int = 4_500_000,
        height_emu: int = 3_000_000,
        credentials=None,
    ) -> str:
        """Inserts an image from a public URL into a slide. Returns the image objectId."""
        service = get_slides_service(credentials)
        image_id = f"img_{uuid.uuid4().hex[:12]}"
        requests = [
            {
                'createImage': {
                    'objectId': image_id,
                    'url': image_url,
                    'elementProperties': {
                        'pageObjectId': slide_id,
                        'size': {
                            'width':  {'magnitude': width_emu,  'unit': 'EMU'},
                            'height': {'magnitude': height_emu, 'unit': 'EMU'},
                        },
                        'transform': {
                            'scaleX': 1,
                            'scaleY': 1,
                            'translateX': left_emu,
                            'translateY': top_emu,
                            'unit': 'EMU',
                        },
                    },
                }
            }
        ]
        service.presentations().batchUpdate(
            presentationId=presentation_id,
            body={'requests': requests},
        ).execute()
        return image_id

    @staticmethod
    def create_slide(presentation_id: str, title: str, subtitle: str = "", credentials=None) -> str:
        """Legacy: creates a blank slide (no text content). Kept for backwards compat."""
        service = get_slides_service(credentials)
        slide_id = f"slide_{uuid.uuid4().hex[:12]}"
        requests = [
            {
                'createSlide': {
                    'objectId': slide_id,
                    'slideLayoutReference': {'predefinedLayout': 'TITLE_AND_BODY'},
                }
            }
        ]
        service.presentations().batchUpdate(
            presentationId=presentation_id, body={'requests': requests}
        ).execute()
        return slide_id
