"""One-off: re-theme the three corporate PPTX templates with the Keralty palette.

All three templates ship with the STOCK Office theme (Arial + Office accent
colors) — their branding lives only in designed slide content, so a Google
Slides copy inherits Arial/Office defaults for any API-inserted text. This
script rewrites every ppt/theme/theme*.xml (plain zip surgery — no external
deps) so re-provisioned templates hand brand colors + the engine font to
generated content.

Originals are untouched; output goes to branding/generated/. Run from backend/:
    python scripts/retheme_templates.py
Then provision with scripts/upload_slides_template.py.
"""

import os
import re
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_BRANDING = os.path.join(_ROOT, "branding")
_OUT = os.path.join(_BRANDING, "generated")

_TEMPLATES = [
    "Template_Keralty.pptx",
    "Template_Presidencia__Corporativo.pptx",
    "Template_Presidencia__Estandar.pptx",
]

# Keralty palette mapped onto the Office color-scheme slots (brand manual §3.6).
# lt1/dk1 stay white/black (text/background base).
_CLR_SCHEME = {
    "dk2": "002E58",      # 288C dark blue
    "lt2": "DCD5CB",      # 400C warm grey
    "accent1": "002F87",  # 287C primary corporate blue
    "accent2": "0071A3",  # 307C secondary blue
    "accent3": "00B288",  # 339C green
    "accent4": "3E8EDE",  # 279C gradient blue
    "accent5": "8CC63F",  # 376C green
    "accent6": "4E9D2D",  # 362C green
    "hlink": "0071CE",    # 285C
    "folHlink": "0071A3",
}


def _retheme_xml(xml: str, font: str) -> str:
    for slot, hexval in _CLR_SCHEME.items():
        xml = re.sub(
            rf'(<a:{slot}>)<a:srgbClr val="[0-9A-Fa-f]{{6}}"/>(</a:{slot}>)',
            rf'\g<1><a:srgbClr val="{hexval}"/>\g<2>',
            xml,
        )
    # majorFont + minorFont latin typeface → engine font (Clan Pro can't render
    # in Google Slides; `font` is the approved Google-catalog stand-in).
    xml = re.sub(r'(<a:latin typeface=")[^"]*(")', rf'\g<1>{font}\g<2>', xml)
    return xml


def _retheme_pptx(src: str, dst: str, font: str) -> None:
    shutil.copyfile(src, dst)
    with zipfile.ZipFile(src) as zin:
        entries = zin.namelist()
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
            for name in entries:
                data = zin.read(name)
                if re.match(r"ppt/theme/theme\d+\.xml$", name):
                    data = _retheme_xml(data.decode("utf-8"), font).encode("utf-8")
                zout.writestr(name, data)


def main() -> None:
    font = settings.BRAND_ENGINE_FONT
    os.makedirs(_OUT, exist_ok=True)
    for filename in _TEMPLATES:
        src = os.path.join(_BRANDING, filename)
        dst = os.path.join(_OUT, filename)
        _retheme_pptx(src, dst, font)
        # Sanity: confirm the rewrite actually landed.
        with zipfile.ZipFile(dst) as z:
            xml = z.read("ppt/theme/theme1.xml").decode("utf-8")
            assert f'typeface="{font}"' in xml, f"font not applied in {filename}"
            assert 'val="002F87"' in xml, f"palette not applied in {filename}"
        print(f"re-themed {filename} -> {dst} (font={font})")


if __name__ == "__main__":
    main()
