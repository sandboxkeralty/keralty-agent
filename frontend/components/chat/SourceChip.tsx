import React from 'react';
import { ExternalLink } from 'lucide-react';

export function SourceChip({ title, url }: { title: string, url: string }) {
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" 
       className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[12px] bg-[var(--color-navy-light)] text-[var(--color-primary)] hover:bg-[var(--color-primary)] hover:text-white transition-colors text-xs font-medium border border-[var(--color-primary)]/20">
      <span>{title}</span>
      <ExternalLink size={10} />
    </a>
  );
}
