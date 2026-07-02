import React from 'react';
import { Button } from '../shared/Button';
import { useTranslations } from 'next-intl';
import { FileText, Check, X } from 'lucide-react';

export interface ApprovalCardProps {
  title: string;
  documentId: string;
  diff: string;
  onApprove: () => void;
  onReject: () => void;
}

export function ApprovalCard({ title, documentId, diff, onApprove, onReject }: ApprovalCardProps) {
  const t = useTranslations('chat');
  return (
    <div className="border border-[var(--color-primary)]/30 bg-[var(--color-primary-light)]/30 rounded-[12px] p-4 my-2">
      <div className="flex items-center gap-2 mb-2">
        <FileText size={18} className="text-[var(--color-primary)]" />
        <h4 className="font-semibold text-[var(--color-navy)]">{title}</h4>
      </div>
      <div className="text-sm text-[var(--color-text-primary)] mb-4 bg-white p-3 rounded border border-white/50 max-h-48 overflow-y-auto">
        <pre className="whitespace-pre-wrap font-mono text-xs">{diff}</pre>
      </div>
      <div className="flex gap-2">
        <Button size="sm" onClick={onApprove} className="bg-green-600 hover:bg-green-700 border-none text-white flex items-center gap-1">
          <Check size={14} /> {t('approve')}
        </Button>
        <Button size="sm" onClick={onReject} variant="secondary" className="text-red-600 border-red-200 hover:bg-red-50 flex items-center gap-1 bg-white">
          <X size={14} /> {t('reject')}
        </Button>
      </div>
    </div>
  );
}
