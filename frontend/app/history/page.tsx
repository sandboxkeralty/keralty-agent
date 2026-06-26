import React from 'react';

export default function HistoryPage() {
  return (
    <div className="p-8 max-w-4xl mx-auto w-full">
      <h1 className="text-2xl font-bold text-[var(--color-navy)] mb-6">Historial de Sesiones</h1>
      <div className="bg-white border border-[var(--color-border)] rounded-[12px] shadow-sm p-6">
        <p className="text-[var(--color-text-muted)]">Cargando historial...</p>
      </div>
    </div>
  );
}
