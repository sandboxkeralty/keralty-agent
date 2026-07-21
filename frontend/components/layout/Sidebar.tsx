"use client";

import * as React from "react";
import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  MessageSquare, Settings, Mail, Plus, Trash2, Loader2, PenLine, Newspaper,
  Folder, FolderOpen, FolderInput, ChevronRight, ChevronDown, Pencil, Check, X,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useChatSession, ChatMessage } from "@/hooks/useChatSession";
import { apiFetch, apiJson, UnauthorizedError } from "@/lib/api";

interface SessionSummary {
  session_id: string;
  title: string;
  folder_id?: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
  preview: string;
}

interface ChatFolder {
  folder_id: string;
  name: string;
}

type GroupKey = "today" | "yesterday" | "last7Days" | "older";
const GROUP_ORDER: GroupKey[] = ["today", "yesterday", "last7Days", "older"];

function groupKey(iso: string): GroupKey {
  const date = new Date(iso);
  const now = new Date();
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const diffDays = Math.round((startOfDay(now) - startOfDay(date)) / 86400000);
  if (diffDays <= 0) return "today";
  if (diffDays === 1) return "yesterday";
  if (diffDays <= 7) return "last7Days";
  return "older";
}

export function Sidebar() {
  const t = useTranslations("sidebar");
  const tNav = useTranslations("nav");
  const router = useRouter();
  const { sessionId, startNewConversation, loadSession, historyRefreshKey } = useChatSession();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [folders, setFolders] = useState<ChatFolder[]>([]);
  const [loading, setLoading] = useState(true);
  const [switching, setSwitching] = useState<string | null>(null);
  // Folder UI state
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [folderName, setFolderName] = useState("");
  const [renamingId, setRenamingId] = useState<string | null>(null);
  // Session rename UI state
  const [renamingSessionId, setRenamingSessionId] = useState<string | null>(null);
  const [sessionTitle, setSessionTitle] = useState("");
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [moveMenuFor, setMoveMenuFor] = useState<string | null>(null);
  const [confirmClearAll, setConfirmClearAll] = useState(false);
  const [busy, setBusy] = useState(false);

  const fetchHistory = useCallback(async () => {
    try {
      const [histRes, foldRes] = await Promise.all([
        apiFetch(`/history/`),
        apiFetch(`/history/folders`),
      ]);
      if (histRes.ok) {
        const data = await histRes.json();
        setSessions(data.sessions || []);
      }
      if (foldRes.ok) {
        const data = await foldRes.json();
        setFolders(data.folders || []);
      }
    } catch (e) {
      if (!(e instanceof UnauthorizedError)) console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory, historyRefreshKey]);

  const handleNewConversation = (folderId: string | null = null) => {
    startNewConversation(folderId);
    if (folderId) setExpanded(prev => new Set(prev).add(folderId));
    router.push("/");
  };

  const handleSelectSession = async (session: SessionSummary) => {
    if (session.session_id === sessionId) {
      router.push("/");
      return;
    }
    setSwitching(session.session_id);
    try {
      const res = await apiFetch(`/history/${session.session_id}`);
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
      if (!(e instanceof UnauthorizedError)) console.error(e);
    } finally {
      setSwitching(null);
    }
  };

  const handleDelete = async (e: React.MouseEvent, session: SessionSummary) => {
    e.stopPropagation();
    try {
      const res = await apiFetch(`/history/${session.session_id}`, { method: "DELETE" });
      if (!res.ok) return;
      setSessions((prev) => prev.filter((s) => s.session_id !== session.session_id));
      if (session.session_id === sessionId) startNewConversation();
    } catch (e) {
      if (!(e instanceof UnauthorizedError)) console.error(e);
    }
  };

  const handleMove = async (session: SessionSummary, folderId: string | null) => {
    setMoveMenuFor(null);
    try {
      await apiJson(`/history/${session.session_id}/folder`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder_id: folderId }),
      });
      setSessions(prev => prev.map(s =>
        s.session_id === session.session_id ? { ...s, folder_id: folderId } : s
      ));
      if (folderId) setExpanded(prev => new Set(prev).add(folderId));
    } catch (e) {
      if (!(e instanceof UnauthorizedError)) console.error(e);
    }
  };

  const handleCreateFolder = async () => {
    const name = folderName.trim();
    if (!name) return;
    try {
      await apiJson(`/history/folders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      setFolderName("");
      setCreatingFolder(false);
      await fetchHistory();
    } catch (e) {
      if (!(e instanceof UnauthorizedError)) console.error(e);
    }
  };

  const handleRenameFolder = async (folderId: string) => {
    const name = folderName.trim();
    setRenamingId(null);
    if (!name) return;
    try {
      await apiJson(`/history/folders/${folderId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      setFolders(prev => prev.map(f => f.folder_id === folderId ? { ...f, name } : f));
    } catch (e) {
      if (!(e instanceof UnauthorizedError)) console.error(e);
    }
  };

  const handleDeleteFolder = async (folderId: string, deleteChats: boolean) => {
    setConfirmDeleteId(null);
    setBusy(true);
    try {
      const memberIds = sessions.filter(s => s.folder_id === folderId).map(s => s.session_id);
      await apiJson(`/history/folders/${folderId}?delete_chats=${deleteChats}`, { method: "DELETE" });
      if (deleteChats && memberIds.includes(sessionId)) startNewConversation();
      await fetchHistory();
    } catch (e) {
      if (!(e instanceof UnauthorizedError)) console.error(e);
    } finally {
      setBusy(false);
    }
  };

  const handleRenameSession = async (sid: string) => {
    const title = sessionTitle.trim();
    setRenamingSessionId(null);
    if (!title) return;
    try {
      await apiJson(`/history/${sid}/title`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      setSessions(prev => prev.map(s => s.session_id === sid ? { ...s, title } : s));
    } catch (e) {
      if (!(e instanceof UnauthorizedError)) console.error(e);
    }
  };

  const handleClearAll = async () => {
    setConfirmClearAll(false);
    setBusy(true);
    try {
      await apiJson(`/history/`, { method: "DELETE" });
      startNewConversation();
      await fetchHistory();
    } catch (e) {
      if (!(e instanceof UnauthorizedError)) console.error(e);
    } finally {
      setBusy(false);
    }
  };

  const unfiled = sessions.filter(s => !s.folder_id);
  const grouped = unfiled.reduce<Record<GroupKey, SessionSummary[]>>((acc, s) => {
    const key = groupKey(s.updated_at);
    (acc[key] ||= []).push(s);
    return acc;
  }, {} as Record<GroupKey, SessionSummary[]>);

  const sessionRow = (s: SessionSummary) => (
    <div key={s.session_id} className="relative">
      {renamingSessionId === s.session_id ? (
        <div className="flex items-center gap-1.5 rounded-[8px] px-3 py-1.5">
          <MessageSquare className="h-3.5 w-3.5 shrink-0 opacity-60" />
          <input
            autoFocus
            value={sessionTitle}
            onChange={e => setSessionTitle(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") handleRenameSession(s.session_id); if (e.key === "Escape") setRenamingSessionId(null); }}
            onBlur={() => handleRenameSession(s.session_id)}
            maxLength={100}
            className="flex-1 min-w-0 rounded-[6px] bg-white/10 border border-white/20 px-1.5 py-0.5 text-xs text-white outline-none focus:border-[var(--color-primary)]"
          />
        </div>
      ) : (
      <button
        onClick={() => handleSelectSession(s)}
        className={`group w-full flex items-center gap-2 rounded-[8px] px-3 py-2 text-sm text-left transition-colors ${
          s.session_id === sessionId
            ? "bg-[var(--color-primary)]/20 text-white"
            : "hover:bg-[var(--color-navy-dark)] text-white/80"
        }`}
      >
        <MessageSquare className="h-3.5 w-3.5 shrink-0 opacity-60" />
        <span className="flex-1 min-w-0 truncate">{s.title || t("untitledConversation")}</span>
        {switching === s.session_id ? (
          <Loader2 className="h-3 w-3 animate-spin shrink-0" />
        ) : (
          <span className="flex items-center gap-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
            <span
              role="button"
              onClick={(e) => { e.stopPropagation(); setRenamingSessionId(s.session_id); setSessionTitle(s.title || ""); }}
              className="hover:text-[var(--color-primary)]"
              title={t("renameConversation")}
            >
              <Pencil className="h-3 w-3" />
            </span>
            <span
              role="button"
              onClick={(e) => { e.stopPropagation(); setMoveMenuFor(moveMenuFor === s.session_id ? null : s.session_id); }}
              className="hover:text-[var(--color-primary)]"
              title={t("moveToFolder")}
            >
              <FolderInput className="h-3.5 w-3.5" />
            </span>
            <span
              role="button"
              onClick={(e) => handleDelete(e, s)}
              className="hover:text-red-400"
              title={t("deleteConversation")}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </span>
          </span>
        )}
      </button>
      )}
      {moveMenuFor === s.session_id && (
        <div className="absolute right-2 top-8 z-50 w-44 rounded-[8px] bg-[var(--color-navy-dark)] border border-white/10 shadow-xl py-1 text-xs">
          <button
            onClick={() => handleMove(s, null)}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-left text-white/80 hover:bg-white/10"
          >
            <span className="w-3.5">{!s.folder_id && <Check className="h-3 w-3" />}</span>
            {t("noFolder")}
          </button>
          {folders.map(f => (
            <button
              key={f.folder_id}
              onClick={() => handleMove(s, f.folder_id)}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-left text-white/80 hover:bg-white/10"
            >
              <span className="w-3.5">{s.folder_id === f.folder_id && <Check className="h-3 w-3" />}</span>
              <span className="truncate">{f.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <aside className="hidden w-[280px] flex-col border-r bg-[var(--color-navy)] text-white md:flex">
      <div className="flex h-16 shrink-0 items-center px-4">
        <Link href="/" className="inline-flex items-center bg-white rounded-[8px] px-3 py-1.5">
          <Image src="/keralty-logo.png" alt="Keralty" width={110} height={44} className="h-7 w-auto object-contain" priority />
        </Link>
      </div>

      <div className="px-4 pb-2">
        <button
          onClick={() => handleNewConversation()}
          className="w-full flex items-center gap-3 rounded-[8px] px-3 py-2 text-sm font-medium bg-[var(--color-primary)] hover:bg-[var(--color-primary-dark)] transition-colors"
        >
          <Plus className="h-4 w-4" />
          {tNav("newChat")}
        </button>
      </div>

      <nav className="px-4 py-2 space-y-1 border-b border-white/10">
        <Link href="/email" className="flex items-center gap-3 rounded-[8px] px-3 py-2 text-sm font-medium hover:bg-[var(--color-navy-dark)]">
          <Mail className="h-4 w-4" />
          {tNav("email")}
        </Link>
        <Link href="/news" className="flex items-center gap-3 rounded-[8px] px-3 py-2 text-sm font-medium hover:bg-[var(--color-navy-dark)]">
          <Newspaper className="h-4 w-4" />
          {tNav("news")}
        </Link>
        <Link href="/estilos" className="flex items-center gap-3 rounded-[8px] px-3 py-2 text-sm font-medium hover:bg-[var(--color-navy-dark)]">
          <PenLine className="h-4 w-4" />
          {tNav("styles")}
        </Link>
        <Link href="/admin" className="flex items-center gap-3 rounded-[8px] px-3 py-2 text-sm font-medium hover:bg-[var(--color-navy-dark)]">
          <Settings className="h-4 w-4" />
          {tNav("admin")}
        </Link>
      </nav>

      <div className="flex-1 overflow-auto px-2 py-3">
        {loading ? (
          <div className="flex items-center gap-2 text-xs text-white/60 px-3 py-2">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> {t("loading")}
          </div>
        ) : (
          <>
            {/* ── Folders ── */}
            <div className="mb-3">
              <div className="flex items-center justify-between px-3 mb-1">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-white/40">{t("folders")}</p>
                <button
                  onClick={() => { setCreatingFolder(p => !p); setFolderName(""); }}
                  className="text-white/40 hover:text-white transition-colors"
                  title={t("newFolder")}
                >
                  <Plus className="h-3.5 w-3.5" />
                </button>
              </div>
              {creatingFolder && (
                <div className="flex items-center gap-1 px-3 mb-1">
                  <input
                    autoFocus
                    value={folderName}
                    onChange={e => setFolderName(e.target.value)}
                    onKeyDown={e => { if (e.key === "Enter") handleCreateFolder(); if (e.key === "Escape") setCreatingFolder(false); }}
                    placeholder={t("folderNamePlaceholder")}
                    maxLength={40}
                    className="flex-1 min-w-0 rounded-[6px] bg-white/10 border border-white/20 px-2 py-1 text-xs text-white placeholder-white/40 outline-none focus:border-[var(--color-primary)]"
                  />
                  <button onClick={handleCreateFolder} className="text-[var(--color-primary)] hover:text-white"><Check className="h-3.5 w-3.5" /></button>
                  <button onClick={() => setCreatingFolder(false)} className="text-white/40 hover:text-white"><X className="h-3.5 w-3.5" /></button>
                </div>
              )}
              {folders.length === 0 && !creatingFolder && (
                <p className="text-[11px] text-white/30 px-3">{t("noFolders")}</p>
              )}
              {folders.map(f => {
                const members = sessions.filter(s => s.folder_id === f.folder_id);
                const isOpen = expanded.has(f.folder_id);
                return (
                  <div key={f.folder_id} className="mb-0.5">
                    <div className="group flex items-center gap-1.5 rounded-[8px] px-3 py-1.5 text-sm text-white/80 hover:bg-[var(--color-navy-dark)]">
                      <button
                        onClick={() => setExpanded(prev => {
                          const next = new Set(prev);
                          if (next.has(f.folder_id)) { next.delete(f.folder_id); } else { next.add(f.folder_id); }
                          return next;
                        })}
                        className="flex items-center gap-1.5 flex-1 min-w-0 text-left"
                      >
                        {isOpen ? <ChevronDown className="h-3 w-3 shrink-0 opacity-50" /> : <ChevronRight className="h-3 w-3 shrink-0 opacity-50" />}
                        {isOpen ? <FolderOpen className="h-3.5 w-3.5 shrink-0 text-[var(--color-primary)]" /> : <Folder className="h-3.5 w-3.5 shrink-0 text-[var(--color-primary)]" />}
                        {renamingId === f.folder_id ? (
                          <input
                            autoFocus
                            value={folderName}
                            onChange={e => setFolderName(e.target.value)}
                            onClick={e => e.stopPropagation()}
                            onKeyDown={e => { if (e.key === "Enter") handleRenameFolder(f.folder_id); if (e.key === "Escape") setRenamingId(null); }}
                            onBlur={() => handleRenameFolder(f.folder_id)}
                            maxLength={40}
                            className="flex-1 min-w-0 rounded-[6px] bg-white/10 border border-white/20 px-1.5 py-0.5 text-xs text-white outline-none"
                          />
                        ) : (
                          <span className="flex-1 min-w-0 truncate">{f.name}</span>
                        )}
                        <span className="text-[10px] text-white/30 shrink-0">{members.length}</span>
                      </button>
                      <span className="flex items-center gap-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                        <span role="button" onClick={() => handleNewConversation(f.folder_id)} className="hover:text-[var(--color-primary)]" title={t("newChatInFolder")}>
                          <Plus className="h-3.5 w-3.5" />
                        </span>
                        <span role="button" onClick={() => { setRenamingId(f.folder_id); setFolderName(f.name); }} className="hover:text-[var(--color-primary)]" title={t("renameFolder")}>
                          <Pencil className="h-3 w-3" />
                        </span>
                        <span role="button" onClick={() => setConfirmDeleteId(confirmDeleteId === f.folder_id ? null : f.folder_id)} className="hover:text-red-400" title={t("deleteFolder")}>
                          <Trash2 className="h-3.5 w-3.5" />
                        </span>
                      </span>
                    </div>
                    {confirmDeleteId === f.folder_id && (
                      <div className="mx-3 mb-1 rounded-[8px] bg-white/5 border border-white/10 p-2 text-[11px] space-y-1.5">
                        <p className="text-white/70">{t("deleteFolderQuestion", { count: members.length })}</p>
                        <button
                          disabled={busy}
                          onClick={() => handleDeleteFolder(f.folder_id, false)}
                          className="w-full rounded-[6px] bg-white/10 hover:bg-white/20 px-2 py-1 text-left text-white/90"
                        >
                          {t("deleteFolderKeepChats")}
                        </button>
                        <button
                          disabled={busy}
                          onClick={() => handleDeleteFolder(f.folder_id, true)}
                          className="w-full rounded-[6px] bg-red-500/20 hover:bg-red-500/40 px-2 py-1 text-left text-red-200"
                        >
                          {t("deleteFolderAndChats")}
                        </button>
                        <button onClick={() => setConfirmDeleteId(null)} className="w-full rounded-[6px] px-2 py-1 text-left text-white/50 hover:text-white">
                          {t("cancel")}
                        </button>
                      </div>
                    )}
                    {isOpen && (
                      <div className="ml-4 border-l border-white/10 pl-1">
                        {members.length === 0
                          ? <p className="text-[11px] text-white/30 px-3 py-1">{t("emptyFolder")}</p>
                          : members.map(sessionRow)}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* ── Unfiled conversations (recency groups) ── */}
            {unfiled.length === 0 && sessions.length === 0 ? (
              <p className="text-xs text-white/40 px-3 py-2">{t("noConversations")}</p>
            ) : (
              GROUP_ORDER.filter((key) => grouped[key]?.length).map((key) => (
                <div key={key} className="mb-3">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-white/40 px-3 mb-1">{t(key)}</p>
                  {grouped[key].map(sessionRow)}
                </div>
              ))
            )}
          </>
        )}
      </div>

      {/* ── Bulk delete ── */}
      <div className="shrink-0 border-t border-white/10 px-2 py-2">
        {confirmClearAll ? (
          <div className="rounded-[8px] bg-red-500/10 border border-red-400/20 p-2 text-[11px] space-y-1.5">
            <p className="text-red-200">{t("clearAllWarning", { count: sessions.length })}</p>
            <div className="flex gap-1.5">
              <button
                disabled={busy}
                onClick={handleClearAll}
                className="flex-1 rounded-[6px] bg-red-500/30 hover:bg-red-500/50 px-2 py-1 text-red-100 font-medium disabled:opacity-50"
              >
                {busy ? <Loader2 className="h-3 w-3 animate-spin mx-auto" /> : t("clearAllConfirm")}
              </button>
              <button onClick={() => setConfirmClearAll(false)} className="flex-1 rounded-[6px] bg-white/10 hover:bg-white/20 px-2 py-1 text-white/70">
                {t("cancel")}
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => sessions.length > 0 && setConfirmClearAll(true)}
            disabled={sessions.length === 0}
            className="w-full flex items-center gap-2 rounded-[8px] px-3 py-1.5 text-xs text-white/40 hover:text-red-300 hover:bg-white/5 transition-colors disabled:opacity-30"
          >
            <Trash2 className="h-3.5 w-3.5" />
            {t("clearAll")}
          </button>
        )}
      </div>
    </aside>
  );
}
