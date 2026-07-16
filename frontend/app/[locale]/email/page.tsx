"use client";

// Correo Ejecutivo v2 — management center over per-thread state.
//
// Flow: mount → GET /api/email/threads (instant paint from stored state) →
// POST /api/email/scan streamed as SSE (same data:{json}\n\n frame format the
// chat stream uses) → progress indicator while Gmail/Gemini work → replace
// state on the final "done" frame. The four tiles are computed views over
// facets — the counts come from the server, the lists are filtered with the
// SAME rules in components/email/types.ts (threadInView).

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { Loader2, Mail, RefreshCw, Settings } from 'lucide-react';
import { apiFetch, UnauthorizedError } from '@/lib/api';
import ThreadCard, { FollowupResult } from '@/components/email/ThreadCard';
import EmailSettings from '@/components/email/EmailSettings';
import SearchBar from '@/components/email/SearchBar';
import DigestView from '@/components/email/DigestView';
import {
  EmailIndicators, EmailSettingsData, Priority, ThreadState, ThreadsPayload,
  ViewTab, threadInView, PRIORITY_KEY, PRIORITY_STYLES,
} from '@/components/email/types';

interface ScanProgress {
  phase: 'listing' | 'fetching' | 'analyzing';
  total?: number;
}

const EMPTY_INDICATORS: EmailIndicators = { bandeja: 0, criticos: 0, pendientes: 0, seguimiento: 0 };
const DEFAULT_SETTINGS: EmailSettingsData = { window_days: 7, followup_days: 3, digest_email_enabled: true };

const VIEWS: { id: ViewTab; labelKey: string; indicator: keyof EmailIndicators; color: string }[] = [
  { id: 'inbox', labelKey: 'tabInbox', indicator: 'bandeja', color: 'text-[var(--color-primary)]' },
  { id: 'critical', labelKey: 'tabCritical', indicator: 'criticos', color: 'text-red-500' },
  { id: 'pending', labelKey: 'tabPending', indicator: 'pendientes', color: 'text-orange-500' },
  { id: 'followup', labelKey: 'tabFollowup', indicator: 'seguimiento', color: 'text-yellow-600' },
];

