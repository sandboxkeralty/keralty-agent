---
name: image-gen-pro
description: >
  Ingeniería de prompts profesional para generación de imágenes con IA:
  fundamentos, plantillas por caso de uso (infografías, fotorrealismo, logos,
  anuncios, mockups, diagramas) y parámetros técnicos.
version: 1
agents: [VisualAgent]
tools: [image_generate]
providers: [openai]
tool_references: [prompt-examples.md]
---

# Image Gen Pro

## Core

Al usar image_generate, describe el SUJETO con precisión — la dirección de
arte completa se aplica automáticamente en el servidor:

- Clasifica primero el caso de uso: foto realista, infografía/diagrama, logo,
  anuncio, mockup UI, ilustración. Dilo explícitamente en la descripción
  ("infografía de...", "fotografía realista de...").
- Describe la ESCENA como párrafo narrativo (no lista de palabras clave):
  escena/fondo → sujeto principal → detalles clave → uso final. Sé concreto en
  materiales, texturas y medio visual (foto, ilustración plana, render 3D).
- Incluye encuadre (close-up, wide shot, top-down), perspectiva e iluminación
  (soft diffuse, golden hour, studio).
- Prefiere momentos humanos cotidianos y optimistas de salud/bienestar; nada
  clínico explícito.
- Para infografías o diagramas con texto: especifica el texto literal entre
  comillas y su jerarquía. Para el resto de imágenes NO pidas texto, logos,
  marcas de agua ni rostros identificables.
- Itera con cambios pequeños, re-especificando lo crítico.

Skill para generar y editar imágenes profesionales de calidad de producción, basado en las mejores prácticas
de ingeniería de prompts para modelos de generación de imágenes con IA.

## Flujo de trabajo obligatorio

1. **Analiza la intención** del usuario: ¿qué tipo de imagen necesita? ¿cuál es su uso final?
2. **Clasifica el caso de uso** (ver sección correspondiente más abajo)
3. **Construye el prompt** siguiendo los fundamentos y la plantilla del tipo de imagen
4. **Especifica los parámetros técnicos** (tamaño, calidad, número de variantes)
5. **Genera o edita** la imagen con el modelo adecuado
6. **Presenta el resultado** y ofrece refinamientos iterativos si es necesario

## Modelos disponibles (referencia)

Lee `/references/models.md` para los parámetros técnicos completos.

Resumen rápido de selección de modelo:
- **gpt-image-2**: Predeterminado para producción. Máxima calidad, edición confiable, texto en imagen.
- **gpt-image-2 quality=low**: Alta velocidad y bajo costo, suficiente para la mayoría de casos.
- **gpt-image-1-mini**: Grandes volúmenes, borradores rápidos, exploración de ideas.

---

## Fundamentos de Prompting (aplicar SIEMPRE)

Estos principios son universales y deben aplicarse en todos los tipos de imagen:

### 1. Estructura del prompt

Usa este orden consistente:
```
[Fondo/Escena] → [Sujeto principal] → [Detalles clave] → [Restricciones] → [Uso final]
```

Para solicitudes complejas, usa segmentos con etiquetas o saltos de línea, no un único párrafo largo.

### 2. Especificidad + Calidad

- **Sé concreto** sobre materiales, formas, texturas y medio visual (foto, acuarela, render 3D)
- Para **fotorrealismo**: incluye "photorealistic", "real photograph", "professional photography"
- Añade "quality levers" solo cuando sea necesario: *film grain*, *textured brushstrokes*, *macro detail*
- Para **texto en imágenes**: usa comillas para el texto literal y especifica tipografía, tamaño, color, posición

### 3. Composición y encuadre

Siempre especifica:
- **Encuadre**: close-up, wide shot, top-down, full body, etc.
- **Perspectiva**: eye-level, low-angle, bird's eye view
- **Iluminación/Mood**: soft diffuse, golden hour, high-contrast, studio lighting
- **Layout**: "logo top-right", "subject centered", "negative space on left"

### 4. Invariantes y restricciones

