"use client";
import * as React from "react";
import { Upload, HardDrive } from "lucide-react";
import { useTranslations } from "next-intl";

export function AttachMenu({
  onUploadClick,
  onDriveClick,
}: {
  onUploadClick: () => void;
  onDriveClick: () => void;
}) {
  const t = useTranslations("documents");

  return (
    <div className="w-56 border border-[var(--color-border)] bg-white rounded-[12px] shadow-sm overflow-hidden">
      <button
        type="button"
        onClick={onUploadClick}
        className="w-full flex items-center gap-2 p-3 hover:bg-[var(--color-navy-light)] text-left text-sm text-[var(--color-text-primary)] transition-colors"
      >
        <Upload size={16} className="text-[var(--color-primary)]" />
        {t("uploadFromDevice")}
      </button>
      <button
        type="button"
        onClick={onDriveClick}
        className="w-full flex items-center gap-2 p-3 hover:bg-[var(--color-navy-light)] text-left text-sm text-[var(--color-text-primary)] border-t border-[var(--color-border)] transition-colors"
      >
        <HardDrive size={16} className="text-[var(--color-primary)]" />
        {t("selectFromDrive")}
      </button>
    </div>
  );
}
