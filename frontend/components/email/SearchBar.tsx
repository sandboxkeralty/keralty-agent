"use client";

// Global Gmail search (Phase 2). Results are message hits joined with stored
// thread state — analyzed threads show their facet badges; unanalyzed ones are
// shown raw with a "sin analizar" tag (search never triggers analysis).

import React, { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Loader2, Search, X } from 'lucide-react';
import { apiJson, UnauthorizedError } from '@/lib/api';
import { PRIORITY_KEY, PRIORITY_STYLES, ThreadState } from './types';

interface SearchHit {
  id: string;
  thread_id: string;
  subject: string;
  from: string;
  date: string;
  snippet: string;
  state: ThreadState | null;
}

export default function SearchBar() {
  const t = useTranslations('email');
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    try {
      const data = await apiJson<{ results: SearchHit[] }>(
        `/api/email/search?q=${encodeURIComponent(query)}&max=25`);
      setResults(data.results);
    } catch (e) {
      if (e instanceof UnauthorizedError) return;
      setError(e instanceof Error ? e.message : t('scanFailed'));
    } finally {
      setSearching(false);
    }
  };

  const clear = () => { setResults(null); setQuery(''); setError(null); };

  return (
    <div className="mb-4">
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--color-text-muted)]" />
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') run(); }}
            placeholder={t('searchPlaceholder')}
            className="w-full text-sm border border-[var(--color-border)] rounded-[8px] pl-8 pr-3 py-2 bg-white"
          />
        </div>
        <button
          type="button" onClick={run} disabled={searching || !query.trim()}
          className="flex items-center gap-1.5 text-sm px-3 py-2 bg-[var(--color-primary)] text-white rounded-[8px] hover:bg-[var(--color-primary-dark)] disabled:opacity-50"
        >
          {searching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
          {t('search')}
        </button>
        {results !== null && (
          <button type="button" onClick={clear}
            className="flex items-center gap-1 text-sm px-2 py-2 text-[var(--color-text-muted)] hover:text-[var(--color-navy)]">
            <X className="h-3.5 w-3.5" /> {t('clearFilter')}
          </button>
        )}
      </div>

      {error && <p className="text-xs text-red-600 mt-2">{error}</p>}

      {results !== null && (
        <div className="mt-2 bg-white border border-[var(--color-border)] rounded-[12px] shadow-sm">
          {results.length === 0 ? (
            <p className="p-4 text-sm text-[var(--color-text-muted)] text-center">{t('noResults')}</p>
          ) : (
            <ul className="divide-y divide-[var(--color-border)]">
              {results.map(hit => (
                <li key={hit.id} className="p-3">
                  <div className="flex justify-between items-start gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="font-semibold text-xs text-[var(--color-navy)] truncate max-w-56">{hit.from}</span>
                      {hit.state ? (
                        <span className={`shrink-0 text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded-full ${PRIORITY_STYLES[hit.state.prioridad]}`}>
                          {t(PRIORITY_KEY[hit.state.prioridad])}
                        </span>
                      ) : (
                        <span className="shrink-0 text-[10px] uppercase px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-500">
                          {t('notAnalyzed')}
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-[var(--color-text-muted)] shrink-0">{hit.date}</span>
                  </div>
                  <p className="text-sm font-medium text-[var(--color-text-primary)]">{hit.subject || t('noSubject')}</p>
                  <p className="text-xs text-[var(--color-text-muted)] mt-0.5 line-clamp-1">
                    {hit.state?.resumen || hit.snippet}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
