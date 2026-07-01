"use client";

import * as React from "react";
import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { MessageSquare, Settings, Mail, Plus, Trash2, Loader2 } from "lucide-react";
import { useChatSession, ChatMessage } from "@/hooks/useChatSession";

interface SessionSummary {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  preview: string;
}

const GROUP_ORDER = ["Hoy", "Ayer", "Últimos 7 días", "Anteriores"];

function groupLabel(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const diffDays = Math.round((startOfDay(now) - startOfDay(date)) / 86400000);
  if (diffDays <= 0) return "Hoy";
  if (diffDays === 1) return "Ayer";
  if (diffDays <= 7) return "Últimos 7 días";
  return "Anteriores";
}

export function Sidebar() {
  const router = useRouter();
  const { sessionId, startNewConversation, loadSession, historyRefreshKey } = useChatSession();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [switching, setSwitching] = useState<string | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const getToken = () => (typeof window !== "undefined" ? localStorage.getItem("keralty_token") || "test-token" : "test-token");

  const fetchHistory = useCallback(async () => {
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
  }, [apiUrl]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory, historyRefreshKey]);

  const handleNewConversation = () => {
    startNewConversation();
    router.push("/");
  };

  const handleSelectSession = async (session: SessionSummary) => {
    if (session.session_id === sessionId) {
      router.push("/");
      return;
    }
    setSwitching(session.session_id);
    try {
      const res = await fetch(`${apiUrl}/history/${session.session_id}`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (res.ok) {
        const data = await res.json();
        const mapped: ChatMessage[] = (data.messages || []).map(
          (m: { role: string; content: string }, i: number) => ({
            id: `resumed-${i}`,
            role: m.role === "user" ? "user" : "assistant",
            content: m.content,
          })
        );
        loadSession(session.session_id, mapped);
        router.push("/");
      }
    } catch (e) {
      console.error(e);
    } finally {
      setSwitching(null);
    }
  };

  const handleDelete = async (e: React.MouseEvent, session: SessionSummary) => {
    e.stopPropagation();
    try {
      await fetch(`${apiUrl}/history/${session.session_id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      setSessions((prev) => prev.filter((s) => s.session_id !== session.session_id));
      if (session.session_id === sessionId) {
        startNewConversation();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const grouped = sessions.reduce<Record<string, SessionSummary[]>>((acc, s) => {
    const label = groupLabel(s.updated_at);
    (acc[label] ||= []).push(s);
    return acc;
  }, {});

  return (
    <aside className="hidden w-[280px] flex-col border-r bg-[var(--color-navy)] text-white md:flex">
      <div className="flex h-16 shrink-0 items-center px-4">
        <Link href="/" className="inline-flex items-center bg-white rounded-[8px] px-3 py-1.5">
          <Image src="/keralty-logo.png" alt="Keralty" width={110} height={44} className="h-7 w-auto object-contain" priority />
        </Link>
      </div>

      <div className="px-4 pb-2">
        <button
          onClick={handleNewConversation}
          className="w-full flex items-center gap-3 rounded-[8px] px-3 py-2 text-sm font-medium bg-[var(--color-primary)] hover:bg-[var(--color-primary-dark)] transition-colors"
        >
          <Plus className="h-4 w-4" />
          Nueva conversación
        </button>
      </div>

      <nav className="px-4 py-2 space-y-1 border-b border-white/10">
        <Link href="/email" className="flex items-center gap-3 rounded-[8px] px-3 py-2 text-sm font-medium hover:bg-[var(--color-navy-dark)]">
          <Mail className="h-4 w-4" />
          Correo Ejecutivo
        </Link>
        <Link href="/admin" className="flex items-center gap-3 rounded-[8px] px-3 py-2 text-sm font-medium hover:bg-[var(--color-navy-dark)]">
          <Settings className="h-4 w-4" />
          Administración
        </Link>
      </nav>

      <div className="flex-1 overflow-auto px-2 py-3">
        {loading ? (
          <div className="flex items-center gap-2 text-xs text-white/60 px-3 py-2">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Cargando...
          </div>
        ) : sessions.length === 0 ? (
          <p className="text-xs text-white/40 px-3 py-2">Sin conversaciones aún.</p>
        ) : (
          GROUP_ORDER.filter((label) => grouped[label]?.length).map((label) => (
            <div key={label} className="mb-3">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-white/40 px-3 mb-1">{label}</p>
              {grouped[label].map((s) => (
                <button
                  key={s.session_id}
                  onClick={() => handleSelectSession(s)}
                  className={`group w-full flex items-center gap-2 rounded-[8px] px-3 py-2 text-sm text-left transition-colors ${
                    s.session_id === sessionId
                      ? "bg-[var(--color-primary)]/20 text-white"
                      : "hover:bg-[var(--color-navy-dark)] text-white/80"
                  }`}
                >
                  <MessageSquare className="h-3.5 w-3.5 shrink-0 opacity-60" />
                  <span className="flex-1 min-w-0 truncate">{s.title || "Conversación"}</span>
                  {switching === s.session_id ? (
                    <Loader2 className="h-3 w-3 animate-spin shrink-0" />
                  ) : (
                    <span
                      role="button"
                      onClick={(e) => handleDelete(e, s)}
                      className="shrink-0 opacity-0 group-hover:opacity-100 hover:text-red-400 transition-opacity"
                      title="Eliminar conversación"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </span>
                  )}
                </button>
              ))}
            </div>
          ))
        )}
      </div>
    </aside>
  );
}
