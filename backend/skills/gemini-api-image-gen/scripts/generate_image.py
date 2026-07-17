#!/usr/bin/env python3
"""
generate_image.py — CLI para generar/editar imágenes con la API de Gemini (Nano Banana).

Requisitos:
    pip install google-genai pillow
    export GEMINI_API_KEY="..."

Ejemplos:
    # Texto a imagen (modelo por defecto: gemini-3.1-flash-image-preview)
    python generate_image.py "Fotografía de producto de una taza negra mate..." -o taza.png

    # Con ratio y resolución
    python generate_image.py "Portada de revista..." --ratio 2:3 --size 2K -o portada.png

    # Edición con imágenes de entrada (hasta 14 en Gemini 3.x)
    python generate_image.py "Ponle este logo a la camiseta..." -i persona.png -i logo.png -o out.png

    # Grounding con Google Search (datos en tiempo real)
    python generate_image.py "Gráfico del clima de 5 días en Bogotá" --search --ratio 16:9 -o clima.png

    # Modelo Pro y thinking alto
    python generate_image.py "Infografía compleja..." -m gemini-3-pro-image-preview -o info.png
    python generate_image.py "Ciudad futurista..." --thinking high -o ciudad.png
"""
import argparse
import os
import sys

RATIOS = ["1:1", "1:4", "1:8", "2:3", "3:2", "3:4", "4:1", "4:3", "4:5",
          "5:4", "8:1", "9:16", "16:9", "21:9"]
SIZES = ["512", "1K", "2K", "4K"]  # "K" mayúscula obligatoria
MODELS = ["gemini-3.1-flash-image-preview", "gemini-3-pro-image-preview",
          "gemini-2.5-flash-image"]


def main() -> int:
    p = argparse.ArgumentParser(description="Genera imágenes con la API de Gemini (Nano Banana).")
    p.add_argument("prompt", help="Instrucción descriptiva (narra la escena, no keywords).")
    p.add_argument("-o", "--output", default="generated_image.png", help="Archivo PNG de salida.")
    p.add_argument("-m", "--model", default="gemini-3.1-flash-image-preview", choices=MODELS)
    p.add_argument("-i", "--input-image", action="append", default=[],
                   help="Imagen de entrada para edición/composición (repetible, hasta 14).")
    p.add_argument("--ratio", choices=RATIOS, help="Aspect ratio (default: 1:1 o el de la entrada).")
    p.add_argument("--size", choices=SIZES, help="Resolución (solo Gemini 3.x). '512' solo 3.1 Flash.")
    p.add_argument("--search", action="store_true", help="Activar grounding con Google Search.")
    p.add_argument("--image-search", action="store_true",
                   help="Activar Búsqueda de imágenes (solo 3.1 Flash; no para personas).")
    p.add_argument("--thinking", choices=["minimal", "high"],
                   help="Nivel de razonamiento (solo 3.1 Flash).")
    p.add_argument("--image-only", action="store_true", help="Responder solo imagen, sin texto.")
    args = p.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: define la variable de entorno GEMINI_API_KEY.", file=sys.stderr)
        return 1

    from google import genai
    from google.genai import types
    from PIL import Image

    client = genai.Client()

    contents = [args.prompt]
    for path in args.input_image:
        contents.append(Image.open(path))

    cfg = {"response_modalities": ["IMAGE"] if args.image_only else ["TEXT", "IMAGE"]}

    image_cfg = {}
    if args.ratio:
        image_cfg["aspect_ratio"] = args.ratio
    if args.size:
        image_cfg["image_size"] = args.size
    if image_cfg:
        cfg["response_format"] = {"image": image_cfg}

    tools = []
    if args.search or args.image_search:
        if args.image_search:
            tools.append(types.Tool(google_search=types.GoogleSearch(
                search_types=types.SearchTypes(
                    web_search=types.WebSearch(),
                    image_search=types.ImageSearch(),
                ))))
        else:
            tools.append({"google_search": {}})
    if tools:
        cfg["tools"] = tools

    if args.thinking:
        cfg["thinking_config"] = types.ThinkingConfig(
            thinking_level="High" if args.thinking == "high" else "minimal")

    response = client.models.generate_content(
        model=args.model, contents=contents,
        config=types.GenerateContentConfig(**cfg))

    saved = 0
    base, ext = os.path.splitext(args.output)
    for part in response.parts:
        if getattr(part, "thought", False):
            continue  # omitir imágenes/textos provisionales del razonamiento
        if part.text:
            print(part.text)
        elif part.inline_data is not None:
            out = args.output if saved == 0 else f"{base}_{saved}{ext}"
            part.as_image().save(out)
            print(f"Imagen guardada: {out}")
            saved += 1

    # Atribución de grounding (requisito de despliegue)
    try:
        gm = response.candidates[0].grounding_metadata
        if gm and gm.grounding_chunks:
            print("\nFuentes (grounding):")
            for ch in gm.grounding_chunks:
                web = getattr(ch, "web", None)
                if web:
                    print(f"  - {web.title}: {web.uri}")
    except (AttributeError, IndexError):
        pass

    if saved == 0:
        print("ADVERTENCIA: la respuesta no incluyó imágenes.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
