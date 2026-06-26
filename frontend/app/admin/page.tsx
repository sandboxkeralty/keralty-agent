import React from 'react';

export default function AdminPage() {
  const adminEnabled = process.env.NEXT_PUBLIC_ADMIN_ENABLED === 'true';

  if (!adminEnabled) {
    return (
      <div className="p-8 max-w-4xl mx-auto w-full text-center">
        <h1 className="text-2xl font-bold text-red-600">Acceso Denegado</h1>
        <p className="text-[var(--color-text-muted)] mt-2">El panel de administración está deshabilitado.</p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl mx-auto w-full">
      <h1 className="text-2xl font-bold text-[var(--color-navy)] mb-6">Panel de Administración</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white border border-[var(--color-border)] rounded-[12px] shadow-sm p-6">
          <h2 className="text-lg font-semibold mb-4 text-[var(--color-primary)]">Gestión de Usuarios</h2>
          <p className="text-[var(--color-text-muted)]">Cargando usuarios...</p>
        </div>

        <div className="bg-white border border-[var(--color-border)] rounded-[12px] shadow-sm p-6">
          <h2 className="text-lg font-semibold mb-4 text-[var(--color-primary)]">Métricas de Uso</h2>
          <p className="text-[var(--color-text-muted)]">Cargando métricas...</p>
        </div>

        <div className="bg-white border border-[var(--color-border)] rounded-[12px] shadow-sm p-6 md:col-span-2">
          <h2 className="text-lg font-semibold mb-4 text-[var(--color-primary)]">Base de Conocimiento (KB)</h2>
          <p className="text-[var(--color-text-muted)]">Cargando documentos de la organización...</p>
        </div>
      </div>
    </div>
  );
}
