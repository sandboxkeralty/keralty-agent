"use client";
import * as React from "react";
import { Globe } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";

const LOCALES = ["es", "en"] as const;
type Locale = (typeof LOCALES)[number];

export function LocaleSwitcher() {
  const pathname = usePathname();
  const router = useRouter();

  const segments = pathname.split("/");
  const currentLocale: Locale = (LOCALES as readonly string[]).includes(segments[1])
    ? (segments[1] as Locale)
    : "es";

  const switchTo = (locale: Locale) => {
    if (locale === currentLocale) return;
    const rest = segments.slice(2).join("/");
    router.push(`/${locale}${rest ? `/${rest}` : ""}`);
  };

  return (
    <div className="flex items-center gap-1 text-sm font-medium text-[var(--color-text-secondary)]">
      <Globe className="h-4 w-4 mr-1" />
      {LOCALES.map((locale, i) => (
        <React.Fragment key={locale}>
          {i > 0 && <span className="text-[var(--color-border)]">/</span>}
          <button
            type="button"
            onClick={() => switchTo(locale)}
            className={`uppercase transition-colors ${
              locale === currentLocale
                ? "text-[var(--color-primary)] font-semibold"
                : "hover:text-[var(--color-primary)]"
            }`}
          >
            {locale}
          </button>
        </React.Fragment>
      ))}
    </div>
  );
}
