"use client";

import * as React from "react";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { LocaleSwitcher } from "./LocaleSwitcher";
import { getToken, clearToken, loginUrl, UNAUTHORIZED_EVENT } from "@/lib/api";

export function Navbar() {
  const t = useTranslations("nav");
  const [userEmail, setUserEmail] = useState<string | null>(null);

  useEffect(() => {
    // AuthGate captures the ?token= redirect before the shell renders; here we
    // just decode the stored token to display the user's email.
    const stored = getToken();
    if (stored) {
      try {
        const payload = JSON.parse(atob(stored.split(".")[1]));
        setUserEmail(payload.email || payload.sub || "Usuario");
      } catch {
        setUserEmail("Usuario");
      }
    }
  }, []);

  function logout() {
    clearToken();
    setUserEmail(null);
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
  }

  return (
    <header className="flex h-16 shrink-0 items-center gap-2 border-b border-[var(--color-border)] bg-white px-6">
      <div className="flex flex-1 items-center gap-4">
        <h1 className="text-xl font-semibold text-[var(--color-navy)]">Keralty Assistant</h1>
      </div>
      <div className="flex items-center gap-4">
        <LocaleSwitcher />
        {userEmail ? (
          <div className="flex items-center gap-2">
            <span className="text-sm text-[var(--color-text-secondary)] hidden sm:block">{userEmail}</span>
            <button
              onClick={logout}
              className="text-sm text-[var(--color-navy)] underline hover:no-underline"
            >
              {t("logout")}
            </button>
          </div>
        ) : (
          <a
            href={loginUrl()}
            className="text-sm font-medium text-[var(--color-primary)] hover:underline"
          >
            {t("login")}
          </a>
        )}
      </div>
    </header>
  );
}
