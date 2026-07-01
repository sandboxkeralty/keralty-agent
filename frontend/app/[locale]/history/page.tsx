"use client";

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Clock, MessageSquare, ChevronRight, Loader2, MessageCirclePlus } from 'lucide-react';

interface SessionSummary {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  preview: string;
}

interface SessionDetail {
  session: { session_id: string; title: string; created_at: string; updated_at: string };
  messages: { role: string; content: string; timestamp: string }[];
}

export default function HistoryPage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<SessionDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const getToken = () => (typeof window !== 'undefined' ? localStorage.getItem('keralty_token') || 'test-token' : 'test-token');

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${apiUrl}/history/`, {
          headers: { Authorization: `Bearer ${getToken()}` },
        });
        if (res.ok) {
          const data = await res.json();
          setSessions(data.sessions || []);
        }
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const loadSession = async (sessionId: string) => {
    setDetailLoading(true);
    try {
      const res = await fetch(`${apiUrl}/history/${sessionId}`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (res.ok) {
        setSelected(await res.json());
      }
    } catch (e) {
      console.error(e);
    } finally {
      setDetailLoading(false);
    }
  };

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleString('es-ES', { dateStyle: 'short', timeStyle: 'short' });

  const handleContinue = () => {
    if (!selected) return;
    const resumedMessages = selected.messages.map((m, i) => ({
      id: `resumed-${i}`,
      role: m.role === 'user' ? 'user' : 'assistant',
      content: m.content,
    }));
    sessionStorage.setItem('keralty_session', selected.session.session_id);
    sessionStorage.setItem('keralty_resume_messages', JSON.stringify(resumedMessages));
    router.push('/');
  };

  return (
    <div className="p-6 max-w-5xl mx-auto w-full">
      <h1 className="text-2xl font-bold text-[var(--color-navy)] mb-6">Historial de Conversaciones</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Session list */}
        <div className="space-y-3">
          {loading ? (
            <div className="flex items-center gap-2 text-[var(--color-text-muted)]">
              <Loader2 className="h-4 w-4 animate-spin" /> Cargando...
            </div>
          ) : sessions.length === 0 ? (
            <div className="bg-white border border-[var(--color-border)] rounded-[12px] p-6 text-center text-[var(--color-text-muted)]">
              No hay conversaciones anteriores.
            </div>
          ) : (
            sessions.map(s => (
              <button
                key={s.session_id}
                onClick={() => loadSession(s.session_id)}
                className={`w-full text-left bg-white border rounded-[12px] p-4 shadow-sm hover:border-[var(--color-primary)] transition-colors flex items-start gap-3 ${selected?.session.session_id === s.session_id ? 'border-[var(--color-primary)] ring-1 ring-[var(--color-primary)]/30' : 'border-[var(--color-border)]'}`}
              >
                <MessageSquare className="h-4 w-4 mt-0.5 shrink-0 text-[var(--color-primary)]" />
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-[var(--color-navy)] text-sm truncate">{s.title || 'Conversación'}</p>
                  {s.preview && (
                    <p className="text-xs text-[var(--color-text-muted)] mt-0.5 truncate">{s.preview}</p>
                  )}
                  <div className="flex items-center gap-2 mt-1">
                    <Clock className="h-3 w-3 text-[var(--color-text-muted)]" />
                    <span className="text-xs text-[var(--color-text-muted)]">{formatDate(s.updated_at)}</span>
                    <span className="text-xs text-[var(--color-text-muted)]">· {s.message_count} mensajes</span>
                  </div>
                </div>
                <ChevronRight className="h-4 w-4 shrink-0 text-[var(--color-text-muted)]" />
              </button>
            ))
          )}
        </div>

        {/* Session detail */}
        <div className="bg-white border border-[var(--color-border)] rounded-[12px] shadow-sm overflow-hidden">
          {detailLoading ? (
            <div className="flex items-center justify-center h-48 gap-2 text-[var(--color-text-muted)]">
              <Loader2 className="h-4 w-4 animate-spin" /> Cargando conversación...
            </div>
          ) : selected ? (
            <div className="flex flex-col h-full max-h-[600px]">
              <div className="px-4 py-3 border-b border-[var(--color-border)] bg-[var(--color-background)] flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-semibold text-sm text-[var(--color-navy)] truncate">{selected.session.title}</p>
                  <p className="text-xs text-[var(--color-text-muted)]">{formatDate(selected.session.created_at)}</p>
                </div>
                <button
                  onClick={handleContinue}
                  className="flex items-center gap-1.5 shrink-0 text-xs font-medium px-3 py-1.5 bg-[var(--color-primary)] text-white rounded-[6px] hover:bg-[var(--color-primary-dark)] transition-colors"
                >
                  <MessageCirclePlus className="h-3.5 w-3.5" /> Continuar conversación
                </button>
              </div>
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {selected.messages.map((m, i) => (
                  <div key={i} className={`flex gap-2 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[80%] px-3 py-2 rounded-[10px] text-sm ${m.role === 'user' ? 'bg-[var(--color-navy)] text-white' : 'bg-gray-100 text-[var(--color-text-primary)]'}`}>
                      {m.content}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-48 text-sm text-[var(--color-text-muted)]">
              Selecciona una conversación para ver el detalle.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
