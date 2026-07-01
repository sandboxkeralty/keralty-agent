"use client";

import { createContext, useCallback, useContext, useState, ReactNode } from "react";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: { title: string; url: string }[];
  isStreaming?: boolean;
}

interface ChatSessionContextValue {
  sessionId: string;
  messages: ChatMessage[];
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  startNewConversation: () => void;
  loadSession: (sessionId: string, messages: ChatMessage[]) => void;
  historyRefreshKey: number;
  bumpHistoryRefresh: () => void;
}

const ChatSessionContext = createContext<ChatSessionContextValue | null>(null);

function newSessionId(): string {
  return crypto.randomUUID();
}

function initialSessionId(): string {
  if (typeof window === "undefined") return "";
  const existing = sessionStorage.getItem("keralty_session");
  if (existing) return existing;
  const sid = newSessionId();
  sessionStorage.setItem("keralty_session", sid);
  return sid;
}

export function ChatSessionProvider({ children }: { children: ReactNode }) {
  const [sessionId, setSessionId] = useState<string>(initialSessionId);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);

  const startNewConversation = useCallback(() => {
    const sid = newSessionId();
    sessionStorage.setItem("keralty_session", sid);
    setSessionId(sid);
    setMessages([]);
  }, []);

  const loadSession = useCallback((sid: string, msgs: ChatMessage[]) => {
    sessionStorage.setItem("keralty_session", sid);
    setSessionId(sid);
    setMessages(msgs);
  }, []);

  const bumpHistoryRefresh = useCallback(() => setHistoryRefreshKey((k) => k + 1), []);

  return (
    <ChatSessionContext.Provider
      value={{ sessionId, messages, setMessages, startNewConversation, loadSession, historyRefreshKey, bumpHistoryRefresh }}
    >
      {children}
    </ChatSessionContext.Provider>
  );
}

export function useChatSession() {
  const ctx = useContext(ChatSessionContext);
  if (!ctx) throw new Error("useChatSession must be used within ChatSessionProvider");
  return ctx;
}
