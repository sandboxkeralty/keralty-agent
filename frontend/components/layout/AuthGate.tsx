"use client";

import * as React from "react";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { getToken, setToken, loginUrl, UNAUTHORIZED_EVENT } from "@/lib/api";

// Renders the app only for an authenticated user. A logged-out user (no token,
// or an expired token that produced a 401 anywhere) sees an explicit
// login-required panel instead of a chat that silently operates as the sandbox
// identity. Captures the OAuth `?token=` redirect before gating.
export function AuthGate({ children }: { children: React.ReactNode }) {
  const t = useTranslations("auth");
  const [authed, setAuthed] = useState<boolean | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("token");
    if (urlToken) {
      setToken(urlToken);
      window.history.replaceState({}, "", window.location.pathname);
    }
    setAuthed(!!getToken());

    const onUnauthorized = () => setAuthed(false);
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  if (authed === null) return null; // brief check; avoid a flash of either state

  if (!authed) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-[var(--color-background)] p-6">
        <div className="w-full max-w-sm rounded-[16px] border border-[var(--color-border)] bg-white p-8 text-center shadow-sm">
          <h2 className="text-lg font-semibold text-[var(--color-navy)]">{t("required")}</h2>
          <p className="mt-2 text-sm text-[var(--color-text-secondary)]">{t("prompt")}</p>
          <a
            href={loginUrl()}
            className="mt-6 inline-block rounded-[8px] bg-[var(--color-primary)] px-5 py-2.5 text-sm font-medium text-white hover:bg-[var(--color-primary-dark)] transition-colors"
          >
            {t("login")}
          </a>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
