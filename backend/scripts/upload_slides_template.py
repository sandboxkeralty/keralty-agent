"""One-off: upload branding/Template_Keralty.pptx to Drive as a Google Slides
template, probe its layouts, and empirically test slide creation per layout.

Run locally from backend/ with the venv:
    GOOGLE_CLOUD_PROJECT=keraltysandbox python scripts/upload_slides_template.py

Uploads under the SANDBOX USER's OAuth creds (from Firestore) so the user owns
the template and per-deck files().copy needs no sharing. Prints the
SLIDES_TEMPLATE_ID to set on Cloud Run. Rerun with a new pptx (same steps)
whenever branding changes — then update the env var.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from googleapiclient.http import MediaFileUpload

from auth.google_oauth import credentials_from_dict
from services.firestore import FirestoreService
from services.drive import get_drive_service, DriveService
from services.slides import SlidesService, get_slides_service

USER = "sandboxkeralty@gmail.com"
PPTX = os.path.join(os.path.dirname(__file__), "..", "..", "branding", "Template_Keralty.pptx")
SEMANTICS = ["cover", "section", "content", "two_column", "title_only", "quote", "big_number", "closing"]

TEST_SPECS = {
    "cover": {"layout": "cover", "title": "Título de prueba", "subtitle": "Subtítulo"},
    "section": {"layout": "section", "title": "Sección de prueba"},
    "content": {"layout": "content", "title": "Contenido", "bullets": ["Uno", "Dos"]},
    "two_column": {"layout": "two_column", "title": "Dos columnas",
                    "columns": [{"heading": "A", "bullets": ["a1"]}, {"heading": "B", "bullets": ["b1"]}]},
    "title_only": {"layout": "title_only", "title": "Solo título"},
    "quote": {"layout": "quote", "quote": "La salud es lo primero", "attribution": "Keralty"},
    "big_number": {"layout": "big_number", "number": "87%", "caption": "satisfacción"},
    "closing": {"layout": "closing", "title": "Gracias", "subtitle": "keralty.com"},
}


def main():
    creds = credentials_from_dict(FirestoreService.get_user_credentials(USER))
    drive = get_drive_service(creds)

    print(f"Uploading {os.path.abspath(PPTX)} with conversion…")
    media = MediaFileUpload(
        PPTX,
        mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        resumable=True,
    )
    file = drive.files().create(
        body={"name": "Keralty Slides Template",
              "mimeType": "application/vnd.google-apps.presentation"},
        media_body=media, fields="id",
    ).execute()
    tid = file["id"]
    print(f"Template converted: https://docs.google.com/presentation/d/{tid}/edit")

    try:
        drive.permissions().create(fileId=tid, body={"type": "anyone", "role": "reader"}).execute()
        print("Shared anyone/reader (future multi-user copies).")
    except Exception as e:
        print(f"WARN: anyone-share failed ({e}) — single-user copies still work.")

    print("\n=== LAYOUT PROBE ===")
    layout_map = SlidesService.resolve_layouts(tid, credentials=creds)
    slides_svc = get_slides_service(creds)
    pres = slides_svc.presentations().get(
        presentationId=tid,
        fields="layouts(objectId,layoutProperties(name,displayName),"
               "pageElements(shape(placeholder(type,index))))",
    ).execute()
    for lay in pres.get("layouts", []):
        phs = [f"{el['shape']['placeholder']['type']}[{el['shape']['placeholder'].get('index',0)}]"
               for el in lay.get("pageElements", [])
               if el.get("shape", {}).get("placeholder", {}).get("type")]
        lp = lay.get("layoutProperties", {})
        print(f"  {lay['objectId']:<12} name={lp.get('name',''):<22} "
              f"display={lp.get('displayName',''):<28} placeholders={phs}")
    print("\nResolved semantic map:")
    for s in SEMANTICS:
        key = "section" if s == "closing" else s
        m = layout_map.get(key)
        print(f"  {s:<11} -> {m['layoutId'] if m else 'UNMAPPED (predefined/BLANK fallback)'}")

    print("\n=== EMPIRICAL PER-LAYOUT TEST (scratch copy) ===")
    scratch = DriveService.copy_file(tid, "scratch-layout-test", creds)
    pres = slides_svc.presentations().get(presentationId=scratch, fields="slides(objectId)").execute()
    reqs = [{"deleteObject": {"objectId": s["objectId"]}} for s in pres.get("slides", [])]
    if reqs:
        slides_svc.presentations().batchUpdate(presentationId=scratch, body={"requests": reqs}).execute()
    scratch_map = SlidesService.resolve_layouts(scratch, credentials=creds)
    for s in SEMANTICS:
        try:
            SlidesService.add_designed_slide(scratch, TEST_SPECS[s], scratch_map, credentials=creds)
            print(f"  {s:<11} PASS")
        except Exception as e:
            print(f"  {s:<11} FAIL — {e}")
    drive.files().delete(fileId=scratch).execute()
    print("Scratch copy deleted.")

    print(f"\nSLIDES_TEMPLATE_ID={tid}")
    print("Set it on Cloud Run:\n  gcloud run services update keralty-agent-backend "
          f"--update-env-vars SLIDES_TEMPLATE_ID={tid} "
          "--region us-central1 --project keraltysandbox --quiet")


if __name__ == "__main__":
    main()