Para ediciones, siempre especifica:
- **Qué cambiar**: "change ONLY X"
- **Qué preservar**: "keep everything else the same", repite la lista en cada iteración
- **Exclusiones**: "no watermark", "no extra text", "no logos", "no trademarks"

### 5. Texto dentro de imágenes

- Pon el texto literal entre **comillas** o en **MAYÚSCULAS**
- Especifica tipografía, tamaño, color y posición
- Para palabras difíciles (marcas, ortografías inusuales), deletrea letra por letra
- Usa `quality=medium` o `quality=high` para texto pequeño o denso

### 6. Iteración inteligente

- Empieza con prompt limpio, refina con cambios pequeños y únicos
- Usa referencias como "same style as before" o "the subject"
- Re-especifica detalles críticos si empiezan a desviarse

---

## Casos de Uso — Generación (texto → imagen)

### 4.1 Infografías

**Cuándo usar**: Explicar información estructurada: estudiantes, ejecutivos, clientes, público general.
Explainers, posters, diagramas etiquetados, timelines, wikis visuales.

**Plantilla de prompt**:
```
Create a detailed infographic of [TEMA].
Target audience: [AUDIENCIA].
Include: [COMPONENTES ESPECÍFICOS].
Visual format: [poster/diagram/timeline/explainer].
Style: clean, labeled, white background, clear hierarchy.
Use quality="high" for dense text or labels.
Size: 1024x1536 (portrait) or 1536x1024 (landscape)
```

**Ejemplo**:
```
Create a detailed Infographic of the functioning and flow of an automatic coffee machine.
From bean basket, to grinding, to scale, water tank, boiler, etc.
I'd like to understand technically and visually the flow.
```

### 4.2 Traducción de Texto en Imágenes

**Cuándo usar**: Localizar diseños existentes (ads, UI, packaging, infografías) a otro idioma sin reconstruir el layout.

**Plantilla de prompt**:
```
Translate the text in the [TYPE OF IMAGE] to [LANGUAGE].
Preserve typography style, placement, spacing, and visual hierarchy.
Translate verbatim and accurately — no extra words, no reflow unless necessary.
Do not alter logos, icons, imagery, or any non-text element.
```

### 4.3 Fotografía Fotorrealista

**Cuándo usar**: Imágenes que deben parecer fotos reales capturadas en el momento.

**Plantilla de prompt**:
```
Create a photorealistic [candid/portrait/action/product] photograph of [SUJETO].
Shot like a [35mm film/digital SLR/iPhone] photograph.
[Focal length]: [50mm/wide/telephoto] lens.
[Lighting]: [soft coastal daylight/golden hour/studio].
[Depth of field]: [shallow/deep].
[Film grain/texture]: [subtle/none].
Natural color balance. The image should feel [honest/candid/unposed].
No glamorization, no heavy retouching.
Size: 1024x1536, quality="medium" or "high"
```

**Claves para fotorrealismo auténtico**:
- Incluye imperfecciones naturales: poros, arrugas, desgaste de tela
- Evita palabras que impliquen producción de estudio o poses artificiales
- Añade detalles cotidianos y contexto de escena real

### 4.4 Conocimiento del Mundo

**Cuándo usar**: El modelo puede inferir contexto histórico, cultural o geográfico sin describirlo explícitamente.

**Plantilla de prompt**:
```
Create a realistic [TYPE OF SCENE] in [LOCATION/CONTEXT] on [DATE/PERIOD].
[Photorealistic/period-accurate] [clothing/environment/details].
```

### 4.5 Generación de Logos

**Cuándo usar**: Crear marcas originales con identidad clara y versatilidad en tamaños.

**Plantilla de prompt**:
```
Create an original, non-infringing logo for [EMPRESA], a [DESCRIPCIÓN BREVE].
Brand personality: [warm/bold/minimalist/playful/professional].
Style: clean, vector-like shapes, strong silhouette, balanced negative space.
Favor simplicity over detail so it reads clearly at small and large sizes.
Flat design, minimal strokes, no gradients unless essential.
Plain background. Single centered logo with generous padding.
No watermark.
Use n=4 to generate multiple variants.
```

**Parámetro especial**: Usa `n=4` para generar 4 variantes simultáneamente.

