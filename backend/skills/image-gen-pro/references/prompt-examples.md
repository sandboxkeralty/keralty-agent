# Ejemplos Completos de Prompts por Caso de Uso

Esta referencia contiene prompts de producción completos y listos para usar o adaptar.

---

## GENERACIÓN (texto → imagen)

### Infografía: Máquina de Café
```python
prompt = """
Create a detailed Infographic of the functioning and flow of an automatic coffee machine like a Jura.
From bean basket, to grinding, to scale, water tank, boiler, etc.
I'd like to understand technically and visually the flow.
"""
# model="gpt-image-2", size="1024x1536", quality="medium"
```

### Infografía: Proceso de Negocio
```python
prompt = """
Create a professional business infographic titled "Customer Journey Map".
Target audience: marketing executives.
Include: 5 stages (Awareness, Consideration, Purchase, Retention, Advocacy),
key touchpoints per stage, pain points and opportunities.
Style: clean corporate design, white background, blue/gray color palette,
clear icons per stage, readable labels, modern sans-serif typography.
"""
# model="gpt-image-2", size="1536x1024", quality="high"
```

### Fotorrealismo Candid: Persona
```python
prompt = """
Create a photorealistic candid photograph of an elderly sailor standing on a small fishing boat.
He has weathered skin with visible wrinkles, pores, and sun texture,
and a few faded traditional sailor tattoos on his arms.
He is calmly adjusting a net while his dog sits nearby on the deck.
Shot like a 35mm film photograph, medium close-up at eye level, using a 50mm lens.
Soft coastal daylight, shallow depth of field, subtle film grain, natural color balance.
The image should feel honest and unposed, with real skin texture, worn materials, and everyday detail.
No glamorization, no heavy retouching.
"""
# model="gpt-image-2", size="1024x1536", quality="medium"
```

### Logo (múltiples variantes)
```python
prompt = """
Create an original, non-infringing logo for a company called Field & Flour, a local bakery.
The logo should feel warm, simple, and timeless.
Use clean, vector-like shapes, a strong silhouette, and balanced negative space.
Favor simplicity over detail so it reads clearly at small and large sizes.
Flat design, minimal strokes, no gradients unless essential.
Plain background. Deliver a single centered logo with generous padding. No watermark.
"""
# model="gpt-image-2", size="1024x1536", quality="medium", n=4
```

### Logo para Empresa de Tecnología de Salud
```python
prompt = """
Create an original, non-infringing logo for "HealthCore AI", a healthcare technology company.
Brand personality: trustworthy, innovative, clean, professional.
Visual concept: subtle combination of a heartbeat line and a circuit/data node.
Style: modern flat design, minimal strokes, clean geometric shapes.
Colors: deep teal and white, with a subtle gray accent.
Scalable: must read clearly at 32px and 512px.
Plain white background. Single centered logo with generous padding.
No watermark. No trademark symbols. No text other than the company name.
Typography (if included): modern sans-serif, clean and bold.
"""
# model="gpt-image-2", size="1024x1024", quality="medium", n=4
```

### Anuncio Publicitario: Streetwear
```python
prompt = """
Give me a cool in-culture ad / fashion shot for a brand called Thread.
It's a hip young street brand. The ad shows a group of friends hanging out together
with the tagline "Yours to Create."
Make it feel like a polished campaign image for a youth streetwear audience:
stylish, contemporary, energetic, and tasteful.
Use clean composition, strong color direction, natural poses, and premium fashion photography cues.
Render the tagline exactly once, clearly and legibly, integrated into the ad layout.
No extra text, no watermarks, no unrelated logos.
"""
# model="gpt-image-2", size="1024x1536", quality="medium"
```

### Comic Strip: Historia de Mascota
```python
prompt = """
Create a short vertical comic-style reel with 4 equal-sized panels.
Panel 1: The owner leaves through the front door. The pet is framed in the window behind them,
small against the glass, eyes wide, paws pressed high, the house suddenly quiet.
Panel 2: The door clicks shut. Silence breaks. The pet slowly turns toward the empty house,
posture shifting, eyes sharp with possibility.
Panel 3: The house transformed. The pet sprawls across the couch like it owns the place,
crumbs nearby, sunlight cutting across the room like a spotlight.
Panel 4: The door opens. The pet is seated perfectly by the entrance, alert and composed,
as if nothing happened.
"""
# model="gpt-image-2", size="1024x1536", quality="medium"
```

