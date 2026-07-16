"""One-off: host the authorized Keralty logos publicly on GCS.

Uploads the 6 usable colorway/orientation PNGs from branding/logos_keralty/ to
gs://{GCS_BUCKET}/logos/ and makes each public (the bucket deliberately has
uniform bucket-level access DISABLED so per-object ACLs work — same pattern as
images/ and signatures/). Grises/Negro colorways are not hosted: the brand
manual only permits white or corporate-blue backgrounds, which the Blanco and
Azul/Color variants cover.

Public URLs are what Slides createImage / Docs insertInlineImage / Gmail <img>
need. Prints the URL map to paste into services/brand.py::LOGO_URLS.

Run from backend/: python scripts/upload_brand_logos.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.cloud import storage

from config import settings

_LOGOS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "branding", "logos_keralty",
)

# (colorway, orientation) -> source filename
_SELECTION = {
    ("azul", "horizontal"): "Keralty Azul Horizontal.png",
    ("azul", "vertical"): "Keralty Azul Vertical.png",
    ("blanco", "horizontal"): "Keralty Blanco Horizontal.png",
    ("blanco", "vertical"): "Keralty Blanco Vertical.png",
    ("color", "horizontal"): "Keralty Color Horizontal.png",
    ("color", "vertical"): "Keralty Color Vertical.png",
}


def main() -> None:
    client = storage.Client(project=settings.GOOGLE_CLOUD_PROJECT)
    bucket = client.bucket(settings.GCS_BUCKET)
    urls = {}
    for (colorway, orientation), filename in _SELECTION.items():
        path = os.path.join(_LOGOS_DIR, filename)
        blob = bucket.blob(f"logos/keralty-{colorway}-{orientation}.png")
        blob.upload_from_filename(path, content_type="image/png")
        blob.make_public()
        urls[(colorway, orientation)] = blob.public_url
        print(f"uploaded {filename} -> {blob.public_url}")

    print("\nLOGO_URLS = {")
    for key, url in urls.items():
        print(f"    {key!r}: \"{url}\",")
    print("}")


if __name__ == "__main__":
    main()
