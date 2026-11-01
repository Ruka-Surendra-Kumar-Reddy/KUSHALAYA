"use client";

import { FormEvent, useEffect, useState } from "react";
import type { CustomFieldDef } from "@/lib/customFields";

const FIELD_TYPES = [
  { id: "text", label: "Text" },
  { id: "textarea", label: "Long text" },
  { id: "number", label: "Number" },
  { id: "email", label: "Email" },
  { id: "phone", label: "Phone" },
  { id: "date", label: "Date" },
  { id: "select", label: "Dropdown" },
  { id: "boolean", label: "Yes / No" },
];

type Props = {
  entityLabel: string;
  fields: CustomFieldDef[];
  onSave: (fields: CustomFieldDef[]) => Promise<void>;
};

function slugKey(label: string): string {
  return label
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "_")
    .replace(/[^a-z0-9_]/g, "");
}

export function CustomFieldBuilder({
  entityLabel,
  fields,
  onSave,
}: Props) {
  const [list, setList] = useState<CustomFieldDef[]>(fields);

  useEffect(() => {
    setList(fields);
  }, [fields]);
  const [label, setLabel] = useState("");
  const [type, setType] = useState("text");
  const [required, setRequired] = useState(false);
  const [optionsText, setOptionsText] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function addField(e: FormEvent) {
    e.preventDefault();
    setError("");
    const trimmed = label.trim();
    if (!trimmed) {
      setError("Enter a field label");
      return;
    }
    const key = slugKey(trimmed);
    if (!key) {
      setError("Invalid label");
      return;
    }
    if (list.some((f) => f.key === key)) {
      setError("A field with this key already exists");
      return;
    }
    const entry: CustomFieldDef = {
      key,
      label: trimmed,
      type,
      required,
      section: "Custom",
    };
    if (type === "select") {
      const opts = optionsText
        .split(/[,;]+/)
        .map((s) => s.trim())
        .filter(Boolean);
      if (!opts.length) {
        setError("Add comma-separated options for dropdown");
        return;
      }
      entry.options = opts;
    }
    setList([...list, entry]);
    setLabel("");
    setType("text");
    setRequired(false);
    setOptionsText("");
  }

  function removeField(key: string) {
    setList(list.filter((f) => f.key !== key));
  }

  async function persist() {
    setSaving(true);
    setError("");
    try {
      await onSave(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      {list.length > 0 && (
        <table className="table" style={{ marginBottom: "1rem" }}>
          <thead>
            <tr>
              <th>Label</th>
              <th>Key</th>
              <th>Type</th>
              <th>Required</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {list.map((f) => (
              <tr key={f.key}>
                <td>{f.label}</td>
                <td>
                  <code>{f.key}</code>
                </td>
                <td>{f.type}</td>
                <td>{f.required ? "Yes" : "No"}</td>
                <td>
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => removeField(f.key)}
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <form onSubmit={addField} className="grid-2" style={{ marginBottom: "1rem" }}>
        <div>
          <label>New field label</label>
          <input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder={`e.g. Preferred hospital (${entityLabel})`}
          />
        </div>
        <div>
          <label>Field type</label>
          <select value={type} onChange={(e) => setType(e.target.value)}>
            {FIELD_TYPES.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
        {type === "select" && (
          <div style={{ gridColumn: "1 / -1" }}>
            <label>Options (comma-separated)</label>
            <input
              value={optionsText}
              onChange={(e) => setOptionsText(e.target.value)}
              placeholder="Veg, Non-veg, Jain"
            />
          </div>
        )}
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <input
            id={`req-${entityLabel}`}
            type="checkbox"
            checked={required}
            onChange={(e) => setRequired(e.target.checked)}
            style={{ width: "auto" }}
          />
          <label htmlFor={`req-${entityLabel}`} style={{ margin: 0 }}>
            Required on create
          </label>
        </div>
        <div style={{ display: "flex", alignItems: "flex-end" }}>
          <button type="submit" className="secondary">
            Add field
          </button>
        </div>
      </form>
      {error && <p className="error">{error}</p>}
      <button type="button" onClick={persist} disabled={saving}>
        {saving ? "Saving…" : `Save ${entityLabel} custom fields`}
      </button>
    </div>
  );
}
