"use client";

/**
 * A drop-down whose "Other" choice opens a short text box; the typed words are the value.
 * A saved value that is not one of the options (e.g. "Neighbour") opens as Other with that text.
 */
import { useState } from "react";

export type Choice = { value: string; label: string };

export function ChoiceWithOther({
  options,
  value,
  onChange,
  otherValue = "other",
  placeholder = "Choose…",
  otherPlaceholder = "Type it here",
  maxLength = 60,
  invalid = false,
  ariaLabel,
}: {
  options: Choice[];
  value: string;
  onChange: (v: string) => void;
  /** The option value that means "Other". */
  otherValue?: string;
  /** Empty first option; null = no empty option. */
  placeholder?: string | null;
  otherPlaceholder?: string;
  maxLength?: number;
  invalid?: boolean;
  ariaLabel?: string;
}) {
  const known = (v: string) => options.some((o) => o.value === v && o.value !== otherValue);
  const [other, setOther] = useState(Boolean(value) && !known(value));
  const text = value === otherValue ? "" : value;
  return (
    <>
      <select
        value={other ? otherValue : value}
        aria-label={ariaLabel}
        aria-invalid={invalid || undefined}
        onChange={(e) => {
          const v = e.target.value;
          const isOther = v === otherValue;
          setOther(isOther);
          onChange(isOther ? "" : v);
        }}
      >
        {placeholder !== null ? <option value="">{placeholder}</option> : null}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {other ? (
        <input
          className="ks-other-input"
          style={{ marginTop: "0.4rem" }}
          value={text}
          maxLength={maxLength}
          placeholder={otherPlaceholder}
          aria-label={ariaLabel ? `${ariaLabel}: other` : "Other"}
          autoFocus
          onChange={(e) => onChange(e.target.value)}
        />
      ) : null}
    </>
  );
}
