"""Keralty brand system — single source of truth.

Distilled from `branding/Manual Keralty (020518).pdf` (v03, 2018) and the
official palette xlsx. Every artifact-generating surface imports from here:
services/slides.py (colors, engine font, logos), tools/image_tools.py (image
art direction), services/email/digest_service.py (email HTML), and the
Visual/Writing/Editing agent instructions (BRAND_INSTRUCTION_BLOCK).

Font reality: the corporate typeface is FF Clan Pro (branding/fonts_keralty/),
but the Google Slides/Docs APIs can only use fonts from Google's catalog —
Clan Pro CANNOT render in generated artifacts. ENGINE_FONT is the approved
Google-font stand-in used by the engines; Clan Pro remains the documented
corporate font for humans editing/exporting offline.
"""

from typing import Dict, Tuple

from config import settings

# ---------------------------------------------------------------------------
# Palette (brand manual §3.6 — Pantone → HEX)

PRIMARY_BLUE = "#002F87"    # 287C — logo, headlines (the manual's primary; NOT the old #002060)
DARK_BLUE = "#002E58"       # 288C — dark backgrounds / photo tints
SECONDARY_BLUE = "#0071A3"  # 307C — secondary headlines
GRADIENT_BLUES = ["#00B4E3", "#3E8EDE", "#0071CE"]              # 306C / 279C / 285C
GREENS = ["#00B288", "#49C3B1", "#8CC63F", "#4E9D2D"]           # 339C / 3258C / 376C / 362C
WARM_GREY = "#DCD5CB"       # 400C
WHITE = "#FFFFFF"

CORPORATE_FONT = "Clan Pro"                 # documentation only — see module docstring
ENGINE_FONT = settings.BRAND_ENGINE_FONT    # Google-font stand-in (probed empirically)

TAGLINE = "Sabemos de Salud"


def slides_rgb(hex_color: str) -> Dict[str, float]:
    """#RRGGBB → Slides API rgbColor dict."""
    h = hex_color.lstrip("#")
    return {
        "red": int(h[0:2], 16) / 255.0,
        "green": int(h[2:4], 16) / 255.0,
        "blue": int(h[4:6], 16) / 255.0,
    }


# ---------------------------------------------------------------------------
# Authorized logos (uploaded by scripts/upload_brand_logos.py to GCS logos/,
# public — Slides createImage / Docs insertInlineImage / Gmail <img> need
# public URLs). All source PNGs are 1250×704. Grises/Negro are deliberately
# not hosted: the manual only allows white or corporate-blue backgrounds.

LOGO_ASPECT = 1250 / 704  # width / height of every authorized PNG

_LOGOS_BASE = f"https://storage.googleapis.com/{settings.GCS_BUCKET}/logos"

LOGO_URLS: Dict[Tuple[str, str], str] = {
    (colorway, orientation): f"{_LOGOS_BASE}/keralty-{colorway}-{orientation}.png"
    for colorway in ("azul", "blanco", "color")
    for orientation in ("horizontal", "vertical")
}


def logo_for_background(background: str, orientation: str = "horizontal") -> str:
    """Manual §3.9/3.10: white (Blanco) logo on corporate blue / dark photo
    backgrounds; blue (Azul) logo on white. Never any other treatment."""
    colorway = "blanco" if background in ("dark", "navy", "blue", "photo") else "azul"
    return LOGO_URLS[(colorway, orientation)]


# ---------------------------------------------------------------------------
# Prompt blocks. IMPORTANT: no bare {tokens} — ADK interpolates {key} in agent
# instructions and an unknown token kills every turn (CLAUDE.md brace trap).

BRAND_INSTRUCTION_BLOCK = (
    "# MARCA KERALTY (manual de marca — obligatorio en todo artefacto)\n"
    "- Paleta: azul corporativo primario #002F87 (titulares y elementos principales), "
    "azul oscuro #002E58 (fondos), azul secundario #0071A3, verdes de marca #00B288 y "
    "#4E9D2D (acentos), gris cálido #DCD5CB. Fondos: solo blanco o azul corporativo.\n"
    "- La palabra Keralty en texto corrido va SIEMPRE con inicial mayúscula y en "
    "negrita: **Keralty**. NUNCA insertes ni describas el logo dentro del texto.\n"
    "- El logo solo lo colocan las herramientas (imágenes autorizadas, nunca "
    "generado, recoloreado, estirado ni rotado).\n"
    "- Tipografía corporativa: Clan Pro (los documentos generados usan la fuente "
    "sustituta configurada; menciona Clan Pro solo si el usuario pregunta por la "
    "tipografía oficial).\n"
    "- Tono de marca: sencillo, fresco, decidido, elegante y eficaz. Optimista y "
    "humano, nunca recargado. Tagline oficial: \"Sabemos de Salud\".\n"
)

# Always appended to image-prompt enrichment (tools/image_tools.py::_enrich_prompt).
# When the image-gen-pro skill (backend/skills/) is present it provides the primary
# prompting craft and this directive rides along as the brand color/mood layer; with
# no skill loaded this is the sole art-direction fallback.
IMAGE_STYLE_DIRECTIVE = (
    "Color mood: Keralty corporate palette — deep corporate blue #002F87, dark blue "
    "#002E58, sky-blue gradient accents (#00B4E3, #3E8EDE, #0071CE), wellbeing greens "
    "(#00B288, #4E9D2D), warm grey #DCD5CB and generous white space. Photography "
    "premises (brand manual): natural, optimistic, everyday human moments, clean and "
    "uncluttered composition, soft natural light — never dark, cluttered or artificial."
)

EMAIL_FONT_STACK = "Arial,Helvetica,sans-serif"  # web-safe; Clan Pro is print/desktop only
