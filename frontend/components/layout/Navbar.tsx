import * as React from "react";
import { LocaleSwitcher } from "./LocaleSwitcher";

export function Navbar() {
  return (
    <header className="flex h-16 shrink-0 items-center gap-2 border-b border-[var(--color-border)] bg-white px-6">
      <div className="flex flex-1 items-center gap-4">
        <h1 className="text-xl font-semibold text-[var(--color-navy)]">Keralty Assistant</h1>
      </div>
      <div className="flex items-center gap-4">
        <LocaleSwitcher />
        <div className="h-8 w-8 rounded-full bg-[var(--color-primary-light)] flex items-center justify-center text-[var(--color-primary)] font-semibold">
          US
        </div>
      </div>
    </header>
  );
}
