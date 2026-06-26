import * as React from "react";
import Link from "next/link";
import { MessageSquare, Clock, Settings, Mail } from "lucide-react";

export function Sidebar() {
  return (
    <aside className="hidden w-[280px] flex-col border-r bg-[var(--color-navy)] text-white md:flex">
      <div className="flex h-16 shrink-0 items-center px-6">
        <Link href="/" className="font-bold text-xl tracking-tight">Keralty</Link>
      </div>
      <nav className="flex-1 overflow-auto px-4 py-4 space-y-2">
        <Link href="/chat" className="flex items-center gap-3 rounded-[8px] px-3 py-2 text-sm font-medium hover:bg-[var(--color-navy-dark)] bg-[var(--color-primary)]">
          <MessageSquare className="h-4 w-4" />
          Nueva conversación
        </Link>
        <Link href="/email" className="flex items-center gap-3 rounded-[8px] px-3 py-2 text-sm font-medium hover:bg-[var(--color-navy-dark)]">
          <Mail className="h-4 w-4" />
          Correo Ejecutivo
        </Link>
        <Link href="/history" className="flex items-center gap-3 rounded-[8px] px-3 py-2 text-sm font-medium hover:bg-[var(--color-navy-dark)]">
          <Clock className="h-4 w-4" />
          Historial
        </Link>
        <Link href="/admin" className="flex items-center gap-3 rounded-[8px] px-3 py-2 text-sm font-medium hover:bg-[var(--color-navy-dark)]">
          <Settings className="h-4 w-4" />
          Administración
        </Link>
      </nav>
    </aside>
  );
}
