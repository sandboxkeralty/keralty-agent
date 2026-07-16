"use client";

// Dashboard draft cycle (Phase 2): choose an action → generate → edit /
// regenerate / shorter / more formal / ES-EN → approve & send.
//
// Sending is HITL-gated end to end: "Aprobar y enviar" first registers an
// approval task, the confirm dialog is the human approval (POST
// /api/tasks/{id}/approve), and only then does the send endpoint run — which
// re-verifies and consumes the approval server-side. Cancelling the dialog
// rejects the task so nothing approvable lingers.

import React, { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Loader2, Send, Trash2, Wand2 } from 'lucide-react';
import { apiFetch, apiJson, UnauthorizedError } from '@/lib/api';

interface DraftData {
  draft_id: string;
  thread_id: string;
  to: string;
  subject: string;
  body: string;
  in_reply_to?: string | null;
  references?: string | null;
}

type ReplyAction = 'aceptar' | 'declinar' | 'mas_info' | 'delegar' | 'libre';

interface Props {
  threadId: string;
  onClose: () => void;
  onSent: () => void;
}

export default function DraftPanel({ threadId, onClose, onSent }: Props) {
  const t = useTranslations('email');
  const [action, setAction] = useState<ReplyAction | null>(null);
  const [instruction, setInstruction] = useState('');
  const [draft, setDraft] = useState<DraftData | null>(null);
  const [body, setBody] = useState('');
  const [busy, setBusy] = useState<string | null>(null); // which operation is running
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [sent, setSent] = useState(false);

  const ACTIONS: { id: ReplyAction; label: string }[] = [
    { id: 'aceptar', label: t('replyAccept') },
    { id: 'declinar', label: t('replyDecline') },
    { id: 'mas_info', label: t('replyMoreInfo') },
    { id: 'delegar', label: t('replyDelegate') },
    { id: 'libre', label: t('replyCustom') },
  ];

  const generate = async (opts: { modifiers?: string[]; language?: string } = {}) => {
    if (!action) return;
    setBusy('generate');
    setError(null);
    try {
      const data = await apiJson<DraftData & { status: string }>(`/api/email/threads/${threadId}/draft`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action,
          instruction,
          language: opts.language ?? null,
          modifiers: opts.modifiers ?? [],
          previous_draft_id: draft?.draft_id ?? null,
        }),
      });
      setDraft(data);
      setBody(data.body);
    } catch (e) {
      if (e instanceof UnauthorizedError) return;
      setError(e instanceof Error ? e.message : t('sendError'));
    } finally {
      setBusy(null);
    }
  };

  const saveEdit = async () => {
    if (!draft) return;
    setBusy('save');
    setError(null);
    try {
      await apiJson(`/api/email/drafts/${draft.draft_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          to: draft.to, subject: draft.subject, body,
          thread_id: draft.thread_id,
          in_reply_to: draft.in_reply_to, references: draft.references,
        }),
      });
      setDraft({ ...draft, body });
    } catch (e) {
      if (e instanceof UnauthorizedError) return;
      setError(e instanceof Error ? e.message : t('sendError'));
    } finally {
      setBusy(null);
    }
  };

  const discard = async () => {
    if (!draft) { onClose(); return; }
    setBusy('discard');
    try {
      await apiFetch(`/api/email/drafts/${draft.draft_id}`, { method: 'DELETE' });
    } catch (e) {
      if (e instanceof UnauthorizedError) return;
    } finally {
      setBusy(null);
      onClose();
    }
  };

  const approveAndSend = async () => {
    if (!draft) return;
    setBusy('send');
    setError(null);
    let taskId: string | null = null;
    try {
      // Persist any pending edit first — what's in the textarea is what sends.
      if (body !== draft.body) await saveEdit();
      const req = await apiJson<{ task_id: string }>(`/api/email/drafts/${draft.draft_id}/request-approval`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subject: draft.subject, to: draft.to, preview: body.slice(0, 1500) }),
      });
      taskId = req.task_id;
      // The confirm dialog click IS the human approval.
      await apiJson(`/api/tasks/${taskId}/approve`, { method: 'POST' });
      await apiJson(`/api/email/drafts/${draft.draft_id}/send?thread_id=${encodeURIComponent(draft.thread_id)}`, {
        method: 'POST',
      });
      setSent(true);
      setConfirming(false);
      onSent();
    } catch (e) {
      if (e instanceof UnauthorizedError) return;
      // A created-but-unused task must not linger approvable.
      if (taskId) {
        try { await apiFetch(`/api/tasks/${taskId}/reject`, { method: 'POST' }); } catch { /* best effort */ }
      }
      setError(e instanceof Error ? e.message : t('sendError'));
      setConfirming(false);
    } finally {
      setBusy(null);
    }
  };

  if (sent) {
    return (
      <div className="mt-2 text-xs bg-green-50 border border-green-200 text-green-700 rounded-[8px] px-3 py-2">
        {t('sendSuccess')}
      </div>
    );
  }

  return (
    <div className="mt-2 border border-[var(--color-border)] rounded-[8px] p-3 bg-[var(--color-background)]/60">
      {/* Step 1: action chooser */}
      <div className="flex items-center gap-1.5 flex-wrap mb-2">
        {ACTIONS.map(a => (
          <button
            key={a.id}
            type="button"
            onClick={() => setAction(a.id)}
            className={`text-xs px-2 py-1 rounded-full border transition-colors ${action === a.id ? 'bg-[var(--color-primary)] text-white border-[var(--color-primary)]' : 'border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-primary)]'}`}
          >
            {a.label}
          </button>
        ))}
      </div>
      {(action === 'libre' || action === 'delegar') && (
        <input
          type="text"
          value={instruction}
          onChange={e => setInstruction(e.target.value)}
          placeholder={t('customInstructionPlaceholder')}
          className="w-full text-xs border border-[var(--color-border)] rounded-[6px] px-2 py-1.5 mb-2 bg-white"
        />
      )}
      {!draft && (
        <button
          type="button"
          disabled={!action || busy === 'generate' || (action === 'libre' && !instruction.trim())}
          onClick={() => generate()}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-[var(--color-primary)] text-white rounded-[6px] hover:bg-[var(--color-primary-dark)] disabled:opacity-50"
        >
          {busy === 'generate' ? <Loader2 className="h-3 w-3 animate-spin" /> : <Wand2 className="h-3 w-3" />}
          {busy === 'generate' ? t('generatingDraft') : t('generateDraft')}
        </button>
      )}

      {/* Step 2: draft review/edit */}
      {draft && (
        <div className="mt-1">
          <p className="text-xs text-[var(--color-text-muted)]">{t('to')} {draft.to}</p>
          <p className="text-xs font-medium text-[var(--color-navy)] mb-1">{draft.subject}</p>
          <textarea
            value={body}
            onChange={e => setBody(e.target.value)}
            rows={7}
            className="w-full text-xs border border-[var(--color-border)] rounded-[6px] px-2 py-1.5 bg-white font-mono"
          />
          <div className="flex items-center gap-1.5 flex-wrap mt-1.5">
            {body !== draft.body && (
              <button type="button" onClick={saveEdit} disabled={!!busy}
                className="text-xs px-2 py-1 bg-[var(--color-navy)] text-white rounded-[6px] disabled:opacity-50">
                {busy === 'save' ? t('generatingDraft') : t('saveEdit')}
              </button>
            )}
            <button type="button" onClick={() => generate()} disabled={!!busy}
              className="text-xs px-2 py-1 border border-[var(--color-border)] rounded-[6px] hover:border-[var(--color-primary)] disabled:opacity-50">
              {t('regenerate')}
            </button>
            <button type="button" onClick={() => generate({ modifiers: ['shorter'] })} disabled={!!busy}
              className="text-xs px-2 py-1 border border-[var(--color-border)] rounded-[6px] hover:border-[var(--color-primary)] disabled:opacity-50">
              {t('shorter')}
            </button>
            <button type="button" onClick={() => generate({ modifiers: ['more_formal'] })} disabled={!!busy}
              className="text-xs px-2 py-1 border border-[var(--color-border)] rounded-[6px] hover:border-[var(--color-primary)] disabled:opacity-50">
              {t('moreFormal')}
            </button>
            <button type="button" onClick={() => generate({ language: 'es' })} disabled={!!busy}
              className="text-xs px-2 py-1 border border-[var(--color-border)] rounded-[6px] hover:border-[var(--color-primary)] disabled:opacity-50">
              ES
            </button>
            <button type="button" onClick={() => generate({ language: 'en' })} disabled={!!busy}
              className="text-xs px-2 py-1 border border-[var(--color-border)] rounded-[6px] hover:border-[var(--color-primary)] disabled:opacity-50">
              EN
            </button>
            <button type="button" onClick={discard} disabled={!!busy}
              className="flex items-center gap-1 text-xs px-2 py-1 border border-red-200 text-red-600 rounded-[6px] hover:bg-red-50 disabled:opacity-50">
              <Trash2 className="h-3 w-3" /> {t('discard')}
            </button>
            <button type="button" onClick={() => setConfirming(true)} disabled={!!busy}
              className="flex items-center gap-1 text-xs px-3 py-1 bg-[var(--color-primary)] text-white rounded-[6px] hover:bg-[var(--color-primary-dark)] disabled:opacity-50">
              <Send className="h-3 w-3" /> {t('approveSend')}
            </button>
          </div>
        </div>
      )}

      {error && <p className="text-xs text-red-600 mt-2">{error}</p>}

      {/* HITL confirm dialog */}
      {confirming && draft && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setConfirming(false)}>
          <div className="bg-white rounded-[12px] shadow-lg border border-[var(--color-border)] p-5 w-full max-w-sm mx-4" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-bold text-[var(--color-navy)] mb-2">{t('confirmSendTitle')}</h3>
            <p className="text-xs text-[var(--color-text-secondary)] mb-1">{t('to')} {draft.to}</p>
            <p className="text-xs font-medium text-[var(--color-navy)] mb-3">{draft.subject}</p>
            <p className="text-xs text-[var(--color-text-muted)] mb-4">{t('confirmSendBody')}</p>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setConfirming(false)}
                className="text-sm px-3 py-1.5 border border-[var(--color-border)] rounded-[6px] text-[var(--color-text-secondary)]">
                {t('cancel')}
              </button>
              <button type="button" onClick={approveAndSend} disabled={busy === 'send'}
                className="flex items-center gap-1.5 text-sm px-3 py-1.5 bg-[var(--color-primary)] text-white rounded-[6px] hover:bg-[var(--color-primary-dark)] disabled:opacity-50">
                {busy === 'send' && <Loader2 className="h-3 w-3 animate-spin" />} {t('confirmSend')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
