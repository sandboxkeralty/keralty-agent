"use client";

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslations } from 'next-intl';
import { PenLine, Check, Trash2, Pencil, Loader2, Upload, ChevronDown, ChevronUp, X } from 'lucide-react';
import { apiFetch, apiJson, UnauthorizedError } from '@/lib/api';

export interface WritingStyle {
  style_id: string;
  name: string;
  description?: string;
  style_guide: string;
  source: 'preset' | 'custom';
}

interface StylesResponse {
  presets: WritingStyle[];
  styles: WritingStyle[];
  default_style_id: string | null;
}

const GUIDE_MAX = 2000;
const NAME_MAX = 60;
const MAX_FILES = 5;

export default function EstilosPage() {
  const t = useTranslations('style');
  const [data, setData] = useState<StylesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [savingDefault, setSavingDefault] = useState(false);

  // create wizard state
  const [files, setFiles] = useState<File[]>([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [draftGuide, setDraftGuide] = useState<string | null>(null);
  const [draftName, setDraftName] = useState('');
  const [draftDesc, setDraftDesc] = useState('');
  const [sampleFilenames, setSampleFilenames] = useState<string[]>([]);
  const [wizardError, setWizardError] = useState('');
  const [saving, setSaving] = useState(false);

  // edit state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [editGuide, setEditGuide] = useState('');

  const fileInputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await apiJson<StylesResponse>('/api/style');
      setData(res);
    } catch (e) {
      if (e instanceof UnauthorizedError) return;
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const setDefault = async (styleId: string | null) => {
    if (!data || savingDefault) return;
    setSavingDefault(true);
    try {
      await apiJson('/api/style/default', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ style_id: styleId }),
      });
      setData({ ...data, default_style_id: styleId });
    } catch (e) {
      if (e instanceof UnauthorizedError) return;
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSavingDefault(false);
    }
  };

  const handleFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(e.target.files || []);
    setWizardError('');
    setFiles(prev => {
      const merged = [...prev];
      for (const f of picked) {
        if (merged.length >= MAX_FILES) { setWizardError(t('errorTooManyFiles')); break; }
        if (!merged.some(m => m.name === f.name && m.size === f.size)) merged.push(f);
      }
      return merged;
    });
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const analyze = async () => {
    if (files.length === 0 || analyzing) return;
    setAnalyzing(true);
    setWizardError('');
    try {
      const form = new FormData();
      files.forEach(f => form.append('files', f));
      const res = await apiFetch('/api/style/analyze', { method: 'POST', body: form });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || t('errorAnalyze'));
      setDraftGuide(body.style_guide);
      setSampleFilenames(body.sample_filenames || []);
    } catch (e) {
      if (e instanceof UnauthorizedError) return;
      setWizardError(e instanceof Error ? e.message : String(e));
    } finally {
      setAnalyzing(false);
    }
  };

  const saveStyle = async () => {
    if (!draftGuide || !draftName.trim() || saving) return;
    setSaving(true);
    setWizardError('');
    try {
      await apiJson('/api/style', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: draftName.trim(),
          description: draftDesc.trim(),
          style_guide: draftGuide,
          sample_filenames: sampleFilenames,
        }),
      });
      setFiles([]); setDraftGuide(null); setDraftName(''); setDraftDesc(''); setSampleFilenames([]);
      await load();
    } catch (e) {
      if (e instanceof UnauthorizedError) return;
      setWizardError(e instanceof Error ? e.message : t('errorSave'));
    } finally {
      setSaving(false);
    }
  };

  const saveEdit = async (styleId: string) => {
    try {
      await apiJson(`/api/style/${styleId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: editName.trim(), style_guide: editGuide }),
      });
      setEditingId(null);
      await load();
    } catch (e) {
      if (e instanceof UnauthorizedError) return;
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const remove = async (styleId: string) => {
    if (!window.confirm(t('confirmDelete'))) return;
    try {
      await apiJson(`/api/style/${styleId}`, { method: 'DELETE' });
      await load();
    } catch (e) {
      if (e instanceof UnauthorizedError) return;
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const defaultId = data?.default_style_id ?? null;

  const styleRow = (s: WritingStyle) => (
    <div key={s.style_id} className="border border-[var(--color-border)] rounded-[12px] p-4 bg-white">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setDefault(defaultId === s.style_id ? null : s.style_id)}
          disabled={savingDefault}
          className={`w-5 h-5 rounded-full border flex items-center justify-center shrink-0 transition-colors ${defaultId === s.style_id ? 'bg-[var(--color-primary)] border-[var(--color-primary)] text-white' : 'border-gray-300 hover:border-[var(--color-primary)]'}`}
          title={t('setDefault')}
        >
          {defaultId === s.style_id && <Check size={12} />}
        </button>
        <span className="font-medium text-sm text-[var(--color-text-primary)]">{s.name}</span>
        {s.source === 'preset' && (
          <span className="text-[10px] uppercase tracking-wide bg-[var(--color-primary-light)] text-[var(--color-navy)] px-2 py-0.5 rounded-full">{t('presetBadge')}</span>
        )}
        {defaultId === s.style_id && (
          <span className="text-[10px] text-[var(--color-primary)]">{t('isDefault')}</span>
        )}
        <div className="ml-auto flex items-center gap-1">
          {s.source === 'custom' && (
            <>
              <button type="button" onClick={() => { setEditingId(s.style_id); setEditName(s.name); setEditGuide(s.style_guide); }} className="p-1.5 text-gray-400 hover:text-[var(--color-navy)]" title={t('edit')}>
                <Pencil size={14} />
              </button>
              <button type="button" onClick={() => remove(s.style_id)} className="p-1.5 text-gray-400 hover:text-red-500" title={t('delete')}>
                <Trash2 size={14} />
              </button>
            </>
          )}
          <button type="button" onClick={() => setExpanded(expanded === s.style_id ? null : s.style_id)} className="p-1.5 text-gray-400 hover:text-[var(--color-navy)]">
            {expanded === s.style_id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>
      {s.description && <p className="text-xs text-[var(--color-text-secondary)] mt-1 ml-7">{s.description}</p>}
      {expanded === s.style_id && editingId !== s.style_id && (
        <pre className="mt-3 ml-7 text-xs whitespace-pre-wrap text-[var(--color-text-secondary)] bg-gray-50 rounded-[8px] p-3">{s.style_guide}</pre>
      )}
      {editingId === s.style_id && (
        <div className="mt-3 ml-7 space-y-2">
          <input value={editName} onChange={e => setEditName(e.target.value)} maxLength={NAME_MAX}
            className="w-full text-sm border border-[var(--color-border)] rounded-[8px] px-3 py-2" />
          <textarea value={editGuide} onChange={e => setEditGuide(e.target.value)} maxLength={GUIDE_MAX} rows={8}
            className="w-full text-xs border border-[var(--color-border)] rounded-[8px] px-3 py-2 font-mono" />
          <div className="flex gap-2">
            <button type="button" onClick={() => saveEdit(s.style_id)} className="text-xs bg-[var(--color-primary)] text-white px-3 py-1.5 rounded-[8px] hover:bg-[var(--color-primary-dark)]">{t('save')}</button>
            <button type="button" onClick={() => setEditingId(null)} className="text-xs px-3 py-1.5 rounded-[8px] border border-[var(--color-border)]">{t('cancel')}</button>
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-3xl mx-auto space-y-8">
        <div>
          <h1 className="text-xl font-semibold text-[var(--color-navy)] flex items-center gap-2">
            <PenLine size={20} /> {t('pageTitle')}
          </h1>
          <p className="text-sm text-[var(--color-text-secondary)] mt-1">{t('pageSubtitle')}</p>
        </div>

        {error && <div className="text-sm text-red-500 border border-red-200 bg-red-50 rounded-[8px] px-4 py-2">{error}</div>}

        {loading ? (
          <div className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]"><Loader2 size={16} className="animate-spin" /> {t('loading')}</div>
        ) : data && (
          <>
            <section className="space-y-3">
              <h2 className="text-sm font-semibold text-[var(--color-text-primary)]">{t('defaultSection')}</h2>
              <div className="border border-[var(--color-border)] rounded-[12px] p-4 bg-white flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setDefault(null)}
                  disabled={savingDefault}
                  className={`w-5 h-5 rounded-full border flex items-center justify-center shrink-0 ${defaultId === null ? 'bg-[var(--color-primary)] border-[var(--color-primary)] text-white' : 'border-gray-300 hover:border-[var(--color-primary)]'}`}
                >
                  {defaultId === null && <Check size={12} />}
                </button>
                <span className="text-sm">{t('noStyle')}</span>
              </div>
              {data.presets.map(styleRow)}
            </section>

            <section className="space-y-3">
              <h2 className="text-sm font-semibold text-[var(--color-text-primary)]">{t('myStyles')}</h2>
              {data.styles.length === 0
                ? <p className="text-xs text-[var(--color-text-secondary)]">{t('empty')}</p>
                : data.styles.map(styleRow)}
            </section>

            <section className="space-y-3">
              <h2 className="text-sm font-semibold text-[var(--color-text-primary)]">{t('createTitle')}</h2>
              <div className="border border-[var(--color-border)] rounded-[12px] p-4 bg-white space-y-3">
                {draftGuide === null ? (
                  <>
                    <p className="text-xs text-[var(--color-text-secondary)]">{t('uploadHint')}</p>
                    <input ref={fileInputRef} type="file" multiple accept=".pdf,.docx,.doc,.txt,.csv,.md" onChange={handleFiles} className="hidden" id="style-files" />
                    <div className="flex items-center flex-wrap gap-2">
                      <label htmlFor="style-files" className="inline-flex items-center gap-2 text-xs border border-[var(--color-border)] rounded-[8px] px-3 py-2 cursor-pointer hover:bg-gray-50">
                        <Upload size={13} /> {t('chooseFiles')}
                      </label>
                      {files.map(f => (
                        <span key={f.name + f.size} className="flex items-center gap-1.5 text-xs bg-[var(--color-primary-light)] text-[var(--color-navy)] px-2 py-1 rounded-full">
                          {f.name}
                          <button type="button" onClick={() => setFiles(prev => prev.filter(x => x !== f))} className="hover:text-red-500"><X size={11} /></button>
                        </span>
                      ))}
                    </div>
                    <button
                      type="button"
                      onClick={analyze}
                      disabled={files.length === 0 || analyzing}
                      className="inline-flex items-center gap-2 text-sm bg-[var(--color-primary)] text-white px-4 py-2 rounded-[8px] hover:bg-[var(--color-primary-dark)] disabled:opacity-50"
                    >
                      {analyzing ? <><Loader2 size={14} className="animate-spin" /> {t('analyzing')}</> : t('analyze')}
                    </button>
                  </>
                ) : (
                  <>
                    <p className="text-xs text-[var(--color-text-secondary)]">{t('reviewHint')}</p>
                    <input value={draftName} onChange={e => setDraftName(e.target.value)} maxLength={NAME_MAX}
                      placeholder={t('namePlaceholder')}
                      className="w-full text-sm border border-[var(--color-border)] rounded-[8px] px-3 py-2" />
                    <input value={draftDesc} onChange={e => setDraftDesc(e.target.value)} maxLength={200}
                      placeholder={t('descriptionPlaceholder')}
                      className="w-full text-sm border border-[var(--color-border)] rounded-[8px] px-3 py-2" />
                    <textarea value={draftGuide} onChange={e => setDraftGuide(e.target.value)} maxLength={GUIDE_MAX} rows={10}
                      className="w-full text-xs border border-[var(--color-border)] rounded-[8px] px-3 py-2 font-mono" />
                    <p className="text-[10px] text-[var(--color-text-secondary)] text-right">{draftGuide.length}/{GUIDE_MAX}</p>
                    <div className="flex gap-2">
                      <button type="button" onClick={saveStyle} disabled={!draftName.trim() || saving}
                        className="inline-flex items-center gap-2 text-sm bg-[var(--color-primary)] text-white px-4 py-2 rounded-[8px] hover:bg-[var(--color-primary-dark)] disabled:opacity-50">
                        {saving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />} {t('approveSave')}
                      </button>
                      <button type="button" onClick={() => setDraftGuide(null)} className="text-sm px-4 py-2 rounded-[8px] border border-[var(--color-border)] hover:bg-gray-50">{t('back')}</button>
                    </div>
                  </>
                )}
                {wizardError && <p className="text-xs text-red-500">{wizardError}</p>}
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  );
}
