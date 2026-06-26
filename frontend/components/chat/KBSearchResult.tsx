import React from 'react';

interface KBSearchResultProps {
  title: string;
  category: string;
  effectiveDate: string;
  excerpt: string;
}

export function KBSearchResult({ title, category, effectiveDate, excerpt }: KBSearchResultProps) {
  return (
    <div className="bg-white border border-[var(--color-border)] rounded-lg p-4 shadow-sm my-2">
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-semibold text-[var(--color-navy)]">{title}</h4>
        <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded-full">{category}</span>
      </div>
      <p className="text-sm text-[var(--color-text-muted)] mb-2">{excerpt}</p>
      <div className="text-xs text-gray-400">
        Effective: {effectiveDate}
      </div>
    </div>
  );
}
