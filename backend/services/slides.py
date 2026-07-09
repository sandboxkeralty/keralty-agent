import re
import uuid
from googleapiclient.discovery import build
import google.auth

from config import settings

_SLIDES_SCOPES = [
    'https://www.googleapis.com/auth/presentations',
    'https://www.googleapis.com/auth/drive',
]

# Default Google Slides 16:9 canvas, EMU.
SLIDE_W = 9_144_000
SLIDE_H = 5_143_500

# Image placement presets. All are exact 16:9 footprints so a 16:9 Imagen
# output fills the box deterministically (createImage scales-to-fit preserving
# aspect and centers — a non-16:9 box would letterbox unpredictably). There is
# deliberately no banner/strip preset: Slides' cropProperties is read-only via
# the API, so a 16:3 crop of a 16:9 image is not achievable.
_PLACEMENTS = {
    'full_bleed': (0, 0, SLIDE_W, SLIDE_H),
    'right_half': (SLIDE_W // 2, SLIDE_H // 4, SLIDE_W // 2, SLIDE_H // 2),
    'left_half': (0, SLIDE_H // 4, SLIDE_W // 2, SLIDE_H // 2),
    'centered': (SLIDE_W // 8, SLIDE_H // 8, SLIDE_W * 3 // 4, SLIDE_H * 3 // 4),
}

# Semantic layout -> Slides predefinedLayout, used when the deck has no usable
# template layout map (blank decks, or unmapped semantics).
_PREDEFINED = {
    'cover': 'TITLE',
    'section': 'SECTION_HEADER',
    'closing': 'SECTION_HEADER',
    'content': 'TITLE_AND_BODY',
    'two_column': 'TITLE_AND_TWO_COLUMNS',
    'title_only': 'TITLE_ONLY',
    'quote': 'BLANK',
    'big_number': 'BLANK',
}


def get_slides_service(credentials=None):
    if credentials is None:
        credentials, _ = google.auth.default(scopes=_SLIDES_SCOPES)
    return build('slides', 'v1', credentials=credentials)


def _hex_to_rgb(hex_color: str) -> dict:
    h = hex_color.lstrip('#')
    return {
        'red': int(h[0:2], 16) / 255.0,
        'green': int(h[2:4], 16) / 255.0,
        'blue': int(h[4:6], 16) / 255.0,
    }


class SlidesService:
    @staticmethod
    def create_presentation(title: str, credentials=None) -> str:
        """Creates a deck. When SLIDES_TEMPLATE_ID is set, copies the corporate
        template (inheriting its master/theme: fonts, colors, backgrounds) and
        deletes its stock slides so the caller starts from an empty themed deck.
        Any template failure falls back loudly to a blank default-themed deck —
        a deck must always be produced."""
        if settings.SLIDES_TEMPLATE_ID:
            try:
                from services.drive import DriveService
                pid = DriveService.copy_file(settings.SLIDES_TEMPLATE_ID, title, credentials)
                service = get_slides_service(credentials)
                pres = service.presentations().get(
                    presentationId=pid, fields='slides(objectId)'
                ).execute()
                reqs = [{'deleteObject': {'objectId': s['objectId']}}
                        for s in pres.get('slides', [])]
                if reqs:
                    service.presentations().batchUpdate(
                        presentationId=pid, body={'requests': reqs}
                    ).execute()
                return pid
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"[slides] TEMPLATE COPY FAILED ({settings.SLIDES_TEMPLATE_ID}): {e} "
                      f"— falling back to blank deck", flush=True)
        service = get_slides_service(credentials)
        presentation = service.presentations().create(body={'title': title}).execute()
        return presentation.get('presentationId')

    @staticmethod
    def resolve_layouts(presentation_id: str, credentials=None) -> dict:
        """Maps this deck's layouts to semantic names by PLACEHOLDER INVENTORY.

        Converted-PPTX layouts usually report layoutProperties.name == "CUSTOM",
        so placeholder signatures are the reliable classification signal; the
        predefined-enum name and displayName only break ties. Returns
        {semantic: {"layoutId": ..., "placeholders": [{"type","index"}]}} —
        missing semantics are allowed (callers fall back to predefinedLayout
        or BLANK + text boxes).
        """
        service = get_slides_service(credentials)
        pres = service.presentations().get(
            presentationId=presentation_id,
            fields="layouts(objectId,layoutProperties(name,displayName),"
                   "pageElements(objectId,shape(placeholder(type,index))))",
        ).execute()

        layout_map: dict = {}

        def _claim(semantic, layout, phs):
            if semantic not in layout_map:
                layout_map[semantic] = {
                    'layoutId': layout['objectId'],
                    'placeholders': phs,
                }

        for layout in pres.get('layouts', []):
            phs = []
            for el in layout.get('pageElements', []):
                ph = el.get('shape', {}).get('placeholder')
                if ph and ph.get('type'):
                    phs.append({'type': ph['type'], 'index': ph.get('index', 0)})
            types = [p['type'] for p in phs]
            name = layout.get('layoutProperties', {}).get('name', '')
            display = layout.get('layoutProperties', {}).get('displayName', '')
            n_body = types.count('BODY')
            has_title = 'TITLE' in types or 'CENTERED_TITLE' in types

            if 'CENTERED_TITLE' in types or ('SUBTITLE' in types and has_title):
                _claim('cover', layout, phs)
            elif name == 'SECTION_HEADER' or (
                has_title and n_body == 0 and re.search(r'secci|section|divider', display, re.I)
            ):
                _claim('section', layout, phs)
            elif has_title and n_body == 1:
                _claim('content', layout, phs)
            elif has_title and n_body == 2:
                _claim('two_column', layout, phs)
            elif has_title and n_body == 0 and 'SUBTITLE' not in types:
                _claim('title_only', layout, phs)
            elif not phs:
                _claim('blank', layout, phs)
            # Predefined-enum names win outright when they match exactly.
            enum_match = {
                'TITLE': 'cover', 'SECTION_HEADER': 'section',
                'TITLE_AND_BODY': 'content', 'TITLE_AND_TWO_COLUMNS': 'two_column',
                'TITLE_ONLY': 'title_only', 'BLANK': 'blank',
            }.get(name)
            if enum_match:
                layout_map[enum_match] = {'layoutId': layout['objectId'], 'placeholders': phs}
        return layout_map

    @staticmethod
    def add_designed_slide(presentation_id: str, spec: dict,
                           layout_map: dict = None, credentials=None) -> str:
        """Adds one slide from an outline-schema-v2 spec dict.

        Spec fields (all optional except one of title/quote/number):
        layout, title, subtitle, bullets (list) or body (\\n-joined string),
        columns ([{heading, bullets}] x2), quote+attribution, number+caption,
        image_url + image_placement, speaker_notes, background_color (#hex).

        Creation strategy: template layoutId when the semantic layout is mapped
        (placeholderIdMappings built ONLY from placeholders the resolver saw —
        mapping a nonexistent placeholder 400s the whole batch), else
        predefinedLayout, else BLANK + styled text boxes. Always returns a slide.
        """
        service = get_slides_service(credentials)
        layout_map = layout_map or {}
        slide_id = f"slide_{uuid.uuid4().hex[:12]}"

        layout = spec.get('layout') or 'content'
        if layout not in _PREDEFINED:
            layout = 'content'
        title = spec.get('title', '')
        subtitle = spec.get('subtitle', '')
        bullets = spec.get('bullets')
        if bullets is None and spec.get('body'):
            bullets = [b.strip() for b in str(spec['body']).split('\n') if b.strip()]
        bullets = bullets or []

        requests = []
        text_fills = []       # (objectId, text) into placeholders
        manual_boxes = []     # requests for BLANK-path text boxes

        # -- createSlide ----------------------------------------------------
        semantic_for_map = 'section' if layout == 'closing' else layout
        mapped = layout_map.get(semantic_for_map)
        if layout in ('quote', 'big_number'):
            mapped = layout_map.get('blank') or None  # composites build on blank/title_only
        mappings = []
        if mapped:
            available = {(p['type'], p['index']) for p in mapped['placeholders']}
            create = {'objectId': slide_id,
                      'slideLayoutReference': {'layoutId': mapped['layoutId']}}
            def _map_ph(ph_type, index, obj_suffix):
                if (ph_type, index) in available:
                    oid = f"{slide_id}_{obj_suffix}"
                    mappings.append({'layoutPlaceholder': {'type': ph_type, 'index': index},
                                     'objectId': oid})
                    return oid
                return None
            title_ph = 'CENTERED_TITLE' if ('CENTERED_TITLE', 0) in available else 'TITLE'
            tid = _map_ph(title_ph, 0, 'title')
            sid = _map_ph('SUBTITLE', 0, 'subtitle')
            b0 = _map_ph('BODY', 0, 'body0')
            b1 = _map_ph('BODY', 1, 'body1')
            if mappings:
                create['placeholderIdMappings'] = mappings
            requests.append({'createSlide': create})
            if tid and title:
                text_fills.append((tid, title))
            if sid and subtitle:
                text_fills.append((sid, subtitle))
            elif subtitle and not sid and layout in ('cover', 'section', 'closing') and b0:
                text_fills.append((b0, subtitle))
                b0 = None
            if layout == 'two_column' and spec.get('columns'):
                cols = spec['columns'][:2]
                for oid, col in zip([b0, b1], cols):
                    if oid and col:
                        heading = col.get('heading', '')
                        col_lines = ([heading] if heading else []) + list(col.get('bullets', []))
                        text_fills.append((oid, '\n'.join(col_lines)))
            elif b0 and bullets:
                text_fills.append((b0, '\n'.join(bullets)))
        else:
            requests.append({'createSlide': {
                'objectId': slide_id,
                'slideLayoutReference': {'predefinedLayout': _PREDEFINED[layout]},
                'placeholderIdMappings': (
                    [{'layoutPlaceholder': {'type': 'TITLE', 'index': 0},
                      'objectId': f'{slide_id}_title'}]
                    if layout not in ('quote', 'big_number') else []
                ) + (
                    [{'layoutPlaceholder': {'type': 'BODY', 'index': 0},
                      'objectId': f'{slide_id}_body0'}]
                    if layout in ('content',) else []
                ) + (
                    [{'layoutPlaceholder': {'type': 'BODY', 'index': 0},
                      'objectId': f'{slide_id}_body0'},
                     {'layoutPlaceholder': {'type': 'BODY', 'index': 1},
                      'objectId': f'{slide_id}_body1'}]
                    if layout == 'two_column' else []
                ) + (
                    [{'layoutPlaceholder': {'type': 'SUBTITLE', 'index': 0},
                      'objectId': f'{slide_id}_subtitle'}]
                    if layout == 'cover' else []
                ),
            }})
            if layout not in ('quote', 'big_number') and title:
                text_fills.append((f'{slide_id}_title', title))
            if layout == 'cover' and subtitle:
                text_fills.append((f'{slide_id}_subtitle', subtitle))
            if layout == 'content' and bullets:
                text_fills.append((f'{slide_id}_body0', '\n'.join(bullets)))
            if layout == 'two_column' and spec.get('columns'):
                for i, col in enumerate(spec['columns'][:2]):
                    heading = col.get('heading', '')
                    col_lines = ([heading] if heading else []) + list(col.get('bullets', []))
                    text_fills.append((f'{slide_id}_body{i}', '\n'.join(col_lines)))
            if layout in ('section', 'closing') and subtitle:
                # SECTION_HEADER has no body; put subtitle in a manual box
                manual_boxes.append((subtitle, 1_143_000, 3_000_000, 6_858_000, 900_000,
                                     {'fontSize': {'magnitude': 18, 'unit': 'PT'}},
                                     'fontSize', 'CENTER'))

        # -- image (before manual text boxes so text z-orders on top) --------
        image_url = spec.get('image_url')
        if image_url:
            x, y, w, h = _PLACEMENTS.get(spec.get('image_placement') or 'right_half',
                                         _PLACEMENTS['right_half'])
            requests.append({'createImage': {
                'objectId': f'img_{uuid.uuid4().hex[:12]}',
                'url': image_url,
                'elementProperties': {
                    'pageObjectId': slide_id,
                    'size': {'width': {'magnitude': w, 'unit': 'EMU'},
                             'height': {'magnitude': h, 'unit': 'EMU'}},
                    'transform': {'scaleX': 1, 'scaleY': 1,
                                  'translateX': x, 'translateY': y, 'unit': 'EMU'},
                },
            }})

        # -- composite layouts: quote / big_number ---------------------------
        if layout == 'quote':
            manual_boxes.append((f'“{spec.get("quote", title)}”',
                                 914_400, 1_543_050, 7_315_200, 2_057_400,
                                 {'italic': True, 'fontSize': {'magnitude': 28, 'unit': 'PT'}},
                                 'italic,fontSize', 'CENTER'))
            if spec.get('attribution'):
                manual_boxes.append((f'— {spec["attribution"]}',
                                     914_400, 3_700_000, 7_315_200, 600_000,
                                     {'fontSize': {'magnitude': 14, 'unit': 'PT'}},
                                     'fontSize', 'END'))
        elif layout == 'big_number':
            manual_boxes.append((spec.get('number', title),
                                 914_400, 1_200_000, 7_315_200, 1_600_000,
                                 {'bold': True, 'fontSize': {'magnitude': 96, 'unit': 'PT'}},
                                 'bold,fontSize', 'CENTER'))
            if spec.get('caption'):
                manual_boxes.append((spec['caption'],
                                     914_400, 3_100_000, 7_315_200, 900_000,
                                     {'fontSize': {'magnitude': 18, 'unit': 'PT'}},
                                     'fontSize', 'CENTER'))

        for text, x, y, w, h, style, fields, align in manual_boxes:
            box_id = f'box_{uuid.uuid4().hex[:10]}'
            requests.append({'createShape': {
                'objectId': box_id, 'shapeType': 'TEXT_BOX',
                'elementProperties': {
                    'pageObjectId': slide_id,
                    'size': {'width': {'magnitude': w, 'unit': 'EMU'},
                             'height': {'magnitude': h, 'unit': 'EMU'}},
                    'transform': {'scaleX': 1, 'scaleY': 1,
                                  'translateX': x, 'translateY': y, 'unit': 'EMU'},
                },
            }})
            requests.append({'insertText': {'objectId': box_id, 'insertionIndex': 0,
                                            'text': text}})
            requests.append({'updateTextStyle': {'objectId': box_id,
                                                 'textRange': {'type': 'ALL'},
                                                 'style': style, 'fields': fields}})
            requests.append({'updateParagraphStyle': {'objectId': box_id,
                                                      'textRange': {'type': 'ALL'},
                                                      'style': {'alignment': align},
                                                      'fields': 'alignment'}})

        # -- placeholder text fills ------------------------------------------
        for oid, text in text_fills:
            if text:
                requests.append({'insertText': {'objectId': oid, 'insertionIndex': 0,
                                                'text': text}})

        # -- optional solid background ---------------------------------------
        if spec.get('background_color'):
            try:
                rgb = _hex_to_rgb(spec['background_color'])
                requests.append({'updatePageProperties': {
                    'objectId': slide_id,
                    'pageProperties': {'pageBackgroundFill': {
                        'solidFill': {'color': {'rgbColor': rgb}}}},
                    'fields': 'pageBackgroundFill.solidFill.color',
                }})
            except Exception:
                pass  # a bad hex must not kill the slide

        try:
            service.presentations().batchUpdate(
                presentationId=presentation_id, body={'requests': requests}
            ).execute()
        except Exception as e:
            # An unreachable/invalid image URL fails the WHOLE batch — retry the
            # same slide without the createImage before degrading the layout.
            no_img = [r for r in requests if 'createImage' not in r]
            if len(no_img) < len(requests):
                try:
                    print(f"[slides] createImage failed on {layout}: {e} — retrying without image",
                          flush=True)
                    service.presentations().batchUpdate(
                        presentationId=presentation_id, body={'requests': no_img}
                    ).execute()
                    if spec.get('speaker_notes'):
                        SlidesService._add_speaker_notes(service, presentation_id, slide_id,
                                                         spec['speaker_notes'])
                    return slide_id
                except Exception as e2:
                    e = e2
            # Guaranteed-fallback path: BLANK slide + title/body text boxes.
            print(f"[slides] designed slide failed ({layout}): {e} — BLANK fallback", flush=True)
            slide_id = f"slide_{uuid.uuid4().hex[:12]}"
            fb = [{'createSlide': {'objectId': slide_id,
                                   'slideLayoutReference': {'predefinedLayout': 'BLANK'}}}]
            y = 457_200
            for text, size, bold in [(title, 28, True),
                                     ('\n'.join(bullets) or subtitle, 16, False)]:
                if not text:
                    continue
                box_id = f'box_{uuid.uuid4().hex[:10]}'
                fb += [
                    {'createShape': {'objectId': box_id, 'shapeType': 'TEXT_BOX',
                                     'elementProperties': {
                                         'pageObjectId': slide_id,
                                         'size': {'width': {'magnitude': 8_229_600, 'unit': 'EMU'},
                                                  'height': {'magnitude': 1_200_000, 'unit': 'EMU'}},
                                         'transform': {'scaleX': 1, 'scaleY': 1,
                                                       'translateX': 457_200, 'translateY': y,
                                                       'unit': 'EMU'}}}},
                    {'insertText': {'objectId': box_id, 'insertionIndex': 0, 'text': text}},
                    {'updateTextStyle': {'objectId': box_id, 'textRange': {'type': 'ALL'},
                                         'style': {'bold': bold,
                                                   'fontSize': {'magnitude': size, 'unit': 'PT'}},
                                         'fields': 'bold,fontSize'}},
                ]
                y += 1_400_000
            service.presentations().batchUpdate(
                presentationId=presentation_id, body={'requests': fb}
            ).execute()

        if spec.get('speaker_notes'):
            SlidesService._add_speaker_notes(service, presentation_id, slide_id,
                                             spec['speaker_notes'])
        return slide_id

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
        placement: str = None,
        credentials=None,
    ) -> str:
        """Inserts an image from a public URL into a slide. Returns the image objectId.

        `placement` (full_bleed | right_half | left_half | centered) overrides the
        four EMU args with a preset 16:9 footprint.
        """
        if placement and placement in _PLACEMENTS:
            left_emu, top_emu, width_emu, height_emu = _PLACEMENTS[placement]
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
