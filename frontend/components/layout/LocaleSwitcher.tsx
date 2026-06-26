"use client";
import * as React from "react";
import { Globe } from "lucide-react";

export function LocaleSwitcher() {
  return (
    <button className="flex items-center gap-2 text-sm font-medium text-[var(--color-text-secondary)] hover:text-[var(--color-primary)] transition-colors">
      <Globe className="h-4 w-4" />
      <span>ES / EN</span>
    </button>
  );
}
