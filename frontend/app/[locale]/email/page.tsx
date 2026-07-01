"use client";

import React, { useEffect, useState } from 'react';
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

export default function EmailPage() {
  const [threads, setThreads] = useState<EmailThread[]>([]);
  const [tracked, setTracked] = useState<TrackedEmail[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'inbox' | 'tracking'>('inbox');
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const getToken = () => typeof window !== 'undefined' ? localStorage.getItem('keralty_token') || 'test-token' : 'test-token';

  const fetchInbox = async () => {
    setLoading(true);
    try {
      await fetch(`${apiUrl}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ message: 'lista mis últimos correos de la bandeja de entrada, máximo 20', session_id: 'email-inbox-session' }),
      });
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(false); // Email data comes via the agent chat; this page is a navigation hub
  }, []);

  return (
    <div className="p-6 max-w-5xl mx-auto w-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Mail className="h-6 w-6 text-[var(--color-primary)]" />
          <h1 className="text-2xl font-bold text-[var(--color-navy)]">Correo Ejecutivo</h1>
        </div>
        <button
          onClick={fetchInbox}
          className="flex items-center gap-2 px-3 py-2 text-sm text-[var(--color-primary)] hover:bg-[var(--color-primary-light)] rounded-[8px] transition-colors"
        >
          <RefreshCw className="h-4 w-4" /> Actualizar
        </button>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Bandeja', value: threads.length || '—', color: 'text-[var(--color-primary)]' },
          { label: 'Críticos', value: '—', color: 'text-red-500' },
          { label: 'Pendientes', value: '—', color: 'text-orange-500' },
          { label: 'Seguimiento', value: tracked.length || '—', color: 'text-yellow-600' },
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
            {tab === 'inbox' ? 'Bandeja de Entrada' : 'Seguimiento'}
          </button>
        ))}
      </div>

      {/* Content */}
      {activeTab === 'inbox' && (
        <div className="bg-white border border-[var(--color-border)] rounded-[12px] shadow-sm">
          {loading ? (
            <div className="flex items-center justify-center h-48 gap-2 text-[var(--color-text-muted)]">
              <Loader2 className="h-4 w-4 animate-spin" /> Cargando correos...
            </div>
          ) : threads.length === 0 ? (
            <div className="p-8 text-center">
              <Mail className="h-10 w-10 text-[var(--color-text-muted)] mx-auto mb-3" />
              <p className="text-[var(--color-text-muted)] text-sm">
                Usa el chat para pedir al asistente que liste tu bandeja de entrada.
              </p>
              <p className="text-xs text-[var(--color-text-muted)] mt-1">
                {'Ejemplo: "Lista mis últimos 20 correos" en el chat principal.'}
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-[var(--color-border)]">
              {threads.map(t => (
                <li key={t.id} className="p-4 hover:bg-[var(--color-background)] transition-colors">
                  <div className="flex justify-between items-start mb-1">
                    <span className="font-semibold text-sm text-[var(--color-navy)]">{t.from}</span>
                    <span className="text-xs text-[var(--color-text-muted)]">{t.date}</span>
                  </div>
                  <p className="text-sm font-medium text-[var(--color-text-primary)]">{t.subject}</p>
                  <p className="text-xs text-[var(--color-text-muted)] mt-0.5 line-clamp-1">{t.snippet}</p>
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
                No hay correos en seguimiento actualmente.
              </p>
              <p className="text-xs text-[var(--color-text-muted)] mt-1">
                {'Pide al asistente "haz seguimiento del correo X" para añadirlo.'}
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-[var(--color-border)]">
              {tracked.map(t => (
                <li key={t.tracking_id} className="p-4 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-[var(--color-navy)]">{t.subject || t.message_id}</p>
                    {t.deadline && (
                      <p className="text-xs text-[var(--color-text-muted)] mt-0.5">Vence: {new Date(t.deadline).toLocaleDateString('es-ES')}</p>
                    )}
                  </div>
                  <button
                    className="flex items-center gap-1 text-xs px-3 py-1.5 bg-[var(--color-primary)] text-white rounded-[6px] hover:bg-[var(--color-primary-dark)] transition-colors"
                    onClick={() => {}}
                  >
                    <Send className="h-3 w-3" /> Generar seguimiento
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
