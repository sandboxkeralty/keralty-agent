"use client";
import * as React from "react";
import { useState, useEffect } from "react";
import { Button } from "../shared/Button";
import { FileText, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";

export interface DriveFile {
  id: string;
  name: string;
  mimeType: string;
  iconLink?: string;
}

export function DocumentPicker({ onSelect }: { onSelect: (file: DriveFile) => void }) {
  const t = useTranslations("documents");
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState("");

  const fetchFiles = async (q: string = "") => {
    setLoading(true);
    try {
      // Note: NEXT_PUBLIC_API_URL should be used instead of hardcoding localhost
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const token = localStorage.getItem('keralty_token') || 'test-token';
      const res = await fetch(`${apiUrl}/documents?q=${encodeURIComponent(q)}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const data = await res.json();
      setFiles(data.files || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFiles();
  }, []);

  return (
    <div className="w-[400px] border border-[var(--color-border)] bg-white rounded-[12px] shadow-sm overflow-hidden flex flex-col h-[500px]">
      <div className="p-4 border-b border-[var(--color-border)] bg-[var(--color-background)]">
        <h3 className="font-semibold text-[var(--color-navy)]">{t("picker")}</h3>
        <div className="mt-2 flex gap-2">
          <input
            type="text"
            className="flex-1 rounded-[8px] border border-[var(--color-border)] px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            placeholder={t("search")}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && fetchFiles(query)}
          />
          <Button size="sm" onClick={() => fetchFiles(query)}>Buscar</Button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {loading ? (
          <div className="flex justify-center items-center h-full">
            <Loader2 className="h-6 w-6 animate-spin text-[var(--color-primary)]" />
          </div>
        ) : files.length === 0 ? (
          <div className="text-center text-sm text-[var(--color-text-muted)] mt-10">No documents found</div>
        ) : (
          <ul className="space-y-1">
            {files.map(f => (
              <li key={f.id}>
                <button 
                  onClick={() => onSelect(f)}
                  className="w-full flex items-center gap-3 rounded-[8px] p-2 hover:bg-[var(--color-navy-light)] text-left transition-colors"
                >
                  {f.iconLink ? <img src={f.iconLink} alt="icon" className="w-5 h-5"/> : <FileText className="w-5 h-5 text-[var(--color-primary)]" />}
                  <span className="text-sm font-medium text-[var(--color-text-primary)] truncate">{f.name}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
