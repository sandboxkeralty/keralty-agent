"use client";

import React, { useState } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { CalendarClock, Check, CheckCheck, Clock, Loader2, Send, Sparkles } from 'lucide-react';
import {
  ACCION_KEY, ESTADO_KEY, PRIORITY_KEY, PRIORITY_STYLES,
  Priority, ThreadState, ViewTab,
} from './types';

export interface FollowupResult {
  subject?: string;
  body?: string;
  error?: string;
}

interface Props {
  thread: ThreadState;
  view: ViewTab;
  onSetState: (threadId: string, estado: 'gestionado' | 'resuelto') => void;
  onSetPriority: (threadId: string, prioridad: Priority) => void;
  onPostpone: (threadId: string, until: string) => void;
  onGenerateFollowup: (trackingId: string) => void;
  generatingFollowup: boolean;
  followupResult?: FollowupResult;
}

const PRIORITIES: Priority[] = ['CRITICO', 'ALTO', 'MEDIO', 'BAJO'];

export default function ThreadCard({
  thread: t, view, onSetState, onSetPriority, onPostpone,
  onGenerateFollowup, generatingFollowup, followupResult,
}: Props) {
  const tr = useTranslations('email');
  const locale = useLocale();
  const [postponing, setPostponing] = useState(false);
  const [postponeDate, setPostponeDate] = useState('');

  const isFollowupView = view === 'followup';
  const displayName = t.is_sent_thread ? t.to : t.from;
  const displayDate = t.last_message_internal_date
    ? new Date(t.last_message_internal_date).toLocaleDateString(locale)
    : t.date;

  return (
    <li className="p-4 hover:bg-[var(--color-background)] transition-colors">
      {/* Header row: sender/recipient, badges, date */}
      <div className="flex justify-between items-start mb-1 gap-2">
        <div className="flex items-center gap-2 min-w-0 flex-wrap">
          <span className="font-semibold text-sm text-[var(--color-navy)] truncate max-w-56">
            {displayName || tr('noSubject')}
          </span>
          {/* Priority as a dropdown chip — the user's correction becomes the floor */}
          <select
            value={t.prioridad}
            onChange={e => onSetPriority(t.thread_id, e.target.value as Priority)}
            title={tr('changePriority')}
            className={`shrink-0 text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded-full border-0 cursor-pointer ${PRIORITY_STYLES[t.prioridad]}`}
          >
            {PRIORITIES.map(p => (
              <option key={p} value={p}>{tr(PRIORITY_KEY[p])}</option>
            ))}
          </select>
          {t.ai_reescalated && (
            <span className="shrink-0 flex items-center gap-0.5 text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded-full bg-purple-100 text-purple-700">
              <Sparkles className="h-2.5 w-2.5" /> {tr('reEscalatedBadge')}
            </span>
          )}
          {t.requiere_accion && t.accion_tipo && t.accion_tipo !== 'informativo' && (
            <span className="shrink-0 text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700">
              {tr(ACCION_KEY[t.accion_tipo])}
            </span>
          )}
          <span className="shrink-0 text-[10px] uppercase px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-500">
            {tr(ESTADO_KEY[t.estado_gestion])}
          </span>
        </div>
        <span className="text-xs text-[var(--color-text-muted)] shrink-0">{displayDate}</span>
      </div>

      <p className="text-sm font-medium text-[var(--color-text-primary)]">{t.subject || tr('noSubject')}</p>

      {t.resumen && (
        <p className="text-xs text-[var(--color-text-secondary)] mt-1">{t.resumen}</p>
      )}
      {t.accion_sugerida && (
        <p className="text-xs text-[var(--color-primary)] mt-1">
          <span className="font-semibold">{tr('suggestedAction')}:</span> {t.accion_sugerida}
        </p>
      )}

      {/* Meta chips: deadline, days without reply */}
      <div className="flex items-center gap-2 mt-1.5 flex-wrap">
        {t.fecha_limite && (
          <span className="flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-800">
            <CalendarClock className="h-2.5 w-2.5" />
            {tr('deadline')}: {new Date(`${t.fecha_limite}T12:00:00`).toLocaleDateString(locale)}
          </span>
        )}
        {isFollowupView && typeof t.days_without_reply === 'number' && (
          <span className="flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-orange-100 text-orange-700">
            <Clock className="h-2.5 w-2.5" /> {tr('daysWithoutReply', { days: t.days_without_reply })}
          </span>
        )}
      </div>

      {/* Follow-up draft result (tracked threads) */}
      {followupResult && (
        followupResult.error ? (
          <p className="text-xs text-red-600 mt-2">{followupResult.error}</p>
        ) : (
          <div className="text-xs mt-2 bg-[var(--color-primary-light)]/50 border border-[var(--color-primary)]/20 rounded-[8px] p-2 max-w-md">
            <p className="font-semibold text-[var(--color-primary)] mb-1">{tr('followupGenerated')}</p>
            <p className="font-medium text-[var(--color-navy)]">{followupResult.subject}</p>
            <p className="whitespace-pre-wrap text-[var(--color-text-secondary)] mt-1">{followupResult.body}</p>
          </div>
        )
      )}

      {/* Action buttons — viewing a card never changes state; these do */}
      <div className="flex items-center gap-2 mt-2 flex-wrap">
        {(t.estado_gestion === 'nuevo' || t.estado_gestion === 'respondido') && (
          <button
            type="button"
            onClick={() => onSetState(t.thread_id, 'gestionado')}
            className="flex items-center gap-1 text-xs px-2 py-1 border border-[var(--color-border)] rounded-[6px] text-[var(--color-text-secondary)] hover:border-[var(--color-primary)] hover:text-[var(--color-primary)] transition-colors"
          >
            <Check className="h-3 w-3" /> {tr('markManaged')}
          </button>
        )}
        {t.estado_gestion !== 'resuelto' && (
          <button
            type="button"
            onClick={() => onSetState(t.thread_id, 'resuelto')}
            className="flex items-center gap-1 text-xs px-2 py-1 border border-[var(--color-border)] rounded-[6px] text-[var(--color-text-secondary)] hover:border-[var(--color-primary)] hover:text-[var(--color-primary)] transition-colors"
          >
            <CheckCheck className="h-3 w-3" /> {tr('markResolved')}
          </button>
        )}
        {isFollowupView && !postponing && (
          <button
            type="button"
            onClick={() => setPostponing(true)}
            className="flex items-center gap-1 text-xs px-2 py-1 border border-[var(--color-border)] rounded-[6px] text-[var(--color-text-secondary)] hover:border-[var(--color-primary)] hover:text-[var(--color-primary)] transition-colors"
          >
            <CalendarClock className="h-3 w-3" /> {tr('postpone')}
          </button>
        )}
        {isFollowupView && postponing && (
          <span className="flex items-center gap-1.5 text-xs">
            <input
              type="date"
              value={postponeDate}
              min={new Date(Date.now() + 86_400_000).toISOString().slice(0, 10)}
              onChange={e => setPostponeDate(e.target.value)}
              className="border border-[var(--color-border)] rounded-[6px] px-1.5 py-0.5 text-xs"
            />
            <button
              type="button"
              disabled={!postponeDate}
              onClick={() => { onPostpone(t.thread_id, postponeDate); setPostponing(false); }}
              className="px-2 py-1 bg-[var(--color-primary)] text-white rounded-[6px] disabled:opacity-50"
            >
              {tr('postponeConfirm')}
            </button>
            <button
              type="button"
              onClick={() => setPostponing(false)}
              className="text-[var(--color-text-muted)] underline"
            >
              {tr('cancel')}
            </button>
          </span>
        )}
        {isFollowupView && t.tracking_id && (
          <button
            type="button"
            onClick={() => onGenerateFollowup(t.tracking_id!)}
            disabled={generatingFollowup}
            className="flex items-center gap-1 text-xs px-3 py-1 bg-[var(--color-primary)] text-white rounded-[6px] hover:bg-[var(--color-primary-dark)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {generatingFollowup ? <Loader2 className="h-3 w-3 animate-spin" /> : <Send className="h-3 w-3" />}
            {t.followup_draft_id ? tr('regenerateFollowup') : tr('generateFollowup')}
          </button>
        )}
      </div>
    </li>
  );
}