export default function EmailPage() {
  const t = useTranslations('email');
  const locale = useLocale();
  const [threads, setThreads] = useState<ThreadState[]>([]);
  const [indicators, setIndicators] = useState<EmailIndicators>(EMPTY_INDICATORS);
  const [settings, setSettings] = useState<EmailSettingsData>(DEFAULT_SETTINGS);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [scan, setScan] = useState<ScanProgress | null>(null);
  const [scanFailed, setScanFailed] = useState(false);
  const [view, setView] = useState<ViewTab>('inbox');
  const [priorityFilter, setPriorityFilter] = useState<Priority | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [generatingId, setGeneratingId] = useState<string | null>(null);
  const [followupResult, setFollowupResult] = useState<Record<string, FollowupResult>>({});
  const scanningRef = useRef(false);

  const applyPayload = useCallback((data: ThreadsPayload) => {
    setThreads(data.threads || []);
    setIndicators(data.indicators || EMPTY_INDICATORS);
    if (data.settings) setSettings(data.settings);
    setWarnings(data.warnings || []);
  }, []);

  const fetchStored = useCallback(async () => {
    try {
      const res = await apiFetch('/api/email/threads');
      if (res.ok) applyPayload(await res.json());
    } catch (e) {
      if (!(e instanceof UnauthorizedError)) console.error(e);
    } finally {
      setLoading(false);
    }
  }, [applyPayload]);

  // Incremental scan over SSE — same frame parsing as the chat stream.
  const runScan = useCallback(async () => {
    if (scanningRef.current) return;
    scanningRef.current = true;
    setScanFailed(false);
    setScan({ phase: 'listing' });
    try {
      const res = await apiFetch('/api/email/scan', { method: 'POST' });
      if (!res.ok || !res.body) throw new Error(`scan failed (${res.status})`);
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split('\n\n');
        buffer = frames.pop() || '';
        for (const frame of frames) {
          if (!frame.startsWith('data: ')) continue;
          const evt = JSON.parse(frame.slice(6));
          if (evt.type === 'progress') {
            setScan({ phase: evt.phase, total: evt.total });
          } else if (evt.type === 'done') {
            applyPayload(evt as ThreadsPayload);
          } else if (evt.type === 'error') {
            setScanFailed(true);
          }
        }
      }
    } catch (e) {
      if (e instanceof UnauthorizedError) return;
      console.error(e);
      setScanFailed(true);
    } finally {
      scanningRef.current = false;
      setScan(null);
      setLoading(false);
    }
  }, [applyPayload]);

  useEffect(() => {
    // Instant paint from stored state, then refresh via incremental scan.
    fetchStored().then(runScan);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- thread mutations (optimistic update + server refetch) ---

  const patchThread = useCallback(async (threadId: string, path: string, body: object) => {
    try {
      const res = await apiFetch(`/api/email/threads/${threadId}/${path}`, {
        method: path === 'postpone' ? 'POST' : 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const data = await res.json();
        setThreads(prev => prev.map(th => th.thread_id === threadId ? { ...th, ...data.thread } : th));
        // Re-sync indicators with the server's view rules.
        fetchStored();
      }
    } catch (e) {
      if (!(e instanceof UnauthorizedError)) console.error(e);
    }
  }, [fetchStored]);

  const handleSetState = (id: string, estado: 'gestionado' | 'resuelto') =>
    patchThread(id, 'state', { estado_gestion: estado });
  const handleSetPriority = (id: string, prioridad: Priority) =>
    patchThread(id, 'priority', { prioridad });
  const handlePostpone = (id: string, until: string) =>
    patchThread(id, 'postpone', { until });

  const handleGenerateFollowup = async (trackingId: string) => {
    setGeneratingId(trackingId);
    setFollowupResult(prev => { const next = { ...prev }; delete next[trackingId]; return next; });
    try {
      const res = await apiFetch(`/api/email/tracking/${trackingId}/generate-followup`, { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || t('followupError'));
      setFollowupResult(prev => ({ ...prev, [trackingId]: { subject: data.subject, body: data.body } }));
      fetchStored();
    } catch (e) {
      if (e instanceof UnauthorizedError) return;
      setFollowupResult(prev => ({
        ...prev, [trackingId]: { error: e instanceof Error ? e.message : t('followupError') },
      }));
    } finally {
      setGeneratingId(null);
    }
  };

  const visibleThreads = threads.filter(th =>
    threadInView(th, view) && (!priorityFilter || th.prioridad === priorityFilter));

  return (
    <div className="p-6 max-w-5xl mx-auto w-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Mail className="h-6 w-6 text-[var(--color-primary)]" />
          <h1 className="text-2xl font-bold text-[var(--color-navy)]">{t('title')}</h1>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setSettingsOpen(true)}
            className="flex items-center gap-2 px-3 py-2 text-sm text-[var(--color-text-muted)] hover:bg-[var(--color-background)] rounded-[8px] transition-colors"
          >
            <Settings className="h-4 w-4" /> {t('settings')}
          </button>
          <button
            onClick={runScan}
            disabled={!!scan}
            className="flex items-center gap-2 px-3 py-2 text-sm text-[var(--color-primary)] hover:bg-[var(--color-primary-light)] rounded-[8px] transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${scan ? 'animate-spin' : ''}`} /> {t('refresh')}
          </button>
        </div>
      </div>

      <SearchBar />

      {/* Indicator tiles = view navigation */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        {VIEWS.map(v => (
          <button
            key={v.id}
            type="button"
            onClick={() => { setView(v.id); setPriorityFilter(null); }}
            className={`bg-white border rounded-[12px] p-3 text-center shadow-sm transition-colors cursor-pointer hover:border-[var(--color-primary)]/60 ${view === v.id ? 'border-[var(--color-primary)] ring-1 ring-[var(--color-primary)]/40' : 'border-[var(--color-border)]'}`}
          >
            <span className={`text-2xl font-bold ${v.color}`}>{indicators[v.indicator]}</span>
            <p className="text-xs text-[var(--color-text-muted)] uppercase mt-0.5">{t(v.labelKey)}</p>
          </button>
        ))}
      </div>

      {/* Scan progress — replaces a dead spinner with what's actually happening */}
      {scan && (
        <div className="mb-4 flex items-center gap-2 text-xs text-[var(--color-primary)] bg-[var(--color-primary-light)]/40 border border-[var(--color-primary)]/20 rounded-[8px] px-3 py-2">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          {scan.phase === 'analyzing' && scan.total
            ? t('analyzingNew', { count: scan.total })
            : t('scanning')}
        </div>
      )}
      {scanFailed && (
        <div className="mb-4 text-xs text-red-700 bg-red-50 border border-red-200 rounded-[8px] px-3 py-2">
          {t('scanFailed')}
        </div>
      )}
      {warnings.length > 0 && (
        <div className="mb-4 text-xs text-orange-700 bg-orange-50 border border-orange-200 rounded-[8px] px-3 py-2">
          {t('summaryWarning')}
        </div>
      )}

      <DigestView />

      {/* Thread list for the active view */}
      <div className="bg-white border border-[var(--color-border)] rounded-[12px] shadow-sm">
        {/* Per-priority filter chips */}
        {!loading && threads.some(th => threadInView(th, view)) && (
          <div className="flex items-center flex-wrap gap-2 p-3 border-b border-[var(--color-border)]">
            {(['CRITICO', 'ALTO', 'MEDIO', 'BAJO'] as Priority[]).map(p => {
              const count = threads.filter(th => threadInView(th, view) && th.prioridad === p).length;
              if (count === 0) return null;
              return (
                <button
                  key={p}
                  type="button"
                  onClick={() => setPriorityFilter(prev => prev === p ? null : p)}
                  className={`text-[10px] font-semibold uppercase px-2 py-1 rounded-full border transition-colors ${PRIORITY_STYLES[p]} ${priorityFilter === p ? 'ring-2 ring-[var(--color-navy)]/40' : 'opacity-80 hover:opacity-100'}`}
                >
                  {t(PRIORITY_KEY[p])} · {count}
                </button>
              );
            })}
            {priorityFilter && (
              <button type="button" onClick={() => setPriorityFilter(null)} className="text-xs text-[var(--color-text-muted)] underline ml-1">
                {t('clearFilter')}
              </button>
            )}
          </div>
        )}
        {loading ? (
          <div className="flex items-center justify-center h-48 gap-2 text-[var(--color-text-muted)]">
            <Loader2 className="h-4 w-4 animate-spin" /> {t('loadingEmails')}
          </div>
        ) : visibleThreads.length === 0 ? (
          <div className="p-8 text-center">
            <Mail className="h-10 w-10 text-[var(--color-text-muted)] mx-auto mb-3" />
            <p className="text-[var(--color-text-muted)] text-sm">{t('emptyView')}</p>
            <p className="text-xs text-[var(--color-text-muted)] mt-1">{t('askAssistantHint')}</p>
          </div>
        ) : (
          <ul className="divide-y divide-[var(--color-border)]">
            {visibleThreads.map(thread => (
              <ThreadCard
                key={thread.thread_id}
                thread={thread}
                view={view}
                onSetState={handleSetState}
                onSetPriority={handleSetPriority}
                onPostpone={handlePostpone}
                onGenerateFollowup={handleGenerateFollowup}
                generatingFollowup={generatingId === thread.tracking_id}
                followupResult={thread.tracking_id ? followupResult[thread.tracking_id] : undefined}
                onSent={fetchStored}
              />
            ))}
          </ul>
        )}
      </div>

      {settingsOpen && (
        <EmailSettings
          initial={settings}
          locale={locale}
          onClose={() => setSettingsOpen(false)}
          onSaved={saved => { setSettings(saved); runScan(); }}
        />
      )}
    </div>
  );
}