### UI Mockup: App de Mercado Agrícola
```python
prompt = """
Create a realistic mobile app UI mockup for a local farmers market.
Show today's market with a simple header, a short list of vendors with small photos and categories,
a small "Today's specials" section, and basic information for location and hours.
Design it to be practical, and easy to use.
White background, subtle natural accent colors, clear typography, and minimal decoration.
It should look like a real, well-designed, beautiful app for a small local market.
Place the UI mockup in an iPhone frame.
"""
# model="gpt-image-2", size="1024x1536", quality="medium"
```

### Visual Científico: Respiración Celular
```python
prompt = """
Create a simple biology diagram titled "Cellular Respiration at a Glance"
for high school students.

Show how glucose turns into energy inside a cell.
Include glycolysis, the Krebs cycle, and the electron transport chain.
Use arrows to connect the steps, and label the main molecules:
glucose, pyruvate, ATP, NADH, FADH2, CO2, O2, and H2O.
Make it look like a clean classroom handout or slide,
with a white background, simple icons, clear labels, and easy-to-read text.

Avoid tiny text, extra decoration, or anything that makes the diagram hard to understand.
"""
# model="gpt-image-2", size="1536x1024", quality="high"
```

### Slide de Pitch Deck
```python
prompt = """
Create one pitch-deck slide titled "Market Opportunity"
that feels like a real Series A fundraising slide from a YC-backed startup.

Use a clean white background, modern sans-serif typography like Inter,
and a crisp, minimal layout. The slide should include:

* A TAM/SAM/SOM concentric-circle diagram in muted blues and grays
* Specific, believable market sizing numbers:
  * TAM: $42B
  * SAM: $8.7B
  * SOM: $340M
* A clean bar chart below showing market growth from 2021 to 2026, with a subtle upward trend
* Small footnotes: "AGI Research, 2024" and "Internal analysis"
* A company logo placeholder in the bottom-right corner

The design should look like it belongs in a deck that actually raised money:
highly readable text, clear data hierarchy, polished spacing,
and professional startup-style visual language.

Avoid clip art, stock photography, gradients, shadows, decorative elements,
or anything that feels generic or overdesigned.
"""
# model="gpt-image-2", size="1536x864", quality="high"
```

---

## EDICIÓN (texto + imagen → imagen)

### Transferencia de Estilo
```python
prompt = """
Use the same style from the input image and generate a man riding a motorcycle
on a white background.
Preserve: color palette, texture, artistic technique, composition style.
Change only: the subject and scene.
No extra elements, no text, no watermarks.
"""
# model="gpt-image-2", image=[open("style_reference.png","rb")], size="1024x1536", quality="medium"
```

### Virtual Try-On Completo
```python
prompt = """
Edit the image to dress the woman using the provided clothing images.
Do not change her face, facial features, skin tone, body shape, pose, or identity in any way.
Preserve her exact likeness, expression, hairstyle, and proportions.
Replace only the clothing, fitting the garments naturally to her existing pose
and body geometry with realistic fabric behavior.
Match lighting, shadows, and color temperature to the original photo
so the outfit integrates photorealistically, without looking pasted on.
Do not change the background, camera angle, framing, or image quality,
and do not add accessories, text, logos, or watermarks.
"""
# model="gpt-image-2"
# image=[person.png, item1.png, item2.png, item3.png]
# size="1024x1536", quality="medium"
```

### Sketch to Render
```python
prompt = """
Turn this drawing into a photorealistic image.
Preserve the exact layout, proportions, and perspective.
Choose realistic materials and lighting consistent with the sketch intent.
Do not add new elements or text.
"""
# model="gpt-image-2", image=[open("sketch.png","rb")], size="1024x1536", quality="medium"
```

### Extracción de Producto para E-commerce
```python
prompt = """
Extract the product from the input image and place it on a plain white opaque background.
Output: centered product, crisp silhouette, no halos or fringing.
Preserve product geometry and label legibility exactly.
Add only light polishing and a subtle realistic contact shadow.
Do not restyle the product; only remove background and lightly polish.
"""
# model="gpt-image-2", image=[open("product.png","rb")]
# size="1024x1536", quality="medium", background="opaque"
```

### Billboard con Producto
```python
prompt = """
Create a realistic billboard mockup of the product on a highway scene during sunset.
Billboard text (EXACT, verbatim, no extra characters): "Fresh and clean"
Typography: bold sans-serif, high contrast, centered, clean kerning.
Ensure text appears once and is perfectly legible.
No watermarks, no logos.
"""
# model="gpt-image-2", image=[open("product.png","rb")], size="1024x1536", quality="medium"
```

