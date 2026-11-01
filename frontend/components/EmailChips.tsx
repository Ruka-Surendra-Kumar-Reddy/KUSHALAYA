"use client";

import { KeyboardEvent, useState } from "react";

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const PHONE = /^\+?[\d\s-]{10,17}$/;

/** A list of email addresses (or phone numbers): × removes one, type + Enter (or Add) adds one. */
export function EmailChips({
  value,
  onChange,
  disabled = false,
  kind = "email",
  placeholder = kind === "phone" ? "98xxxxxxxx or +44…" : "name@example.com",
  label = kind === "phone" ? "Add a phone number" : "Add an email",
}: {
  value: string[];
  onChange: (next: string[]) => void;
  disabled?: boolean;
  kind?: "email" | "phone";
  placeholder?: string;
  label?: string;
}) {
  const [draft, setDraft] = useState("");
  const [bad, setBad] = useState(false);

  function add() {
    const addr = draft.trim();
    if (!addr) return;
    if (!(kind === "phone" ? PHONE : EMAIL).test(addr)) {
      setBad(true);
      return;
    }
    if (!value.some((v) => v.toLowerCase() === addr.toLowerCase())) onChange([...value, addr]);
    setDraft("");
    setBad(false);
  }

  function onKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      add();
    }
  }

  return (
    <div className="ks-chips">
      {value.map((addr) => (
        <span key={addr} className="ks-chip">
          {addr}
          {!disabled && (
            <button type="button" aria-label={`Remove ${addr}`} onClick={() => onChange(value.filter((v) => v !== addr))}>
              ×
            </button>
          )}
        </span>
      ))}
      {!disabled && (
        <span className="ks-chip-add">
          <input
            type={kind === "phone" ? "tel" : "email"}
            value={draft}
            aria-label={label}
            aria-invalid={bad}
            placeholder={placeholder}
            onChange={(e) => {
              setDraft(e.target.value);
              setBad(false);
            }}
            onKeyDown={onKey}
            onBlur={() => draft.trim() && add()}
          />
          <button type="button" onClick={add}>
            Add
          </button>
        </span>
      )}
      {bad && (
        <small className="ks-chip-error">
          {kind === "phone" ? "Enter a 10-digit mobile, or + and the country code." : "That doesn’t look like an email address."}
        </small>
      )}
    </div>
  );
}
