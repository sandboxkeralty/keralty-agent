"use client";

import React, { useEffect, useState } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { Mail, Loader2, RefreshCw, Send, Clock } from 'lucide-react';

interface EmailThread {
  id: string;
  subject: string;
  from: string;
  date: string;
  snippet: string;
}

interface TrackedEmail {
  tracking_id: string;
  message_id: string;
  subject?: string;
  deadline?: string;
  status: string;
}

interface EmailIndicators {
  bandeja: number;
  criticos: number;
  pendientes: number;
  seguimiento: number;
}

export default function EmailPage() {
  const t = useTranslations('email');
  const locale = useLocale();
  const [threads, setThreads] = useState<EmailThread[]>([]);
  const [tracked, setTracked] = useState<TrackedEmail[]>([]);
  const [indicators, setIndicators] = useState<EmailIndicators>({ bandeja: 0, criticos: 0, pendientes: 0, seguimiento: 0 });
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'inbox' | 'tracking'>('inbox');
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const getToken = () => typeof window !== 'undefined' ? localStorage.getItem('keralty_token') || 'test-token' : 'test-token';

  const fetchSummary = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${apiUrl}/api/email/summary`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (res.ok) {
        const data = await res.json();
        setThreads(data.inbox_today || []);
        setTracked(data.tracked || []);
        setIndicators(data.indicators || { bandeja: 0, criticos: 0, pendientes: 0, seguimiento: 0 });
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, []);

  return (
    <div className="p-6 max-w-5xl mx-auto w-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Mail className="h-6 w-6 text-[var(--color-primary)]" />
          <h1 className="text-2xl font-bold text-[var(--color-navy)]">{t('title')}</h1>
        </div>
        <button
          onClick={fetchSummary}
          className="flex items-center gap-2 px-3 py-2 text-sm text-[var(--color-primary)] hover:bg-[var(--color-primary-light)] rounded-[8px] transition-colors"
        >
          <RefreshCw className="h-4 w-4" /> {t('refresh')}
        </button>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: t('inboxIndicator'), value: indicators.bandeja, color: 'text-[var(--color-primary)]' },
          { label: t('criticalIndicator'), value: indicators.criticos, color: 'text-red-500' },
          { label: t('pendingIndicator'), value: indicators.pendientes, color: 'text-orange-500' },
          { label: t('followupIndicator'), value: indicators.seguimiento, color: 'text-yellow-600' },
        ].map(s => (
          <div key={s.label} className="bg-white border border-[var(--color-border)] rounded-[12px] p-3 text-center shadow-sm">
            <span className={`text-2xl font-bold ${s.color}`}>{s.value}</span>
            <p className="text-xs text-[var(--color-text-muted)] uppercase mt-0.5">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Tab nav */}
      <div className="flex gap-1 border-b border-[var(--color-border)] mb-4">
        {(['inbox', 'tracking'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${activeTab === tab ? 'border-[var(--color-primary)] text-[var(--color-primary)]' : 'border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-navy)]'}`}
          >
            {tab === 'inbox' ? t('inboxTab') : t('trackingTab')}
          </button>
        ))}
      </div>

      {/* Content */}
      {activeTab === 'inbox' && (
        <div className="bg-white border border-[var(--color-border)] rounded-[12px] shadow-sm">
          {loading ? (
            <div className="flex items-center justify-center h-48 gap-2 text-[var(--color-text-muted)]">
              <Loader2 className="h-4 w-4 animate-spin" /> {t('loadingEmails')}
            </div>
          ) : threads.length === 0 ? (
            <div className="p-8 text-center">
              <Mail className="h-10 w-10 text-[var(--color-text-muted)] mx-auto mb-3" />
              <p className="text-[var(--color-text-muted)] text-sm">
                {t('noEmailsToday')}
              </p>
              <p className="text-xs text-[var(--color-text-muted)] mt-1">
                {t('askAssistantHint')}
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-[var(--color-border)]">
              {threads.map(thread => (
                <li key={thread.id} className="p-4 hover:bg-[var(--color-background)] transition-colors">
                  <div className="flex justify-between items-start mb-1">
                    <span className="font-semibold text-sm text-[var(--color-navy)]">{thread.from}</span>
                    <span className="text-xs text-[var(--color-text-muted)]">{thread.date}</span>
                  </div>
                  <p className="text-sm font-medium text-[var(--color-text-primary)]">{thread.subject}</p>
                  <p className="text-xs text-[var(--color-text-muted)] mt-0.5 line-clamp-1">{thread.snippet}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {activeTab === 'tracking' && (
        <div className="bg-white border border-[var(--color-border)] rounded-[12px] shadow-sm">
          {tracked.length === 0 ? (
            <div className="p-8 text-center">
              <Clock className="h-10 w-10 text-[var(--color-text-muted)] mx-auto mb-3" />
              <p className="text-[var(--color-text-muted)] text-sm">
                {t('noTracking')}
              </p>
              <p className="text-xs text-[var(--color-text-muted)] mt-1">
                {t('trackingHint')}
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-[var(--color-border)]">
              {tracked.map(item => (
                <li key={item.tracking_id} className="p-4 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-[var(--color-navy)]">{item.subject || item.message_id}</p>
                    {item.deadline && (
                      <p className="text-xs text-[var(--color-text-muted)] mt-0.5">{t('due')} {new Date(item.deadline).toLocaleDateString(locale)}</p>
                    )}
                  </div>
                  <button
                    className="flex items-center gap-1 text-xs px-3 py-1.5 bg-[var(--color-primary)] text-white rounded-[6px] hover:bg-[var(--color-primary-dark)] transition-colors"
                    onClick={() => {}}
                  >
                    <Send className="h-3 w-3" /> {t('generateFollowup')}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
