# Referencia técnica — API de Gemini para generación de imágenes

Endpoint REST: `POST https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent`
Header: `x-goog-api-key: $GEMINI_API_KEY`
SDKs oficiales: `google-genai` (Python), `@google/genai` (JavaScript), `google.golang.org/genai` (Go), Java.

Modelos: `gemini-3.1-flash-image-preview` (default recomendado), `gemini-3-pro-image-preview`,
`gemini-2.5-flash-image`.

## Índice
1. Texto a imagen
2. Edición (imagen + texto → imagen)
3. Edición multi-turno (chat)
4. Múltiples imágenes de referencia (hasta 14)
5. Grounding con Google Search / Búsqueda de imágenes
6. Resolución hasta 4K y aspect ratios (tablas)
7. Thinking (proceso de pensamiento) y firmas
8. Modalidades de respuesta
9. Batch API
10. Manejo de la respuesta

---

## 1. Texto a imagen

### Python
```python
from google import genai
from google.genai import types

client = genai.Client()  # usa GEMINI_API_KEY del entorno

response = client.models.generate_content(
    model="gemini-3.1-flash-image-preview",
    contents=["Create a picture of a nano banana dish in a fancy restaurant"],
)
for part in response.parts:
    if part.text is not None:
        print(part.text)
    elif part.inline_data is not None:
        part.as_image().save("generated_image.png")
```

### JavaScript
```javascript
import { GoogleGenAI } from "@google/genai";
import * as fs from "node:fs";

const ai = new GoogleGenAI({});
const response = await ai.models.generateContent({
  model: "gemini-3.1-flash-image-preview",
  contents: "Create a picture of ...",
});
for (const part of response.candidates[0].content.parts) {
  if (part.text) console.log(part.text);
  else if (part.inlineData) {
    fs.writeFileSync("image.png", Buffer.from(part.inlineData.data, "base64"));
  }
}
```

### REST
```bash
curl -s -X POST \
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent" \
  -H "x-goog-api-key: $GEMINI_API_KEY" -H "Content-Type: application/json" \
  -d '{"contents":[{"parts":[{"text":"Create a picture of ..."}]}]}'
```

## 2. Edición (imagen + texto → imagen)

Adjunta la(s) imagen(es) como parte del contenido. En Python con PIL:

```python
from PIL import Image
image = Image.open("/path/to/cat_image.png")
response = client.models.generate_content(
    model="gemini-3.1-flash-image-preview",
    contents=["Add a small knitted wizard hat to my cat...", image],
)
```

En JS/REST, la imagen va como `inlineData`/`inline_data` con `mimeType` y `data` en base64:
```json
{"inline_data": {"mime_type": "image/png", "data": "<BASE64>"}}
```
Recordatorio: verificar derechos de las imágenes subidas.

## 3. Edición multi-turno (chat) — recomendado para iterar

```python
chat = client.chats.create(
    model="gemini-3.1-flash-image-preview",
    config=types.GenerateContentConfig(
        response_modalities=['TEXT', 'IMAGE'],
        tools=[{"google_search": {}}],   # opcional
    ),
)
r1 = chat.send_message("Create a vibrant infographic that explains photosynthesis ...")
# turno 2: editar manteniendo el resto
r2 = chat.send_message(
    "Update this infographic to be in Spanish. Do not change any other elements of the image.",
    config=types.GenerateContentConfig(
        response_format={"image": {"aspect_ratio": "16:9", "image_size": "2K"}},
    ),
)
```
En REST multi-turno, envía el historial completo incluyendo la imagen previa como parte `model`.
El chat de los SDK maneja automáticamente las firmas de pensamiento (§7).

## 4. Múltiples imágenes de referencia (hasta 14)

| | 3.1 Flash Image | 3 Pro Image |
|---|---|---|
| Objetos de alta fidelidad | hasta 10 | hasta 6 |
| Imágenes de personajes (consistencia) | hasta 4 | hasta 5 |

```python
response = client.models.generate_content(
    model="gemini-3.1-flash-image-preview",
    contents=[
        "An office group photo of these people, they are making funny faces.",
        Image.open('person1.png'), Image.open('person2.png'),
        Image.open('person3.png'), Image.open('person4.png'), Image.open('person5.png'),
    ],
    config=types.GenerateContentConfig(
        response_modalities=['TEXT', 'IMAGE'],
        response_format={"image": {"aspect_ratio": "5:4", "image_size": "2K"}},
    ),
)
```

## 5. Grounding con Google Search

Herramienta `google_search` para datos en tiempo real (clima, deportes, noticias):
```python
config=types.GenerateContentConfig(
    response_modalities=['TEXT', 'IMAGE'],
    response_format={"image": {"aspect_ratio": "16:9"}},
    tools=[{"google_search": {}}],
)
```
La respuesta incluye `groundingMetadata` con:
- `searchEntryPoint`: HTML/CSS del chip de Búsqueda (debe renderizarse — requisito).
- `groundingChunks`: top 3 fuentes web usadas.

### Búsqueda de imágenes (solo `gemini-3.1-flash-image-preview`)
Usa imágenes web como contexto visual. No puede usarse para buscar personas.
```python
tools=[types.Tool(google_search=types.GoogleSearch(
    search_types=types.SearchTypes(
        web_search=types.WebSearch(),
        image_search=types.ImageSearch(),
    )
))]
```
REST: `"tools":[{"google_search":{"searchTypes":{"webSearch":{},"imageSearch":{}}}}]`

Metadatos adicionales: `imageSearchQueries`, `groundingChunks` con `uri` (página fuente para
atribución) e `image_uri` (URL directa de la imagen), `groundingSupports`.
Requisitos de despliegue: enlace de atribución a la página contenedora; si muestras las imágenes
fuente, navegación de 1 clic directa a la página de origen (sin visores intermedios).

