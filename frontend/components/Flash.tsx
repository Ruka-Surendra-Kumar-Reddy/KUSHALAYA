"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import "./flash.css";

/**
 * Success / error notices as a notification card in the top-right corner (icon,
 * text, ✕) instead of a line of text with a "Dismiss" button in the page.
 * Same props as the shared @workforceos/contracts Flash (the other products keep
 * theirs). Success fades out after 5 s; an error stays until closed.
 */
export function Flash({
  error,
  message,
  onClear,
}: {
  error?: string;
  message?: string;
  onClear?: () => void;
  /** Kept for compatibility with the shared Flash; the ✕ replaces the button. */
  dismissLabel?: string;
}) {
  const text = error || message || "";
  const [hidden, setHidden] = useState(false);
  useEffect(() => setHidden(false), [text]);

  const close = () => {
    setHidden(true);
    onClear?.();
  };

  useEffect(() => {
    if (!text || error) return;
    const t = window.setTimeout(close, 5000);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- restart only for a new notice
  }, [text, error]);

  if (!text || hidden || typeof document === "undefined") return null;
  return createPortal(
    <div className={error ? "ks-toast is-error" : "ks-toast"} role={error ? "alert" : "status"} aria-live="polite">
      <span className="ks-toast-ic" aria-hidden="true">
        {error ? "!" : "✓"}
      </span>
      <p>{text}</p>
      <button type="button" className="ks-toast-x" onClick={close} aria-label="Close">
        ✕
      </button>
    </div>,
    document.body,
  );
}