### 4.6 Anuncios Publicitarios

**Cuándo usar**: Material de campaña, exploración creativa, ads de marcas.

**Plantilla de prompt**:
```
Create a [TYPE: billboard/social ad/banner] for [MARCA], a [DESCRIPCIÓN DE MARCA].
Target audience: [AUDIENCIA].
Concept/vibe: [DESCRIPCIÓN DEL CONCEPTO].
Tagline (EXACT, verbatim): "[TAGLINE]"
Style: [polished/energetic/minimal/premium] [photography/illustration].
Composition: [clean/bold/atmospheric].
Typography: [bold sans-serif/serif/handwritten], integrated naturally into layout.
No extra text, no watermarks, no unrelated logos.
```

**Clave**: Escribe el prompt como un creative brief, no como especificación técnica.

### 4.7 Tiras Cómicas y Narrativa Visual

**Cuándo usar**: Contar historias secuenciales, ilustrar procesos, contenido de redes sociales.

**Plantilla de prompt**:
```
Create a [vertical/horizontal] comic strip with [N] equal-sized panels.
Panel 1: [DESCRIPCIÓN DE ACCIÓN CONCRETA Y VISUAL].
Panel 2: [DESCRIPCIÓN DE ACCIÓN CONCRETA Y VISUAL].
Panel N: [DESCRIPCIÓN DE ACCIÓN CONCRETA Y VISUAL].
Style: [comic book/manga/children's book/newspaper strip].
```

**Clave**: Cada panel debe describir una acción visual concreta y enfocada, no estados emocionales abstractos.

### 4.8 Mockups de UI/UX

**Cuándo usar**: Prototipos de apps, pantallas de software, interfaces web.

**Plantilla de prompt**:
```
Create a realistic [mobile/web/tablet] app UI mockup for [APP PURPOSE].
Show [MAIN SCREEN/FEATURE] with:
- [ELEMENTO 1]: [DESCRIPCIÓN]
- [ELEMENTO 2]: [DESCRIPCIÓN]
Design: [ESTILO VISUAL: minimal/bold/playful/professional].
[Color scheme]. Clear typography. No decorative clutter.
It should look like a real, well-designed, shipped interface.
[Place in iPhone/Android/browser frame if needed.]
```

**Clave**: Describe el producto como si ya existiera. Evita lenguaje de "concept art".

### 4.9 Visuales Científicos y Educativos

**Cuándo usar**: Biología, química, física, materiales de clase, diagramas, sistemas de iconos.

**Plantilla de prompt**:
```
Create a [diagram/infographic/illustration] titled "[TÍTULO]" for [AUDIENCE: high school students/executives/general public].

[DESCRIPCIÓN DEL CONTENIDO: Include X, show Y, use arrows to connect Z].
Label: [LISTA DE COMPONENTES REQUERIDOS].

Style: clean classroom [handout/slide], white background, simple icons,
clear labels, easy-to-read text.
Avoid tiny text, extra decoration, or anything that makes the diagram hard to understand.
Use quality="high" for dense labels.
```

### 4.10 Diapositivas, Diagramas y Material de Productividad

**Cuándo usar**: Slides de pitch, diagramas de flujo, charts, páginas de documentos.

**Plantilla de prompt**:
```
Create one [TYPE: pitch-deck slide/workflow diagram/chart] titled "[TÍTULO]"
that feels like a real [professional deliverable].

Canvas: [SIZE: landscape 1536x864 for slides]
Style: [VISUAL LANGUAGE: clean white, modern sans-serif like Inter, minimal layout]

Include:
- [ELEMENTO 1 con datos reales]
- [ELEMENTO 2 con datos reales]

Design: highly readable text, clear data hierarchy, polished spacing, professional visual language.
Avoid clip art, stock photography, gradients, shadows, or generic decorative elements.
Use quality="high" for small text, legends, axes, or footnotes.
```

---

## Casos de Uso — Edición (texto + imagen → imagen)

### 5.1 Transferencia de Estilo

**Cuándo usar**: Aplicar el lenguaje visual de una imagen de referencia a nuevo contenido (paleta, textura, pinceladas, grano de película).

