"""Gemini-based email priority triage for the executive email dashboard.

Reuses the same CRÍTICO/ALTO/MEDIO/BAJO rubric already defined in
agents/email_agent.py's chat instruction, so the dashboard's Inbox tab
reflects the same triage intelligence the chat-based EmailAgent already has,
instead of relaying Gmail's generic is:important flag. Mirrors the batched
LLM-scoring pattern in services/rag/reranker.py: one prompt scores every
candidate at once, with a safe fallback on any parsing/call failure.
"""

import json
from typing import List

from config import settings
from services.genai_client import get_genai_client

_VALID_LABELS = {"CRITICO", "ALTO", "MEDIO", "BAJO"}
_FALLBACK_LABEL = "MEDIO"

_PROMPT_HEADER = (
    "Eres un clasificador de prioridad de correo para un ejecutivo de una empresa de salud "
    "con operaciones en varios países. Clasifica cada correo en una de estas categorías:\n"
    "- CRITICO: remitente ejecutivo, junta directiva, reguladores o clientes estratégicos; o "
    "palabras clave como 'urgente', 'aprobación', 'fallo', 'regulatorio', 'deadline' con acción "
    "inmediata requerida (menos de 4 horas).\n"
    "- ALTO: requiere respuesta el mismo día, o es una solicitud de reunión con fecha próxima.\n"
    "- MEDIO: puede esperar 24-48 horas.\n"
    "- BAJO: boletines, newsletters, notificaciones automáticas, informativo sin acción "
    "necesaria.\n\n"
)


def classify_priority(threads: List[dict]) -> List[str]:
    """Returns one of CRITICO/ALTO/MEDIO/BAJO per thread, same order as input.

    Never raises — falls back to MEDIO for every item on any failure, so a
    triage outage never breaks the rest of the dashboard.
    """
    if not threads:
        return []

    try:
        snippets = "\n".join(
            f"[{i}] De: {t.get('from', '')} | Asunto: {t.get('subject', '')} | "
            f"{(t.get('snippet', '') or '')[:150]}"
            for i, t in enumerate(threads)
        )
        prompt = (
            f"{_PROMPT_HEADER}Correos:\n{snippets}\n\n"
            f"Responde con SOLO un array JSON de {len(threads)} strings, uno por correo, en el "
            "mismo orden, usando exactamente una de estas etiquetas: CRITICO, ALTO, MEDIO, BAJO."
        )

        from google.genai import types

        client = get_genai_client()
        response = client.models.generate_content(
            model=settings.GEMINI_FLASH_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=512,
                # Without this, Gemini 2.5 Flash's "thinking" tokens can consume
                # the whole max_output_tokens budget before any visible JSON is
                # emitted, truncating the response and silently degrading every
                # item to the MEDIO fallback. Confirmed empirically on the
                # sibling follow-up-body call (services/email/followup_service.py).
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        raw = (response.text or "").strip()
        start, end = raw.find("["), raw.rfind("]") + 1
        labels = json.loads(raw[start:end]) if start >= 0 else []

        if len(labels) != len(threads):
            return [_FALLBACK_LABEL] * len(threads)
        return [l if l in _VALID_LABELS else _FALLBACK_LABEL for l in labels]

    except Exception as e:
        print(f"[triage_service] classification failed: {e}")
        return [_FALLBACK_LABEL] * len(threads)