### Transformación Climática
```python
prompt = """
Make it look like a winter evening with snowfall.
Change ONLY: lighting, weather, atmosphere, precipitation.
Preserve: all subjects, objects, geometry, camera angle, composition.
"""
# model="gpt-image-2", image=[open("original.png","rb")]
# input_fidelity="high", size="1024x1536", quality="medium"
```

### Eliminación de Objeto Específico
```python
prompt = """
Remove the [OBJETO] from the image. Do not change anything else.
Preserve: composition, lighting, all other objects, camera angle.
Fill the area naturally to match the surrounding context.
"""
# model="gpt-image-2", image=[open("photo.png","rb")]
# input_fidelity="high", size="1024x1536", quality="medium"
```

### Persona en Nueva Escena
```python
prompt = """
Generate a highly realistic action scene where this person is [ACCIÓN].
The image should look like a real photograph someone could have taken,
not an overly enhanced or cinematic movie-poster image.
[DESCRIPCIÓN DE APARIENCIA Y ESTADO].
The setting is [LUGAR], with believable natural details.
The time of day is [HORA], with natural lighting and realistic colors.
Everything should feel grounded, authentic, and unstyled.
Avoid cinematic lighting, dramatic color grading, or stylized composition.
"""
# model="gpt-image-2", image=[open("person.png","rb")]
# input_fidelity="high", size="1024x1536", quality="medium"
```

### Compositing Multi-Imagen
```python
prompt = """
Place the dog from the second image into the setting of image 1,
right next to the woman, use the same style of lighting, composition and background.
Do not change anything else.
"""
# model="gpt-image-2"
# image=[open("scene.png","rb"), open("dog.png","rb")]
# input_fidelity="high", size="1024x1536", quality="medium"
```

---

## CASOS ESPECIALES

### Rediseño de Interior
```python
prompt = """
In this room photo, replace ONLY [OBJETO ACTUAL: white chairs]
with [NUEVO OBJETO: chairs made of wood].
Preserve: camera angle, room lighting, floor shadows, and all surrounding objects.
Keep ALL other aspects of the image unchanged.
Add photorealistic contact shadows and realistic [wood/fabric/metal] texture.
"""
# model="gpt-image-2", image=[open("room.jpg","rb")], size="1536x1024", quality="medium"
```

### Libro Infantil — Ancla de Personaje
```python
prompt = """
Create a children's book illustration introducing a main character.

Character:
A young, storybook-style hero inspired by a little forest outlaw,
wearing a simple green hooded tunic, soft brown boots, and a small belt pouch.
The character has a kind expression, gentle eyes, and a brave but warm demeanor.
Carries a small wooden bow used only for helping, never harming.

Theme:
The character protects and rescues small forest animals like squirrels, birds, and rabbits.

Style:
Children's book illustration, hand-painted watercolor look,
soft outlines, warm earthy colors, whimsical and friendly.
Proportions suitable for picture books (slightly oversized head, expressive face).

Constraints:
- Original character (no copyrighted characters)
- No text
- No watermarks
- Plain forest background to clearly showcase the character
"""
# model="gpt-image-2", size="1024x1536", quality="medium"
```

### Libro Infantil — Continuación de Historia
```python
prompt = """
Continue the children's book story using the same character.

Scene:
The same young forest hero is gently helping a frightened squirrel
out of a fallen tree after a winter storm.
The character kneels beside the squirrel, offering reassurance.

Character Consistency (DO NOT CHANGE):
- Same green hooded tunic
- Same facial features, proportions, and color palette
- Same gentle, heroic personality

Style:
Children's book watercolor illustration,
soft lighting, snowy forest environment, warm and comforting mood.

Constraints:
- Do not redesign the character
- No text
- No watermarks
"""
# model="gpt-image-2"
# image=[open("character_anchor.png","rb")]  # imagen del paso anterior
# size="1024x1536", quality="medium"
```

### Producto Coleccionable / Merch
```python
prompt = """
Create a collectible action figure of a vintage-style toy propeller airplane
with rounded wings, a front-mounted spinning propeller, slightly worn paint edges,
classic childhood proportions, designed as a nostalgic holiday collectible,
in blister packaging.

Concept:
A nostalgic holiday collectible inspired by the simple toy airplanes
children used to play with during winter holidays.
Evokes warmth, imagination, and childhood wonder.

Style:
Premium toy photography, realistic plastic and painted metal textures,
studio lighting, shallow depth of field,
sharp label printing, high-end retail presentation.

Constraints:
- Original design only
- No trademarks
- No watermarks
- No logos

Include ONLY this packaging text (verbatim): "Christmas Memories Edition"
"""
# model="gpt-image-2", size="1024x1536", quality="medium"
```
