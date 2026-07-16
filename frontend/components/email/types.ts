// Correo Ejecutivo v2 — shared types and the view rules.
//
// threadInView MUST stay in lockstep with the backend's
// scan_service.compute_indicators: the tiles' counts come from the server,
// the lists are filtered client-side — a drift between the two shows a tile
// count that doesn't match its list.

export type Priority = 'CRITICO' | 'ALTO' | 'MEDIO' | 'BAJO';
export type Estado = 'nuevo' | 'gestionado' | 'resuelto' | 'pospuesto' | 'respondido';
export type AccionTipo = 'responder' | 'aprobar' | 'decidir' | 'informativo';
export type ViewTab = 'inbox' | 'critical' | 'pending' | 'followup';

export interface ThreadState {
  thread_id: string;
  subject: string;
  from: string;
  to: string;
  snippet: string;
  date: string;
  message_count?: number;
  prioridad: Priority;
  prioridad_source?: 'ai' | 'user';
  ai_reescalated?: boolean;
  requiere_accion?: boolean;
  accion_tipo?: AccionTipo;
  esperando_respuesta?: boolean;
  estado_gestion: Estado;
  resumen?: string;
  accion_sugerida?: string;
  fecha_limite?: string | null;
  is_sent_thread?: boolean;
  days_without_reply?: number | null;
  tracking_id?: string | null;
  followup_draft_id?: string | null;
  last_message_internal_date?: number;
}

export interface EmailIndicators {
  bandeja: number;
  criticos: number;
  pendientes: number;
  seguimiento: number;
}

export interface EmailSettingsData {
  window_days: number;
  followup_days: number;
  digest_email_enabled: boolean;
  locale?: string;
}

export interface ThreadsPayload {
  threads: ThreadState[];
  indicators: EmailIndicators;
  settings: EmailSettingsData;
  warnings: string[];
}

// Strict precedence Critical > Pending: a CRITICO thread never shows in
// Pendientes. Inbox shows ALL new mail, criticals included — the default view
// must never hide an urgent arrival.
export function threadInView(t: ThreadState, view: ViewTab): boolean {
  switch (view) {
    case 'inbox':
      return t.estado_gestion === 'nuevo';
    case 'critical':
      return t.prioridad === 'CRITICO' && t.estado_gestion !== 'resuelto';
    case 'pending':
      return !!t.requiere_accion && t.estado_gestion !== 'resuelto' && t.prioridad !== 'CRITICO';
    case 'followup':
      return !!t.esperando_respuesta && t.estado_gestion !== 'pospuesto';
  }
}

export const PRIORITY_STYLES: Record<Priority, string> = {
  CRITICO: 'bg-red-100 text-red-700',
  ALTO: 'bg-orange-100 text-orange-700',
  MEDIO: 'bg-yellow-100 text-yellow-700',
  BAJO: 'bg-gray-100 text-gray-600',
};

export const PRIORITY_KEY: Record<Priority, string> = {
  CRITICO: 'priorityCritical',
  ALTO: 'priorityHigh',
  MEDIO: 'priorityMedium',
  BAJO: 'priorityLow',
};

export const ESTADO_KEY: Record<Estado, string> = {
  nuevo: 'stateNew',
  gestionado: 'stateManaged',
  resuelto: 'stateResolved',
  pospuesto: 'statePostponed',
  respondido: 'stateResponded',
};

export const ACCION_KEY: Record<AccionTipo, string> = {
  responder: 'actionResponder',
  aprobar: 'actionAprobar',
  decidir: 'actionDecidir',
  informativo: 'actionInformativo',
};
