import type { InputHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

interface TextInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {
  id: string;
  label: string;
  hint?: string;
  error?: string;
}

export function TextInput({ className, error, hint, id, label, ...props }: TextInputProps) {
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-ink" htmlFor={id}>
        {label}
      </label>
      {hint ? (
        <p className="text-sm leading-5 text-ink-muted" id={hintId}>
          {hint}
        </p>
      ) : null}
      <input
        aria-describedby={describedBy}
        aria-invalid={error ? true : undefined}
        className={cn(
          "min-h-11 w-full border border-rule-strong bg-canvas px-3 py-2 text-base text-ink placeholder:text-ink-muted focus:border-ink focus:outline-none",
          error && "border-ink",
          className,
        )}
        id={id}
        {...props}
      />
      {error ? (
        <p className="text-sm leading-5 text-ink" id={errorId}>
          {error}
        </p>
      ) : null}
    </div>
  );
}
