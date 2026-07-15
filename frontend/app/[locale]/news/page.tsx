"use client";

import React, { useEffect, useMemo, useState } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { Newspaper, Loader2, RefreshCw, ExternalLink } from 'lucide-react';
import { apiFetch, UnauthorizedError } from '@/lib/api';

type Region = 'pais_vasco' | 'espana';

interface NewsItem {
  id: string;
  source_id: string;
  source_name: string;
  region: Region;
  title: string;
  summary: string;
  link: string;
  published_at?: string;
  image_url?: string;
}

interface NewsResponse {
  generated_at: string;
  items: NewsItem[];
  warnings: string[];
}

const SOURCE_COLORS: Record<string, string> = {
  diariovasco: 'bg-emerald-100 text-emerald-700',
  eitb: 'bg-purple-100 text-purple-700',
  elcorreo: 'bg-blue-100 text-blue-700',
  elcorreo_alava: 'bg-sky-100 text-sky-700',
  elpais: 'bg-slate-200 text-slate-700',
  elmundo: 'bg-amber-100 text-amber-700',
};

function relativeTime(iso: string | undefined, locale: string): string {
  if (!iso) return '';
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' });
  if (mins < 60) return rtf.format(-mins, 'minute');
  const hours = Math.round(mins / 60);
  if (hours < 24) return rtf.format(-hours, 'hour');
  return rtf.format(-Math.round(hours / 24), 'day');
}

