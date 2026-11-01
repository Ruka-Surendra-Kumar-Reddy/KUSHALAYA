"use client";

import { useEffect, useRef, type ReactNode } from "react";

/**
 * In-app confirm sheet (replaces window.confirm): bottom sheet on phones,
 * centred card on desktop. Escape or tapping outside cancels.
 */
export function FamilyConfirmSheet({
  open,
  title,
  children,
  confirmLabel,
  onConfirm,
  onCancel,
  cancelLabel = "Not now",
  busy = false,
  danger = false,
  extra,
}: {
  open: boolean;
  title: string;
  children?: ReactNode;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  cancelLabel?: string;
  busy?: boolean;
  danger?: boolean;
  /** Optional third action, e.g. "Decline". */
  extra?: ReactNode;
}) {
  const confirmRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    confirmRef.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onCancel();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open) return null;
  return (
    <div className="fh-sheet-scrim" role="presentation" onClick={onCancel}>
      <div
        className="fh-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="fh-sheet-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="fh-sheet-title">{title}</h2>
        <div className="fh-sheet-body">{children}</div>
        <div className="fh-sheet-actions">
          <button
            ref={confirmRef}
            type="button"
            className={danger ? "danger primary" : "primary"}
            disabled={busy}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
          {extra}
          <button type="button" className="secondary" disabled={busy} onClick={onCancel}>
            {cancelLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
