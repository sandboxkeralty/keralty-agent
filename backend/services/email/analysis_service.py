"""Full-facet thread analysis for Correo Ejecutivo v2.

Extends the batched-classification pattern of triage_service (whose rubric it
reuses verbatim) from a single priority label to the complete facet set the
dashboard needs: prioridad, requiere_accion(+tipo), resumen, accion_sugerida,
fecha_limite. Runs ONLY on new/changed threads — the scan engine serves
unchanged threads from stored state.

Failure model: a failed chunk yields None per item (sentinel), and the caller
keeps each thread's previously stored facets (or defaults for brand-new
threads). Never raises — an analysis outage degrades to stale summaries, never
a broken dashboard.
"""

import json
import re
from typing import Dict, List, Optional

from config import settings
from services.genai_client import get_genai_client
from services.email.triage_service import _PROMPT_HEADER as _RUBRIC

_VALID_PRIORITIES = {"CRITICO", "ALTO", "MEDIO", "BAJO"}
_VALID_ACTION_TYPES = {"responder", "aprobar", "decidir", "informativo"}
_MAX_RESUMEN = 500
_MAX_ACCION = 200
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_INSTRUCTIONS = (
    "Además de la prioridad, para cada hilo determina:\n"
    "- requiere_accion: true si el ejecutivo debe hacer algo (responder, aprobar, decidir); "
    "false si es puramente informativo. En hilos ENVIADOS por el ejecutivo sin respuesta, "
    "normalmente false (la acción está en el otro lado).\n"
    "- accion_tipo: 'responder', 'aprobar', 'decidir' o 'informativo'.\n"
    "- resumen: 1-3 frases en español — de qué trata el hilo y qué solicita el remitente. "
    "Máximo 500 caracteres.\n"
    "- accion_sugerida: qué debería hacer el ejecutivo, en una frase imperativa corta "
    "(máximo 200 caracteres). Si no requiere acción, describe por qué (p. ej. 'Solo "
    "informativo, no requiere respuesta').\n"
    "- fecha_limite: fecha límite detectada en el texto en formato YYYY-MM-DD, o null si "
    "no hay ninguna explícita. No inventes fechas.\n\n"
)


def _format_item(i: int, item: Dict) -> str:
    direction = "ENVIADO por el ejecutivo" if item.get("is_sent_thread") else "RECIBIDO"
    return (
        f"[{i}] ({direction}) De: {item.get('from', '')} | Para: {item.get('to', '')} | "
        f"Asunto: {item.get('subject', '')}\n{item.get('excerpt', '')}"
    )


def _validate(entry: Dict) -> Optional[Dict]:
    if not isinstance(entry, dict):
        return None
    prioridad = entry.get("prioridad")
    if prioridad not in _VALID_PRIORITIES:
        prioridad = "MEDIO"
    accion_tipo = entry.get("accion_tipo")
    if accion_tipo not in _VALID_ACTION_TYPES:
        accion_tipo = "informativo"
    fecha = entry.get("fecha_limite")
    if not (isinstance(fecha, str) and _DATE_RE.match(fecha)):
        fecha = None
    return {
        "prioridad": prioridad,
        "requiere_accion": bool(entry.get("requiere_accion")),
        "accion_tipo": accion_tipo,
        "resumen": str(entry.get("resumen") or "")[:_MAX_RESUMEN],
        "accion_sugerida": str(entry.get("accion_sugerida") or "")[:_MAX_ACCION],
        "fecha_limite": fecha,
    }


def _analyze_chunk(items: List[Dict]) -> List[Optional[Dict]]:
    try:
        blocks = "\n\n".join(_format_item(i, item) for i, item in enumerate(items))
        prompt = (
            f"{_RUBRIC}{_INSTRUCTIONS}Hilos de correo:\n{blocks}\n\n"
            f"Responde con SOLO un array JSON de {len(items)} objetos, uno por hilo, en el "
            "mismo orden. Cada objeto: {\"prioridad\": \"CRITICO|ALTO|MEDIO|BAJO\", "
            "\"requiere_accion\": true|false, \"accion_tipo\": "
            "\"responder|aprobar|decidir|informativo\", \"resumen\": \"...\", "
            "\"accion_sugerida\": \"...\", \"fecha_limite\": \"YYYY-MM-DD\"|null}."
        )

        from google.genai import types

        client = get_genai_client()
        response = client.models.generate_content(
            model=settings.GEMINI_FLASH_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=4096,
                # Mandatory: without this, thinking tokens can consume the whole
                # output budget before any JSON is emitted (see triage_service).
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        raw = (response.text or "").strip()
        start, end = raw.find("["), raw.rfind("]") + 1
        parsed = json.loads(raw[start:end]) if start >= 0 else []
        if len(parsed) != len(items):
            return [None] * len(items)
        return [_validate(e) for e in parsed]
    except Exception as e:
        print(f"[analysis_service] chunk analysis failed: {e}")
        return [None] * len(items)


def analyze_threads(items: List[Dict]) -> List[Optional[Dict]]:
    """One result (or None) per input item, same order.

    Input items: {subject, from, to, is_sent_thread, excerpt} — excerpt is the
    caller-built last-2-messages digest labeled by direction.
    """
    if not items:
        return []
    results: List[Optional[Dict]] = []
    size = max(1, settings.EMAIL_ANALYSIS_BATCH_SIZE)
    for start in range(0, len(items), size):
        results.extend(_analyze_chunk(items[start:start + size]))
    return results
