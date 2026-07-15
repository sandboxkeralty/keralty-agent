"use client";
import * as React from "react";
import { useState, useEffect } from "react";
import { Button } from "../shared/Button";
import { FileText, Folder, Loader2, X, ChevronRight, Home } from "lucide-react";
import { useTranslations } from "next-intl";
import { apiFetch, UnauthorizedError } from "@/lib/api";

export interface DriveFile {
  id: string;
  name: string;
  mimeType: string;
  iconLink?: string;
}

const FOLDER_MIME = "application/vnd.google-apps.folder";

export function DocumentPicker({ onSelect, onClose }: { onSelect: (file: DriveFile) => void; onClose: () => void }) {
  const t = useTranslations("documents");
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState("");
  // Breadcrumb trail for folder browsing; empty = "My Drive" root.
  // A non-empty search shows global results instead of the folder view.
  const [path, setPath] = useState<{ id: string; name: string }[]>([]);
  const [searching, setSearching] = useState(false);

  const fetchFiles = async (opts: { q?: string; folderId?: string }) => {
    setLoading(true);
    try {
      // Trailing slash is required: FastAPI 307-redirects "/documents" to
      // "/documents/" with an http:// Location (Cloud Run terminates TLS, so
      // Uvicorn sees plain HTTP), which the browser blocks as mixed content on
      // an https page — invisible to curl. Call the canonical path directly.
      const params = new URLSearchParams();
      if (opts.q) params.set("q", opts.q);
      else params.set("folder_id", opts.folderId || "root");
      params.set("limit", "50");
      const res = await apiFetch(`/documents/?${params.toString()}`);
      const data = await res.json();
      setFiles(data.files || []);
    } catch (err) {
      if (!(err instanceof UnauthorizedError)) console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFiles({ folderId: "root" });
  }, []);

  const runSearch = () => {
    const q = query.trim();
    if (!q) {
      setSearching(false);
      fetchFiles({ folderId: path.length ? path[path.length - 1].id : "root" });
      return;
    }
    setSearching(true);
    fetchFiles({ q });
  };

  const openFolder = (folder: { id: string; name: string } | null) => {
    setSearching(false);
    setQuery("");
    if (folder === null) {
      setPath([]);
      fetchFiles({ folderId: "root" });
      return;
    }
    // Clicking a breadcrumb ancestor truncates the trail to it.
    const idx = path.findIndex((p) => p.id === folder.id);
    const next = idx >= 0 ? path.slice(0, idx + 1) : [...path, folder];
    setPath(next);
    fetchFiles({ folderId: folder.id });
  };

  return (
    <div className="w-[400px] border border-[var(--color-border)] bg-white rounded-[12px] shadow-sm overflow-hidden flex flex-col h-[500px]">
      <div className="p-4 border-b border-[var(--color-border)] bg-[var(--color-background)]">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-[var(--color-navy)]">{t("picker")}</h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1 -mr-1 text-[var(--color-text-muted)] hover:text-[var(--color-navy)] transition-colors"
            title={t("close")}
          >
            <X size={16} />
          </button>
        </div>
        <div className="mt-2 flex gap-2">
          <input
            type="text"
            className="flex-1 rounded-[8px] border border-[var(--color-border)] px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            placeholder={t("search")}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && runSearch()}
          />
          <Button size="sm" onClick={runSearch}>{t("searchButton")}</Button>
        </div>
        {/* Breadcrumbs (hidden while a global search is showing) */}
        {!searching && (
          <div className="mt-2 flex items-center flex-wrap gap-1 text-xs text-[var(--color-text-muted)]">
            <button
              type="button"
              onClick={() => openFolder(null)}
              className={`flex items-center gap-1 hover:text-[var(--color-primary)] ${path.length === 0 ? "text-[var(--color-navy)] font-medium" : ""}`}
            >
              <Home size={11} /> {t("myDrive")}
            </button>
            {path.map((p, i) => (
              <span key={p.id} className="flex items-center gap-1">
                <ChevronRight size={11} />
                <button
                  type="button"
                  onClick={() => openFolder(p)}
                  className={`hover:text-[var(--color-primary)] truncate max-w-[110px] ${i === path.length - 1 ? "text-[var(--color-navy)] font-medium" : ""}`}
                >
                  {p.name}
                </button>
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {loading ? (
          <div className="flex justify-center items-center h-full">
            <Loader2 className="h-6 w-6 animate-spin text-[var(--color-primary)]" />
          </div>
        ) : files.length === 0 ? (
          <div className="text-center text-sm text-[var(--color-text-muted)] mt-10">{t("noDocuments")}</div>
        ) : (
          <ul className="space-y-1">
            {files.map(f => (
              <li key={f.id}>
                <button
                  onClick={() => f.mimeType === FOLDER_MIME ? openFolder({ id: f.id, name: f.name }) : onSelect(f)}
                  className="w-full flex items-center gap-3 rounded-[8px] p-2 hover:bg-[var(--color-navy-light)] text-left transition-colors"
                >
                  {f.mimeType === FOLDER_MIME ? (
                    <Folder className="w-5 h-5 text-[var(--color-navy)] shrink-0" />
                  ) : f.iconLink ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={f.iconLink} alt="icon" className="w-5 h-5"/>
                  ) : (
                    <FileText className="w-5 h-5 text-[var(--color-primary)] shrink-0" />
                  )}
                  <span className="text-sm font-medium text-[var(--color-text-primary)] truncate">{f.name}</span>
                  {f.mimeType === FOLDER_MIME && <ChevronRight size={14} className="ml-auto shrink-0 text-[var(--color-text-muted)]" />}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
