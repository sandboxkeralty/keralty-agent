"""Server-side HITL approval gate.

The product guarantee ("NUNCA ejecutes escrituras sin aprobación humana
registrada") must be enforced in code, not merely by the agent reading the
literal text `[APROBADO] task_id=...`. Otherwise a prompt-injected attachment
or a crafted user message could satisfy the gate with plain text.

`_require_approval` verifies that an `approved`, user-owned, not-yet-consumed
Firestore task exists for the exact resource being mutated, then consumes it so
one approval authorizes exactly one execution.
"""

from services.firestore import FirestoreService

# Bilingual refusal — the destructive tools return this verbatim to the agent,
# which relays it. Never execute the action when this is returned.
_NO_APPROVAL = (
    "Acción bloqueada: requiere aprobación humana registrada y no se encontró una "
    "aprobación válida (aprobada y sin consumir) para este recurso. Usa approval_create "
    "y espera a que el usuario apruebe antes de ejecutar. / Action blocked: no valid "
    "human approval on record for this resource."
)


def _require_approval(tool_context, resource_id: str):
    """Returns None when the action is authorized (and consumes the approval);
    otherwise returns an error dict the caller must return immediately without
    performing the destructive action.

    `resource_id` is the document_id / draft_id / spreadsheet_id that
    approval_create stored under the task's `document_id` field.
    """
    state = getattr(tool_context, "state", {}) if tool_context else {}
    user_id = state.get("user_id")
    if not user_id:
        return {"status": "error", "message": "No authenticated user in session; cannot verify approval."}

    task = FirestoreService.find_approved_task(user_id, resource_id)
    if not task:
        return {"status": "error", "message": _NO_APPROVAL}

    FirestoreService.consume_task(task["task_id"])
    return None
