"use client";

import { useState, useRef, useEffect } from 'react';
import type { AnchorHTMLAttributes, ImgHTMLAttributes } from 'react';
import { Send, Bot, User, Paperclip, X, Download, Volume2, Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { SourceChip } from './SourceChip';
import { ApprovalCard } from './ApprovalCard';
import { DocumentPicker, DriveFile } from '../documents/DocumentPicker';
import { AttachMenu } from '../documents/AttachMenu';
import { VoiceChat } from './VoiceChat';
import { useTranslations, useLocale } from 'next-intl';
import { useChatSession, ChatMessage } from '@/hooks/useChatSession';

// Strips Markdown syntax so it isn't read aloud literally (e.g. "asterisk asterisk").
function stripMarkdownForSpeech(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/(\*\*|__)(.*?)\1/g, '$2')
    .replace(/(\*|_)(.*?)\1/g, '$2')
    .replace(/^\s*[-*+]\s+/gm, '')
    .replace(/^\s*\d+\.\s+/gm, '')
    .replace(/\|/g, ' ')
    .replace(/\n{2,}/g, '. ')
    .replace(/\n/g, ' ')
    .trim();
}

function MarkdownImage({ src, alt }: ImgHTMLAttributes<HTMLImageElement>) {
  const imgSrc = typeof src === 'string' ? src : undefined;

  const handleDownload = async () => {
    if (!imgSrc) return;
    try {
      const res = await fetch(imgSrc, { cache: 'no-store' });
      const blob = await res.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = (typeof alt === 'string' && alt.trim()) || 'imagen-generada.png';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(blobUrl);
    } catch (e) {
      console.error('Image download failed', e);
      window.open(imgSrc, '_blank');
    }
  };

  return (
    <span className="relative inline-block group my-1 max-w-full">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={imgSrc} alt={typeof alt === 'string' ? alt : ''} className="max-w-full rounded-lg border border-[var(--color-border)]" />
      <button
        type="button"
        onClick={handleDownload}
        title="Descargar imagen"
        className="absolute top-2 right-2 p-1.5 bg-white/90 rounded-full shadow hover:bg-white transition-colors opacity-0 group-hover:opacity-100"
      >
        <Download size={14} className="text-[var(--color-navy)]" />
      </button>
    </span>
  );
}

// Links to created documents/artifacts (Docs, Sheets, Slides, images, etc.)
// should open in a new tab instead of navigating away from the app.
function MarkdownLink({ href, children }: AnchorHTMLAttributes<HTMLAnchorElement>) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  );
}

interface PendingTask {
  task_id: string;
  description: string;
  document_id: string;
  changes_summary: string;
  type: string;
}

