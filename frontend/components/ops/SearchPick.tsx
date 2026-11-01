"use client";

import { useEffect, useId, useMemo, useState } from "react";

export type PickItem = { value: string; label: string; hint?: string; group?: string };

/**
 * Type-to-search picker (client / lead lists in popups): one box, matching names
 * underneath, click or Enter to choose. Styles: "Search pick" in components/ks-shell.css.
 */
export function SearchPick({
  items,
  value,
  onChange,
  placeholder = "Search by name or phone",
  label,
  loading = false,
  openOnType = false,
}: {
  items: PickItem[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  label: string;
  loading?: boolean;
  /** List the results in the flow (inside short popups) instead of floating over the form. */
  openOnType?: boolean;
}) {
  const chosen = items.find((i) => i.value === value) ?? null;
  const [q, setQ] = useState(chosen?.label ?? "");
  const [open, setOpen] = useState(false);
  const [hi, setHi] = useState(0);
  const listId = useId();
  useEffect(() => setQ(chosen?.label ?? ""), [chosen?.label]);

  const shown = useMemo(() => {
    const n = q.trim().toLowerCase();
    const list = !n || (chosen && q === chosen.label) ? items : items.filter((i) =>
      `${i.label} ${i.hint ?? ""} ${i.group ?? ""}`.toLowerCase().includes(n));
    return list.slice(0, 50);
  }, [items, q, chosen]);

  function pick(i: PickItem) {
    onChange(i.value);
    setQ(i.label);
    setOpen(false);
  }

  return (
    <div className="ks-pick">
      <label htmlFor={`${listId}-in`}>{label}</label>
      <input
        id={`${listId}-in`}
        type="search"
        value={q}
        placeholder={loading ? "Loading…" : placeholder}
        disabled={loading}
        autoComplete="off"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        // Never pops open by itself (e.g. when a popup focuses this box): only once typed.
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(e.target.value.trim().length > 0);
          setHi(0);
          if (value) onChange("");
        }}
        onKeyDown={(e) => {
          if (e.key === "Escape" && open) {
            e.stopPropagation(); // close the list, not the popup around it
            setOpen(false);
          } else if (e.key === "ArrowDown") {
            setOpen(true);
            setHi((h) => Math.min(h + 1, shown.length - 1));
          } else if (e.key === "ArrowUp") setHi((h) => Math.max(h - 1, 0));
          else if (e.key === "Enter" && open && shown[hi]) {
            e.preventDefault();
            pick(shown[hi]);
          } else return;
          e.preventDefault();
        }}
      />
      {open && !loading ? (
        <ul id={listId} role="listbox" className={openOnType ? "ks-pick-list is-inline" : "ks-pick-list"}>
          {shown.length === 0 ? <li className="ks-pick-none">No match</li> : null}
          {shown.map((i, n) => (
            <li
              key={i.value}
              role="option"
              aria-selected={i.value === value}
              className={n === hi ? "is-hi" : undefined}
              onMouseDown={(e) => {
                e.preventDefault();
                pick(i);
              }}
            >
              <strong>{i.label}</strong>
              {i.group ? <em>{i.group}</em> : null}
              {i.hint ? <small>{i.hint}</small> : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
