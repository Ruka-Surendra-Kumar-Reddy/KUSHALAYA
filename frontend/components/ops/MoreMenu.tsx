"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * Small "More ▾" / "⋯" overflow menu (styles: "More menu" block in components/ks-shell.css).
 * Children are menu items: use className="ks-more-item" (add "is-danger" for destructive ones).
 * The menu closes on an item click, an outside click or Escape.
 */
export function MoreMenu({
  label = "More",
  icon = false,
  title,
  align = "left",
  children,
}: {
  label?: string;
  /** true: a compact "⋯" button with `label` as its accessible name. */
  icon?: boolean;
  title?: string;
  align?: "left" | "right";
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent | TouchEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("touchstart", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("touchstart", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="ks-more" ref={ref}>
      <button
        type="button"
        className={icon ? "secondary ks-more-dots" : "secondary"}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={icon ? label : undefined}
        title={title ?? (icon ? label : undefined)}
        onClick={() => setOpen((v) => !v)}
      >
        {icon ? (
          <span aria-hidden="true">⋯</span>
        ) : (
          <>
            {label} <span aria-hidden="true">▾</span>
          </>
        )}
      </button>
      {open ? (
        <div
          className={`ks-more-menu${align === "right" ? " is-right" : ""}`}
          role="menu"
          onClick={(e) => {
            if ((e.target as HTMLElement).closest(".ks-more-item")) setOpen(false);
          }}
        >
          {children}
        </div>
      ) : null}
    </div>
  );
}