export function ChatWindow() {
  const t = useTranslations('chat');
  const td = useTranslations('documents');
  const locale = useLocale();
  const { sessionId, messages, setMessages, bumpHistoryRefresh } = useChatSession();
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [pendingTasks, setPendingTasks] = useState<PendingTask[]>([]);
  const [showAttachMenu, setShowAttachMenu] = useState(false);
  const [showPicker, setShowPicker] = useState(false);
  const [attachedDoc, setAttachedDoc] = useState<{ file: DriveFile; text: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [playingMessageId, setPlayingMessageId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);

  const stopPlayback = () => {
    audioRef.current?.pause();
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
    audioRef.current = null;
    setPlayingMessageId(null);
  };

  const playMessage = async (id: string, text: string) => {
    if (playingMessageId === id) {
      stopPlayback();
      return;
    }
    stopPlayback();
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const token = localStorage.getItem('keralty_token') || 'test-token';
      const res = await fetch(`${apiUrl}/api/tts`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ text: stripMarkdownForSpeech(text), locale }),
      });
      if (!res.ok) throw new Error('TTS request failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      audioUrlRef.current = url;
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => stopPlayback();
      audio.onerror = () => stopPlayback();
      setPlayingMessageId(id);
      await audio.play();
    } catch (e) {
      console.error('TTS playback failed', e);
      stopPlayback();
    }
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    const poll = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const token = localStorage.getItem('keralty_token') || 'test-token';
        const res = await fetch(`${apiUrl}/api/tasks`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (res.ok) {
          const tasks: PendingTask[] = await res.json();
          setPendingTasks(tasks);
        }
      } catch {
        // ignore polling errors
      }
    };
    poll();
    const interval = setInterval(poll, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleApprove = async (taskId: string, documentId: string) => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const token = localStorage.getItem('keralty_token') || 'test-token';
    await fetch(`${apiUrl}/api/tasks/${taskId}/approve`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
    });
    setPendingTasks(prev => prev.filter(t => t.task_id !== taskId));
    // Auto-send approval message so the agent can continue
    setInput(`[APROBADO] task_id=${taskId} — procede con la operación para el documento ${documentId}`);
    setTimeout(() => {
      document.querySelector<HTMLFormElement>('form')?.requestSubmit();
    }, 100);
  };

  const handleSelectDoc = async (file: DriveFile) => {
    setShowPicker(false);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const token = localStorage.getItem('keralty_token') || 'test-token';
      const res = await fetch(`${apiUrl}/documents/${file.id}/text`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setAttachedDoc({ file, text: data.text });
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleLocalUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    setShowAttachMenu(false);
    if (!file) return;
    setUploading(true);
    setUploadError('');
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const token = localStorage.getItem('keralty_token') || 'test-token';
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${apiUrl}/documents/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || td('uploadFailed'));
      setAttachedDoc({
        file: { id: `local:${Date.now()}`, name: data.filename, mimeType: file.type || 'application/octet-stream' },
        text: data.text,
      });
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : String(err));
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleTranscript = (text: string) => {
    stopPlayback();
    setInput(text);
    setTimeout(() => formRef.current?.requestSubmit(), 80);
  };

  const handleReject = async (taskId: string) => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const token = localStorage.getItem('keralty_token') || 'test-token';
    await fetch(`${apiUrl}/api/tasks/${taskId}/reject`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
    });
    setPendingTasks(prev => prev.filter(t => t.task_id !== taskId));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    const assistantId = (Date.now() + 1).toString();
    setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '', isStreaming: true }]);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const token = localStorage.getItem('keralty_token') || 'test-token';
      const response = await fetch(`${apiUrl}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          message: userMessage.content,
          session_id: sessionId,
          ...(attachedDoc ? { attached_context: attachedDoc.text } : {}),
        }),
      });

      if (!response.body) throw new Error('No readable stream');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      let done = false;
      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        if (value) {
          buffer += decoder.decode(value, { stream: !done });
          const lines = buffer.split('\n\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const dataStr = line.slice(6);
              try {
                const data = JSON.parse(dataStr);
                if (data.type === 'content') {
                  setMessages(prev => prev.map(m =>
                    m.id === assistantId ? { ...m, content: m.content + data.text } : m
                  ));
                } else if (data.type === 'source') {
                   setMessages(prev => prev.map(m => {
                      if (m.id === assistantId) {
                         const sources = m.sources || [];
                         return { ...m, sources: [...sources, data.source] };
                      }
                      return m;
                   }));
                }
              } catch (e) {
                console.error("Error parsing JSON chunk", e);
              }
            }
          }
        }
      }
      
      setMessages(prev => prev.map(m =>
        m.id === assistantId ? { ...m, isStreaming: false } : m
      ));
      setAttachedDoc(null);
      bumpHistoryRefresh();
    } catch (err) {
      console.error(err);
      setMessages(prev => prev.map(m =>
        m.id === assistantId ? { ...m, content: 'Error communicating with the assistant.', isStreaming: false } : m
      ));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative flex flex-col h-full bg-[var(--color-background)] rounded-lg shadow-sm border border-[var(--color-border)]">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map(m => (
          <div key={m.id} className={`flex gap-3 max-w-[80%] ${m.role === 'user' ? 'ml-auto flex-row-reverse' : ''}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${m.role === 'user' ? 'bg-[var(--color-navy)] text-white' : 'bg-[var(--color-primary-light)] text-[var(--color-navy)]'}`}>
              {m.role === 'user' ? <User size={16} /> : <Bot size={16} />}
            </div>
            <div className={`flex flex-col gap-2 ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
              <div className={`px-4 py-3 rounded-[12px] text-sm ${m.role === 'user' ? 'bg-[var(--color-navy)] text-white' : 'bg-white border border-[var(--color-border)] text-[var(--color-text-primary)] shadow-sm'}`}>
                <div className="[&_a]:text-blue-600 [&_a]:underline [&_a:hover]:text-blue-800 [&_h1]:text-base [&_h1]:font-bold [&_h1]:mb-1 [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:mb-1 [&_h3]:text-sm [&_h3]:font-semibold [&_p]:mb-1 [&_ul]:list-disc [&_ul]:pl-4 [&_ol]:list-decimal [&_ol]:pl-4 [&_li]:mb-0.5 [&_table]:border-collapse [&_table]:w-full [&_td]:border [&_td]:border-gray-200 [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:border-gray-200 [&_th]:px-2 [&_th]:py-1 [&_th]:bg-gray-50 [&_code]:bg-gray-100 [&_code]:px-1 [&_code]:rounded [&_blockquote]:border-l-2 [&_blockquote]:border-gray-300 [&_blockquote]:pl-2 [&_blockquote]:italic">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ img: MarkdownImage, a: MarkdownLink }}>{m.content}</ReactMarkdown>
                </div>
                {m.isStreaming && <span className="inline-block w-1 h-4 ml-1 bg-current animate-pulse align-middle" />}
              </div>
              {m.sources && m.sources.length > 0 && (
                <div className="flex gap-2 flex-wrap mt-1">
                  {m.sources.map((s, i) => (
                    <SourceChip key={i} title={s.title} url={s.url} />
                  ))}
                </div>
              )}
              {m.role === 'assistant' && !m.isStreaming && m.content.trim() && (
                <button
                  type="button"
                  onClick={() => playMessage(m.id, m.content)}
                  title={playingMessageId === m.id ? t('stopReading') : t('readAloud')}
                  className={`self-start flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full border transition-colors ${
                    playingMessageId === m.id
                      ? 'text-[var(--color-primary)] border-[var(--color-primary)]/40 bg-[var(--color-primary-light)]'
                      : 'text-[var(--color-text-muted)] border-transparent hover:text-[var(--color-primary)] hover:border-[var(--color-primary)]/20'
                  }`}
                >
                  <Volume2 size={12} className={playingMessageId === m.id ? 'animate-pulse' : ''} />
                </button>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      {pendingTasks.length > 0 && (
        <div className="px-4 pb-2 space-y-2 max-h-[50vh] overflow-y-auto">
          {pendingTasks.map(task => (
            <ApprovalCard
              key={task.task_id}
              title={task.description}
              documentId={task.document_id}
              diff={task.changes_summary}
              onApprove={() => handleApprove(task.task_id, task.document_id)}
              onReject={() => handleReject(task.task_id)}
            />
          ))}
        </div>
      )}
      <form ref={formRef} onSubmit={handleSubmit} className="p-4 border-t border-[var(--color-border)] bg-white">
        {attachedDoc && (
          <div className="flex items-center gap-2 mb-2 px-1">
            <span className="flex items-center gap-1.5 text-xs bg-[var(--color-primary-light)] text-[var(--color-navy)] px-2 py-1 rounded-full border border-[var(--color-primary)]/30">
              <Paperclip size={11} />
              {attachedDoc.file.name}
              <button type="button" onClick={() => setAttachedDoc(null)} className="ml-1 hover:text-red-500">
                <X size={11} />
              </button>
            </span>
          </div>
        )}
        {uploadError && (
          <div className="mb-2 px-1 text-xs text-red-500">{uploadError}</div>
        )}
        <div className="relative flex items-center gap-2">
          <div className="relative flex-1 flex items-center">
            <button
              type="button"
              onClick={() => setShowAttachMenu(p => !p)}
              disabled={uploading}
              className="absolute left-3 p-1 text-[var(--color-text-muted)] hover:text-[var(--color-primary)] transition-colors z-10 disabled:opacity-50"
              title="Adjuntar documento"
            >
              {uploading ? <Loader2 size={16} className="animate-spin" /> : <Paperclip size={16} />}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.doc,.txt,.csv,.md"
              onChange={handleLocalUpload}
              className="hidden"
            />
            <input
              type="text"
              className="w-full pl-10 pr-20 py-3 rounded-full border border-[var(--color-border)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/30 text-sm"
              placeholder={t('placeholder')}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
            />
            <div className="absolute right-2 flex items-center gap-1">
              <VoiceChat onTranscript={handleTranscript} />
              <button
                type="submit"
                disabled={!input.trim() || loading}
                className="p-2 rounded-full bg-[var(--color-primary)] text-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[var(--color-primary-dark)] transition-colors"
              >
                <Send size={16} />
              </button>
            </div>
          </div>
        </div>
        {showAttachMenu && (
          <div className="absolute bottom-20 left-4 z-50 shadow-xl rounded-[12px] overflow-hidden">
            <AttachMenu
              onUploadClick={() => {
                setShowAttachMenu(false);
                fileInputRef.current?.click();
              }}
              onDriveClick={() => {
                setShowAttachMenu(false);
                setShowPicker(true);
              }}
            />
          </div>
        )}
        {showPicker && (
          <div className="absolute bottom-20 left-4 z-50 shadow-xl rounded-[12px] overflow-hidden">
            <DocumentPicker onSelect={handleSelectDoc} />
          </div>
        )}
      </form>
    </div>
  );
}