export default function NewsPage() {
  const t = useTranslations('news');
  const locale = useLocale();
  const [data, setData] = useState<NewsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [region, setRegion] = useState<Region | 'all'>('all');
  const [sourceFilter, setSourceFilter] = useState<string | null>(null);

  const fetchNews = async (refresh = false) => {
    refresh ? setRefreshing(true) : setLoading(true);
    try {
      const res = await apiFetch('/api/news' + (refresh ? '/refresh' : ''), {
        method: refresh ? 'POST' : 'GET',
      });
      if (res.ok) setData(await res.json());
    } catch (e) {
      if (!(e instanceof UnauthorizedError)) console.error(e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { fetchNews(); }, []);

  const visible = useMemo(() => {
    let items = data?.items || [];
    if (region !== 'all') items = items.filter(i => i.region === region);
    if (sourceFilter) items = items.filter(i => i.source_id === sourceFilter);
    return [...items].sort((a, b) => (b.published_at || '').localeCompare(a.published_at || ''));
  }, [data, region, sourceFilter]);

  const sourcesInView = useMemo(() => {
    const items = (data?.items || []).filter(i => region === 'all' || i.region === region);
    const map = new Map<string, { name: string; count: number }>();
    for (const i of items) {
      const e = map.get(i.source_id);
      map.set(i.source_id, { name: i.source_name, count: (e?.count || 0) + 1 });
    }
    return Array.from(map.entries());
  }, [data, region]);

  const failedNames = useMemo(() => {
    if (!data?.warnings?.length) return '';
    const byId = new Map((data.items || []).map(i => [i.source_id, i.source_name]));
    return data.warnings.map(w => byId.get(w) || w).join(', ');
  }, [data]);

  const [featured, ...rest] = visible;

  return (
    <div className="p-6 max-w-5xl mx-auto w-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Newspaper className="h-6 w-6 text-[var(--color-primary)]" />
          <div>
            <h1 className="text-2xl font-bold text-[var(--color-navy)]">{t('title')}</h1>
            {data?.generated_at && (
              <p className="text-xs text-[var(--color-text-muted)]">
                {t('updated')} {relativeTime(data.generated_at, locale)}
              </p>
            )}
          </div>
        </div>
        <button
          onClick={() => fetchNews(true)}
          disabled={refreshing}
          className="flex items-center gap-2 px-3 py-2 text-sm text-[var(--color-primary)] hover:bg-[var(--color-primary-light)] rounded-[8px] transition-colors disabled:opacity-50"
        >
          {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          {t('refresh')}
        </button>
      </div>

      {failedNames && (
        <div className="mb-4 text-xs text-orange-700 bg-orange-50 border border-orange-200 rounded-[8px] px-3 py-2">
          {t('sourceWarning', { sources: failedNames })}
        </div>
      )}

      {/* Region tabs */}
      <div className="flex gap-1 border-b border-[var(--color-border)] mb-3">
        {([['all', t('regionAll')], ['pais_vasco', t('regionBasque')], ['espana', t('regionSpain')]] as [Region | 'all', string][]).map(([id, label]) => (
          <button
            key={id}
            onClick={() => { setRegion(id); setSourceFilter(null); }}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${region === id ? 'border-[var(--color-primary)] text-[var(--color-primary)]' : 'border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-navy)]'}`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Source chips */}
      {sourcesInView.length > 1 && (
        <div className="flex items-center flex-wrap gap-2 mb-4">
          {sourcesInView.map(([id, s]) => (
            <button
              key={id}
              type="button"
              onClick={() => setSourceFilter(prev => prev === id ? null : id)}
              className={`text-[11px] font-semibold px-2.5 py-1 rounded-full border transition-colors ${SOURCE_COLORS[id] || 'bg-gray-100 text-gray-600'} ${sourceFilter === id ? 'ring-2 ring-[var(--color-navy)]/40' : 'opacity-80 hover:opacity-100'}`}
            >
              {s.name} · {s.count}
            </button>
          ))}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-48 gap-2 text-[var(--color-text-muted)]">
          <Loader2 className="h-4 w-4 animate-spin" /> {t('loading')}
        </div>
      ) : visible.length === 0 ? (
        <div className="p-10 text-center bg-white border border-[var(--color-border)] rounded-[12px]">
          <Newspaper className="h-10 w-10 text-[var(--color-text-muted)] mx-auto mb-3" />
          <p className="text-sm text-[var(--color-text-muted)]">{t('empty')}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {/* Featured card */}
          {featured && (
            <a
              href={featured.link}
              target="_blank"
              rel="noopener noreferrer"
              className="group block bg-white border border-[var(--color-border)] rounded-[12px] shadow-sm p-5 hover:border-[var(--color-primary)]/50 transition-colors"
            >
              <div className="flex gap-5">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full ${SOURCE_COLORS[featured.source_id] || 'bg-gray-100 text-gray-600'}`}>
                      {featured.source_name}
                    </span>
                    <span className="text-xs text-[var(--color-text-muted)]">{relativeTime(featured.published_at, locale)}</span>
                  </div>
                  <h2 className="text-lg font-bold text-[var(--color-navy)] group-hover:text-[var(--color-primary)] transition-colors">
                    {featured.title}
                  </h2>
                  <p className="text-sm text-[var(--color-text-secondary)] mt-1.5">{featured.summary}</p>
                  <span className="inline-flex items-center gap-1 text-xs text-[var(--color-primary)] mt-2">
                    {t('readAt', { source: featured.source_name })} <ExternalLink size={11} />
                  </span>
                </div>
                {featured.image_url && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={featured.image_url} alt="" className="hidden sm:block w-48 h-32 object-cover rounded-[8px] shrink-0" />
                )}
              </div>
            </a>
          )}

          {/* Rest */}
          <div className="bg-white border border-[var(--color-border)] rounded-[12px] shadow-sm divide-y divide-[var(--color-border)]">
            {rest.map(item => (
              <a
                key={item.id}
                href={item.link}
                target="_blank"
                rel="noopener noreferrer"
                className="group flex gap-4 p-4 hover:bg-[var(--color-background)] transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded-full ${SOURCE_COLORS[item.source_id] || 'bg-gray-100 text-gray-600'}`}>
                      {item.source_name}
                    </span>
                    <span className="text-xs text-[var(--color-text-muted)]">{relativeTime(item.published_at, locale)}</span>
                    <ExternalLink size={11} className="text-[var(--color-text-muted)] opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                  <p className="text-sm font-semibold text-[var(--color-text-primary)] group-hover:text-[var(--color-primary)] transition-colors">
                    {item.title}
                  </p>
                  <p className="text-xs text-[var(--color-text-secondary)] mt-0.5 line-clamp-2">{item.summary}</p>
                </div>
                {item.image_url && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={item.image_url} alt="" className="hidden sm:block w-28 h-20 object-cover rounded-[8px] shrink-0" />
                )}
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