**Plantilla de prompt**:
```
Use the same style from the input image and generate [NUEVO CONTENIDO].
Preserve: [ELEMENTOS DE ESTILO: color palette/texture/composition].
Change only: [NUEVO SUJETO/ESCENA].
Background: [white/transparent/same as reference].
No extra elements.
```

### 5.2 Virtual Try-On de Ropa

**Cuándo usar**: E-commerce, previsualizaciones de moda, configuradores de outfits.

**Plantilla de prompt**:
```
Edit the image to dress the [person] using the provided clothing images.
PRESERVE (do NOT change):
- Face, facial features, skin tone
- Body shape, pose, proportions
- Expression, hairstyle, exact likeness

CHANGE ONLY:
- Replace clothing, fitting garments naturally to existing pose and body geometry
- Realistic fabric behavior (draping, folds, occlusion)

Match lighting, shadows, and color temperature to the original photo.
Do not change background, camera angle, framing, or image quality.
Do not add accessories, text, logos, or watermarks.
```

**Input**: imagen de persona (1) + imágenes de prendas (2, 3, 4…)

### 5.3 Dibujo a Imagen Real (Sketch-to-Render)

**Cuándo usar**: Convertir bocetos en renders fotorrealistas, visualizar conceptos arquitectónicos.

**Plantilla de prompt**:
```
Turn this drawing into a photorealistic image.
Preserve the exact layout, proportions, and perspective.
Choose realistic materials and lighting consistent with the sketch intent.
Do not add new elements or text.
```

### 5.4 Mockups de Producto (Fondo Limpio)

**Cuándo usar**: Catálogos, marketplaces, sistemas de diseño.

**Plantilla de prompt**:
```
Extract the product from the input image and place it on a plain white opaque background.
Output: centered product, crisp silhouette, no halos or fringing.
Preserve product geometry and label legibility exactly.
Add only light polishing and a subtle realistic contact shadow.
Do not restyle the product; only remove background and lightly polish.
background="opaque"
```

### 5.5 Creativos de Marketing con Texto Real

**Cuándo usar**: Ads con copy específico, billboards, banners, materiales de campaña.

**Plantilla de prompt**:
```
Create a realistic [TYPE: billboard/banner/ad] mockup using the input image.
Text (EXACT, verbatim, no extra characters): "[COPY EXACTO]"
Typography: [bold sans-serif/serif], high contrast, centered, clean kerning.
Ensure text appears ONCE and is perfectly legible.
No watermarks, no logos.
[Describe scene/environment/context]
```

### 5.6 Transformación de Iluminación y Clima

**Cuándo usar**: Re-escenificar fotos para diferentes momentos, estaciones o estados de ánimo.

**Plantilla de prompt**:
```
Transform the environmental conditions to [NUEVA CONDICIÓN: winter evening with snowfall/sunset/overcast].
Change ONLY: lighting direction/quality, shadows, atmosphere, precipitation, ground conditions.
PRESERVE: identity, geometry, camera angle, object placement, composition.
The result should still clearly read as the same original photo.
```

### 5.7 Eliminación de Objetos

**Cuándo usar**: Limpiar composiciones, eliminar elementos no deseados.

**Plantilla de prompt**:
```
Remove [OBJETO ESPECÍFICO] from the image.
Do not change anything else.
Preserve: composition, lighting, all other objects, camera angle.
Fill the area naturally to match the surrounding context.
```

### 5.8 Insertar Persona en Escena

**Cuándo usar**: Storyboards, campañas, visualizaciones "what if" con preservación de identidad.

**Plantilla de prompt**:
```
Generate a [TYPE: action/portrait/lifestyle] scene where this person is [ACCIÓN].
The image should look like a real photograph, not a cinematic movie poster.
[DESCRIPCIÓN DE ROPA/EXPRESIÓN/POSTURA].
[CONTEXTO DE ESCENA: location, time of day, lighting].
Everything should feel grounded, authentic, and unstyled.
Avoid cinematic lighting, dramatic color grading, or stylized composition.
Use input_fidelity="high" for better identity preservation.
```

