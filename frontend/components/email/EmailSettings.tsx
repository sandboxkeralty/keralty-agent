"use client";

import React, { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Loader2, X } from 'lucide-react';
import { apiJson, UnauthorizedError } from '@/lib/api';
import { EmailSettingsData } from './types';

interface Props {
  initial: EmailSettingsData;
  locale: string;
  onClose: () => void;
  onSaved: (saved: EmailSettingsData) => void;
}

export default function EmailSettings({ initial, locale, onClose, onSaved }: Props) {
  const t = useTranslations('email');
  const [windowDays, setWindowDays] = useState(initial.window_days);
  const [followupDays, setFollowupDays] = useState(initial.followup_days);
  const [digestEmail, setDigestEmail] = useState(initial.digest_email_enabled);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const data = await apiJson<{ settings: EmailSettingsData }>('/api/email/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          window_days: windowDays,
          followup_days: followupDays,
          digest_email_enabled: digestEmail,
          locale,
        }),
      });
      onSaved(data.settings);
      onClose();
    } catch (e) {
      if (e instanceof UnauthorizedError) return;
      setError(t('settingsError'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div
        className="bg-white rounded-[12px] shadow-lg border border-[var(--color-border)] p-5 w-full max-w-sm mx-4"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-bold text-[var(--color-navy)]">{t('settings')}</h2>
          <button type="button" onClick={onClose} className="text-[var(--color-text-muted)] hover:text-[var(--color-navy)]">
            <X className="h-4 w-4" />
          </button>
        </div>

        <label className="block text-sm text-[var(--color-text-secondary)] mb-4">
          {t('windowDays')}: <span className="font-semibold text-[var(--color-navy)]">{windowDays}</span>
          <input
            type="range" min={3} max={14} value={windowDays}
            onChange={e => setWindowDays(Number(e.target.value))}
            className="w-full mt-1 accent-[var(--color-primary)]"
          />
        </label>

        <label className="block text-sm text-[var(--color-text-secondary)] mb-4">
          {t('followupDays')}: <span className="font-semibold text-[var(--color-navy)]">{followupDays}</span>
          <input
            type="range" min={1} max={14} value={followupDays}
            onChange={e => setFollowupDays(Number(e.target.value))}
            className="w-full mt-1 accent-[var(--color-primary)]"
          />
        </label>

        <label className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)] mb-4 cursor-pointer">
          <input
            type="checkbox"
            checked={digestEmail}
            onChange={e => setDigestEmail(e.target.checked)}
            className="accent-[var(--color-primary)]"
          />
          {t('digestEmailEnabled')}
        </label>

        {error && <p className="text-xs text-red-600 mb-3">{error}</p>}

        <div className="flex justify-end gap-2">
          <button
            type="button" onClick={onClose}
            className="text-sm px-3 py-1.5 border border-[var(--color-border)] rounded-[6px] text-[var(--color-text-secondary)]"
          >
            {t('cancel')}
          </button>
          <button
            type="button" onClick={save} disabled={saving}
            className="flex items-center gap-1.5 text-sm px-3 py-1.5 bg-[var(--color-primary)] text-white rounded-[6px] hover:bg-[var(--color-primary-dark)] disabled:opacity-50"
          >
            {saving && <Loader2 className="h-3 w-3 animate-spin" />} {t('save')}
          </button>
        </div>
      </div>
    </div>
  );
}
