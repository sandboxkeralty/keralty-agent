---
name: gemini-api-image-gen
description: >
  Genera y edita imágenes profesionales usando la API de Gemini (Nano Banana / Nano Banana Pro / Nano Banana 2)
  de acuerdo a la intención del usuario. Usa este skill SIEMPRE que el usuario pida crear, generar, editar,
  transformar, combinar o mejorar imágenes de cualquier tipo: fotos realistas, fotografía de producto,
  logotipos, íconos, calcomanías, infografías, mockups, portadas, banners, cómics, storyboards,
  transferencia de estilo, try-on virtual, restauración de bocetos, o imágenes fundamentadas en datos
  en tiempo real (clima, noticias, deportes). Aplica ante frases como "genera una imagen de…",
  "crea una foto de…", "edita esta imagen…", "haz un logo…", "image generation", "nano banana",
  o cualquier variante, aunque no mencionen "Gemini" explícitamente. Cubre selección de modelo,
  técnicas de prompting profesional, configuración (aspect ratio, resolución hasta 4K, thinking,
  grounding con Google Search) y código listo para usar en Python, JavaScript y REST.
compatibility: Requiere una clave GEMINI_API_KEY y acceso de red a generativelanguage.googleapis.com (o al SDK google-genai / @google/genai).
version: 1
tools: [image_generate]
providers: [google, anthropic]
tool_references: [prompting-guide.md]
---

# Generación de imágenes profesionales con la API de Gemini (Nano Banana)

Skill agnóstico de agente para generar y editar imágenes de calidad profesional con los modelos de imagen
nativos de Gemini. "Nano Banana" es el nombre de estas capacidades y cubre tres modelos.

## Flujo de trabajo (síguelo en orden)

1. **Interpreta la intención del usuario** → clasifícala en uno de los casos de uso de
   `references/prompting-guide.md` (fotorrealismo, producto, logo/texto, ilustración, edición,
   composición multi-imagen, grounding, etc.).
2. **Selecciona el modelo** con la tabla de abajo.
3. **Construye el prompt** aplicando el principio central y las plantillas del caso de uso
   (lee `references/prompting-guide.md` — es obligatorio antes de escribir el prompt).
4. **Configura la salida**: aspect ratio, resolución, modalidades, thinking, herramientas.
   Detalles y tablas completas en `references/api-reference.md`.
5. **Llama a la API** (usa `scripts/generate_image.py` como base en entornos Python, o los
   snippets de `references/api-reference.md` para JS/REST).
6. **Itera conversacionalmente**: los modelos están diseñados para refinamiento multi-turno.
   No esperes perfección al primer intento; pide cambios pequeños y específicos.

## Selección de modelo

| Modelo | ID | Cuándo usarlo |
|---|---|---|
| **Nano Banana 2** (Gemini 3.1 Flash Image Preview) | `gemini-3.1-flash-image-preview` | **Opción por defecto.** Mejor balance inteligencia/costo/latencia. Alta eficiencia y gran volumen. Soporta 512/1K/2K/4K, ratios extremos (1:4, 4:1, 1:8, 8:1), Búsqueda de imágenes de Google, thinking configurable, hasta 10 objetos de alta fidelidad + 4 personajes. |
| **Nano Banana Pro** (Gemini 3 Pro Image Preview) | `gemini-3-pro-image-preview` | Producción de recursos profesionales e instrucciones complejas: texto de alta fidelidad en imágenes, razonamiento avanzado, hasta 5 personajes consistentes + 6 objetos, 1K–4K, grounding con Google Search. |
| **Nano Banana** (Gemini 2.5 Flash Image) | `gemini-2.5-flash-image` | Velocidad y eficiencia máximas, tareas de gran volumen y baja latencia. Salida 1024 px. Mejor con ≤3 imágenes de entrada. |
| **Imagen 4 / Imagen 4 Ultra** | vía API de Imagen | Alternativa especializada cuando se necesita la máxima calidad fotográfica pura (Ultra genera 1 imagen a la vez). |

## Principio central de prompting