### 5.9 Compositing Multi-Imagen

**Cuándo usar**: Combinar elementos de múltiples inputs en una imagen coherente.

**Plantilla de prompt**:
```
Reference images by index:
- Image 1: [DESCRIPCIÓN]
- Image 2: [DESCRIPCIÓN]

Composite: Place [ELEMENTO from Image N] into [ESCENA of Image M],
[POSICIÓN: right next to the subject/in the background/on the table].
Match: lighting, perspective, scale, and shadows from Image M.
Preserve: [ELEMENTOS QUE NO DEBEN CAMBIAR].
Do not change anything else.
Use input_fidelity="high".
```

---

## Casos de Uso Adicionales de Alto Valor

### 6.1 Rediseño de Interiores

**Plantilla**:
```
In this room photo, replace ONLY [OBJETO: white chairs] with [NUEVO OBJETO: chairs made of wood].
Preserve: camera angle, room lighting, floor shadows, and surrounding objects.
Keep ALL other aspects unchanged.
Add photorealistic contact shadows and realistic material texture.
```

### 6.2 Tarjetas y Materiales Estacionales

**Plantilla**:
```
Create a [HOLIDAY/SEASONAL] [card/poster] illustration.
Scene: [DESCRIPCIÓN DETALLADA DE LA ESCENA].
Mood: [warm/nostalgic/festive/magical].
Style: [premium holiday/watercolor/illustrated], realistic textures, shallow depth of field.
Constraints: original artwork only, no trademarks, no watermarks, no logos.
Include ONLY this text (verbatim): "[TEXTO EXACTO]"
```

### 6.3 Merch y Concepto de Productos Coleccionables

**Plantilla**:
```
Create a [action figure/plush/keychain] of [DESCRIPCIÓN DEL PERSONAJE/OBJETO],
in [blister/gift box] packaging.
Style: premium toy photography, realistic [plastic/fabric/metal] textures,
studio lighting, shallow depth of field, sharp label printing.
Constraints: original design only, no trademarks, no watermarks, no logos.
Include ONLY this packaging text (verbatim): "[TEXTO EXACTO]"
```

### 6.4 Libro Infantil con Consistencia de Personajes

**Workflow multi-imagen para mantener consistencia visual**:

**Paso 1 — Ancla de personaje** (generación inicial):
```
Create a children's book illustration introducing a main character.
Character: [DESCRIPCIÓN DETALLADA: apariencia, ropa, expresión, proporiones].
Theme: [TEMA DE LA HISTORIA].
Style: children's book illustration, [watercolor/digital/pencil] look,
soft outlines, warm colors, whimsical and friendly.
Proportions: picture book style (slightly oversized head, expressive face).
Constraints: original character, no text, no watermarks, plain background.
```

**Paso 2+ — Continuación** (edición con imagen anterior como input):
```
Continue the children's book story using the same character.
Scene: [NUEVA ESCENA Y ACCIÓN].
Character Consistency (DO NOT CHANGE):
- Same [outfit details]
- Same facial features, proportions, and color palette
- Same [personality trait]
Style: same children's book illustration style, [nueva condición: snowy/sunny/indoor].
Constraints: do not redesign the character, no text, no watermarks.
```

---

## Parámetros Técnicos Rápidos

| Caso de uso | Size | Quality |
|-------------|------|---------|
| Texto denso, infografías | 1024x1536 | high |
| Portraits, personas | 1024x1536 | medium |
| Slides, landscapes | 1536x1024 o 1536x864 | medium/high |
| Logos (múltiples) | 1024x1536 | medium, n=4 |
| Mockups UI | 1024x1536 | medium |
| Alta velocidad/volumen | cualquiera | low |
| Fotorrealismo máximo | 1024x1536 | high |
| Compositing / identidad | 1024x1536 | medium + input_fidelity="high" |

---

## Detalles técnicos completos

Para especificaciones avanzadas de modelos, tamaños exactos, y parámetros de API, lee:
→ `references/models.md`

Para ejemplos de prompts completos por caso de uso, lee:
→ `references/prompt-examples.md`
