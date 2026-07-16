"use client";

// In-app weekly digest (Phase 3). Collapsible; fetches the latest stored
// digest on first expand. The email delivery of this same digest is per-user
// opt-out-able in EmailSettings.

import React, { useState } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { ChevronDown, ChevronRight, Loader2, Newspaper } from 'lucide-react';
import { apiJson, UnauthorizedError } from '@/lib/api';

interface DigestSectionItem {
  subject: string;
  from?: string;
  to?: string;
  resumen?: string;
  accion_sugerida?: string;
  days_without_reply?: number | null;
}

interface Digest {
  narrative: string;
  week_start: string;
  week_end: string;
  sections: {
    totals: { total: number; criticos: number; pendientes: number; seguimiento: number; resueltos: number };
    criticos: DigestSectionItem[];
    pendientes: DigestSectionItem[];
    seguimiento: DigestSectionItem[];
  };
}

export default function DigestView() {
  const t = useTranslations('email');
  const locale = useLocale();
  const [open, setOpen] = useState(false);
  const [digest, setDigest] = useState<Digest | null | undefined>(undefined); // undefined = not fetched
  const [loading, setLoading] = useState(false);

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (next && digest === undefined) {
      setLoading(true);
      try {
        const data = await apiJson<{ digest: Digest | null }>('/api/email/digest');
        setDigest(data.digest);
      } catch (e) {
        if (!(e instanceof UnauthorizedError)) setDigest(null);
      } finally {
        setLoading(false);
      }
    }
  };

  const SECTION_LABELS: [keyof Digest['sections'] & string, string][] = [
    ['criticos', t('tabCritical')],
    ['pendientes', t('tabPending')],
    ['seguimiento', t('tabFollowup')],
  ];

  return (
    <div className="mb-4 bg-white border border-[var(--color-border)] rounded-[12px] shadow-sm">
      <button
        type="button"
        onClick={toggle}
        className="w-full flex items-center gap-2 p-3 text-sm font-medium text-[var(--color-navy)]"
      >
        {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        <Newspaper className="h-4 w-4 text-[var(--color-primary)]" />
        {t('digestTitle')}
      </button>
      {open && (
        <div className="px-4 pb-4">
          {loading ? (
            <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)]">
              <Loader2 className="h-3 w-3 animate-spin" /> {t('loadingEmails')}
            </div>
          ) : !digest ? (
            <p className="text-xs text-[var(--color-text-muted)]">{t('digestEmpty')}</p>
          ) : (
            <div>
              <p className="text-xs text-[var(--color-text-muted)] mb-2">
                {t('digestWeekOf', {
                  from: new Date(digest.week_start).toLocaleDateString(locale),
                  to: new Date(digest.week_end).toLocaleDateString(locale),
                })}
              </p>
              <p className="text-sm text-[var(--color-text-secondary)] mb-3">{digest.narrative}</p>
              {SECTION_LABELS.map(([key, label]) => {
                const items = digest.sections[key] as DigestSectionItem[];
                if (!items?.length) return null;
                return (
                  <div key={key} className="mb-2">
                    <p className="text-xs font-semibold text-[var(--color-navy)] uppercase mb-1">{label} · {items.length}</p>
                    <ul className="text-xs text-[var(--color-text-secondary)] space-y-0.5">
                      {items.slice(0, 5).map((item, i) => (
                        <li key={i} className="truncate">
                          • {item.subject || t('noSubject')}
                          {key === 'seguimiento' && typeof item.days_without_reply === 'number'
                            ? ` — ${t('daysWithoutReply', { days: item.days_without_reply })}`
                            : item.accion_sugerida ? ` — ${item.accion_sugerida}` : ''}
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