## 6. Resolución y aspect ratios

Config (Gemini 3.x): `response_format={"image": {"aspect_ratio": "16:9", "image_size": "2K"}}`
(en REST/JS: `responseFormat.image.aspectRatio` / `imageSize`; en Go/Java: `ImageConfig`).
Gemini 2.5 Flash Image solo acepta `aspect_ratio` (salida 1024 px).

- Valores de `image_size`: `"512"` (solo 3.1 Flash, sin sufijo K), `"1K"` (default), `"2K"`, `"4K"`.
  **"K" mayúscula obligatoria** — `1k` en minúscula se rechaza.
- Por defecto, el modelo iguala el tamaño de la imagen de entrada, o genera 1:1 si no hay entrada.

### Ratios disponibles
- 2.5 Flash y 3 Pro: 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9
- 3.1 Flash agrega: 1:4, 4:1, 1:8, 8:1 (banners extremos)

### Tabla — Gemini 3.1 Flash Image (resolución px | tokens: 512→747, 1K→1120, 2K→1680, 4K→2520)
| Ratio | 512 | 1K | 2K | 4K |
|---|---|---|---|---|
| 1:1 | 512x512 | 1024x1024 | 2048x2048 | 4096x4096 |
| 1:4 | 256x1024 | 512x2048 | 1024x4096 | 2048x8192 |
| 1:8 | 192x1536 | 384x3072 | 768x6144 | 1536x12288 |
| 2:3 | 424x632 | 848x1264 | 1696x2528 | 3392x5056 |
| 3:2 | 632x424 | 1264x848 | 2528x1696 | 5056x3392 |
| 3:4 | 448x600 | 896x1200 | 1792x2400 | 3584x4800 |
| 4:1 | 1024x256 | 2048x512 | 4096x1024 | 8192x2048 |
| 4:3 | 600x448 | 1200x896 | 2400x1792 | 4800x3584 |
| 4:5 | 464x576 | 928x1152 | 1856x2304 | 3712x4608 |
| 5:4 | 576x464 | 1152x928 | 2304x1856 | 4608x3712 |
| 8:1 | 1536x192 | 3072x384 | 6144x768 | 12288x1536 |
| 9:16 | 384x688 | 768x1376 | 1536x2752 | 3072x5504 |
| 16:9 | 688x384 | 1376x768 | 2752x1536 | 5504x3072 |
| 21:9 | 792x168 | 1584x672 | 3168x1344 | 6336x2688 |

### Tabla — Gemini 3 Pro Image (tokens: 1K→1120, 2K→1120, 4K→2000)
Ratios 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9 con las mismas resoluciones px que
la tabla anterior en 1K/2K/4K.

### Tabla — Gemini 2.5 Flash Image (1290 tokens por imagen)
| Ratio | Resolución |
|---|---|
| 1:1 | 1024x1024 |
| 2:3 | 832x1248 |
| 3:2 | 1248x832 |
| 3:4 | 864x1184 |
| 4:3 | 1184x864 |
| 4:5 | 896x1152 |
| 5:4 | 1152x896 |
| 9:16 | 768x1344 |
| 16:9 | 1344x768 |
| 21:9 | 1536x672 |

## 7. Thinking (proceso de pensamiento)

- Los modelos Gemini 3 de imagen razonan por defecto; **no se puede desactivar**.
- Generan hasta 2 imágenes provisionales de composición (visibles como `part.thought`, no se cobran
  como imágenes finales; los **tokens de pensamiento sí se facturan siempre**).
- En 3.1 Flash Image se controla con `thinkingConfig`:
```python
config=types.GenerateContentConfig(
    response_modalities=["IMAGE"],
    thinking_config=types.ThinkingConfig(
        thinking_level="High",   # "minimal" (default, menor latencia) | "High" (mayor calidad)
        include_thoughts=True,   # devolver o no los pensamientos en la respuesta
    ),
)
```
- Inspeccionar pensamientos: iterar `response.parts` y filtrar `part.thought`.

### Firmas de pensamiento (`thought_signature`)
Preservan el contexto de razonamiento en multi-turno. Regla: si recibes una firma, devuélvela
**exactamente igual** al reenviar el historial; si no, la respuesta puede fallar.
- Toda parte `inline_data` de imagen que sea respuesta final lleva firma.
- La primera parte de texto tras los pensamientos también lleva firma.
- Las imágenes que son pensamientos (`thought: true`) NO llevan firma.
- **Los SDK oficiales con chat (o al reinsertar el objeto de respuesta completo al historial) las
  gestionan automáticamente.**

## 8. Modalidades de respuesta

Default: `response_modalities=['TEXT', 'IMAGE']` (texto + imagen intercalados).
Solo imagen: `response_modalities=['IMAGE']`.
Modos soportados: texto→imagen, texto→imagen+texto intercalado (ej. receta ilustrada),
imagen+texto→imagen+texto (ej. "¿qué otros colores de sofá funcionarían? Actualiza la imagen").

## 9. Batch API

Para generación masiva: límites de frecuencia más altos a cambio de respuesta de hasta 24 h.
Ver documentación de Batch API de Gemini (`/gemini-api/docs/batch-api#image-generation`).

## 10. Manejo de la respuesta

- Las imágenes llegan como partes `inline_data` (base64) con `mime_type` de imagen.
- Python: `part.as_image()` devuelve un objeto PIL. JS: decodificar base64 a Buffer.
- Puede haber varias partes de texto e imagen intercaladas — procesa todas.
- Todas las imágenes llevan marca de agua SynthID.
- Errores comunes: `image_size` en minúscula ("1k") → rechazado; ratio no soportado por el
  modelo elegido; omitir firmas de pensamiento en multi-turno manual.