> **Describe la escena, no enumeres palabras clave.** Un párrafo narrativo y descriptivo casi
> siempre produce una imagen mejor y más coherente que una lista de palabras desconectadas.
> La fortaleza principal del modelo es su comprensión profunda del lenguaje.

Buenas prácticas resumidas (el detalle está en `references/prompting-guide.md`):
- Sé hiperespecífico en detalles de materiales, luz, cámara y composición.
- Explica el **propósito** de la imagen ("logo para marca de skincare minimalista de alta gama").
- Itera con cambios pequeños en la misma conversación/chat.
- Para escenas complejas, da instrucciones paso a paso (fondo → medio → primer plano).
- Usa negativos semánticos: en vez de "sin autos", describe "una calle vacía y desierta".
- Controla la cámara con lenguaje fotográfico/cinematográfico: wide-angle, macro, low-angle, 85mm, bokeh.
- Para texto en imágenes: especifica el texto exacto entre comillas, describe la fuente y el layout.
  Si el texto es largo, genera primero el texto y luego pide la imagen que lo contiene.

## Capacidades clave (Gemini 3.x)

- **Texto a imagen** y **edición imagen+texto → imagen** (agregar/quitar elementos, máscara semántica, transferencia de estilo).
- **Edición multi-turno conversacional** (recomendado usar el modo chat del SDK).
- **Hasta 14 imágenes de referencia** combinadas (objetos de alta fidelidad + consistencia de personajes).
- **Resoluciones**: 512 (solo 3.1 Flash), 1K (default), 2K, 4K. Usar "K" mayúscula.
- **Aspect ratios**: 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9 (+1:4, 4:1, 1:8, 8:1 en 3.1 Flash).
- **Grounding con Google Search**: imágenes basadas en datos en tiempo real (clima, resultados deportivos, noticias). Incluye `groundingMetadata` con atribución obligatoria.
- **Búsqueda de imágenes de Google** (solo 3.1 Flash): usa imágenes web como contexto visual. No sirve para buscar personas. Exige atribución con enlace a la página fuente.
- **Modo de pensamiento (Thinking)**: activo por defecto en Gemini 3; genera hasta 2 imágenes provisionales de composición. En 3.1 Flash se controla con `thinkingLevel` (`minimal`|`high`). Los tokens de pensamiento se facturan siempre.
- **Firmas de pensamiento** (`thought_signature`): en multi-turno deben devolverse tal cual; los SDK oficiales con chat las manejan automáticamente.
- **Salidas intercaladas** texto+imagen (recetas ilustradas, artículos con imágenes, tutoriales paso a paso).
- **Batch API** para generación masiva (límites más altos, respuesta hasta 24 h).
- Todas las imágenes llevan **marca de agua SynthID**.

## Limitaciones que debes comunicar/considerar

- No genera fondos transparentes (pide fondo blanco para recortar después).
- No admite entradas de audio/video.
- No siempre respeta la cantidad exacta de imágenes solicitadas.
- Grounding con búsqueda no permite usar imágenes de personas reales de la web.
- Mejores idiomas: EN, es-MX, ar-EG, de-DE, fr-FR, hi-IN, id-ID, it-IT, ja-JP, ko-KR, pt-BR, ru-RU, ua-UA, vi-VN, zh-CN.
- Verifica derechos de las imágenes que se suben; no generar contenido que infrinja derechos de terceros.

## Archivos de referencia

- `references/prompting-guide.md` — **Léelo siempre antes de redactar el prompt.** Plantillas y ejemplos
  por caso de uso: fotorrealismo, stickers/íconos, texto/logos, fotografía de producto, minimalismo,
  cómic/storyboard, grounding, edición (agregar/quitar, inpainting semántico, style transfer,
  composición multi-imagen, preservación de detalles, boceto→foto, vista 360° de personaje).
- `references/api-reference.md` — Código completo (Python/JavaScript/REST), configuración
  (`response_modalities`, `aspect_ratio`, `image_size`, `thinkingConfig`, herramientas de búsqueda),
  tablas de resoluciones/tokens por modelo, firmas de pensamiento, Batch API.
- `scripts/generate_image.py` — Script CLI listo para usar (texto→imagen, edición con imágenes de
  entrada, ratio/resolución/grounding configurables).
