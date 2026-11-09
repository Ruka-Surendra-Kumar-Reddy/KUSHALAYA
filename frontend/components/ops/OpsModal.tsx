"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

/**
 * The one popup for "Add / Assign / Create / New" forms in the Ops app: centred over
 * a dimmed page (portalled to <body>, so no parent can clip or push it), closes on
 * ✕, Esc or a click outside, scrolls inside when tall, full width on phones.
 * Styles: "Ops modal" block in components/ks-shell.css.
 */
export function OpsModal({
  open,
  title,
  onClose,
  children,
  wide = false,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  /** Forms with many fields side by side (e.g. a schedule form). */
  wide?: boolean;
}) {
  const box = useRef<HTMLDivElement>(null);
  // Callers pass a new onClose on every render; keep the latest here so the effect below
  // runs only when the popup opens. Re-running it moved the cursor back to the first
  // field on every keystroke.
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeRef.current();
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    // First field gets focus, so typing starts straight away.
    window.setTimeout(() => {
      box.current?.querySelector<HTMLElement>("input, select, textarea, button:not(.ks-modal-x)")?.focus();
    }, 30);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open]);

  if (!open || typeof document === "undefined") return null;
  return createPortal(
    <div
      className="ks-modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={box}
        className={wide ? "ks-modal is-wide" : "ks-modal"}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <header className="ks-modal-head">
          <h2>{title}</h2>
          <button type="button" className="ks-modal-x" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>
        <div className="ks-modal-body">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
