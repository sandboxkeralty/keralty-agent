# Skills — developer-provided capability packages

Cada skill es un directorio `backend/skills/<skill_id>/` con un `SKILL.md`
(frontmatter YAML + cuerpo Markdown) y, opcionalmente, `references/*.md`.
Se cargan una vez al arranque por `services/skill_registry.py` — son contenido
de repositorio revisado en código; **no existe carga en runtime ni desde el
admin panel** (decisión de diseño: las skills modifican prompts de agentes).

## Formato

```markdown
---
name: <skill_id>            # OBLIGATORIO — debe ser IGUAL al nombre del directorio (kebab-case)
description: <una frase>    # OBLIGATORIO
version: 1                  # opcional, informativo
agents: [VisualAgent]       # opcional — agentes cuya INSTRUCTION incorpora la sección Core
tools: [image_generate]     # opcional — tools que consumen el cuerpo completo en código
---

## Core
(≤ ~300 tokens / 1200 chars. Se incorpora SIEMPRE a la instrucción de los
agentes listados — cada turno paga estos tokens; sé breve.)

## <resto del cuerpo>
(Sin límite práctico. Lo consumen deterministicamente las tools listadas —
p. ej. _enrich_prompt en tools/image_tools.py — junto con references/*.md.
Nunca entra al contexto del chat.)
```

## Reglas

- **PROHIBIDO usar llaves `{}` en cualquier parte del contenido** — ADK las
  interpreta como placeholders de estado y un token desconocido mata el turno
  (KeyError). El registry las sanea a `()` al cargar, pero elimínalas del
  fuente. Placeholders permitidos en instrucciones: exactamente
  `{writing_style?}` y `{signature?}` — nunca dentro de una skill.
- Un fallo de parseo NO tumba el arranque: la skill se omite con un log
  `[skill_registry] SKIPPED ...`. La ausencia de skills es el estado
  "desactivado" — no hay feature flag.
- `references/` solo admite `.md` en v1 (otros ficheros se ignoran, reservado).
- No apuntar una skill a los 9 agentes: las reglas independientes del routing
  van en `BRAND_INSTRUCTION_BLOCK` (services/brand.py), no en una skill.

## Flujo para añadir una skill

1. Copiar la carpeta a `backend/skills/<skill_id>/` (sin `.DS_Store`).
2. Normalizar frontmatter: `name` = directorio, añadir `agents`/`tools`/`version`.
3. Redactar la sección `## Core` si el skill debe guiar al agente en chat.
4. Validar: `cd backend && ./venv/bin/python -m services.skill_registry`
   (exit 1 = error duro; corrige antes de commitear).
5. Si el skill apunta a agentes/tools ya cableados (p. ej. VisualAgent /
   image_generate), es un cambio SOLO de contenido: commit + deploy.
   Un agente/tool nuevo necesita una línea de código
   (`core_block_for_agent(...)` en el módulo del agente, o
   `full_guidance_for_tool(...)` en la tool).

## Campos opcionales de scoping

- `providers: [openai]` — el skill solo alimenta a las tools cuando la
  conversación corre en ese proveedor (valores = vocabulario de
  `model_registry.ModelSpec.provider`: `google`/`anthropic`/`openai`;
  ausente = todos). El proveedor lo decide `image_generate` a partir de
  `state["model_provider"]` (anthropic usa la ruta de imagen de Google).
- `tool_references: [fichero.md]` — qué `references/*.md` entran en
  `full_guidance_for_tool` (ausente = todos). Útil para excluir referencias de
  puro código API que solo son ruido para el enriquecedor.
- `scripts/` y otros ficheros no-`.md` se ignoran (reservado).

## Skills actuales

- `image-gen-pro` — ingeniería de prompts para `image_generate` en
  conversaciones **OpenAI** (providers: [openai]; tool_references:
  prompt-examples.md). Su `## Core` (genérico, válido para todos los
  proveedores) se incorpora a VisualAgent. Nota: las plantillas de edición
  (imagen→imagen) y los parámetros de API (`size`, `quality`, `n`) no son
  accionables hoy — la plataforma solo genera y `image_generate` no expone
  esos parámetros; el enriquecedor emite solo el texto del prompt.
- `gemini-api-image-gen` — prompting Nano Banana para la ruta **Gemini/Imagen**
  (providers: [google, anthropic]; tool_references: prompting-guide.md —
  api-reference.md y scripts/ son código de API, excluidos del enriquecedor).
  Misma nota: edición multi-imagen, grounding y selección de modelo del
  material original no son accionables por `image_generate` hoy.
