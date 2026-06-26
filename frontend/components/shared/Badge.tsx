import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "success" | "warning" | "error" | "info" | "agent";
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
        {
          "border-transparent bg-[var(--color-navy-light)] text-[var(--color-navy)]": variant === "default",
          "border-transparent bg-[var(--color-success-light)] text-[var(--color-success)]": variant === "success",
          "border-transparent bg-[var(--color-warning-light)] text-[var(--color-warning)]": variant === "warning",
          "border-transparent bg-[var(--color-error-light)] text-[var(--color-error)]": variant === "error",
          "border-transparent bg-[var(--color-info-light)] text-[var(--color-info)]": variant === "info",
          "border-transparent bg-[var(--color-agent-light)] text-[var(--color-agent-thinking)]": variant === "agent",
        },
        className
      )}
      {...props}
    />
  );
}

export { Badge };
