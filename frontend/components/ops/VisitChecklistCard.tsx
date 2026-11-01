"use client";

import { useEffect, useState } from "react";
import {
  getVisitChecklist,
  saveVisitChecklist,
  type ChecklistItem,
  type ChecklistSuggestion,
} from "@/lib/incident-reports";
import "./commerce.css";
import "./incidents.css";
import { can } from "@/lib/roles";

/** Per-client visit checklist (#99): the caregiver ticks each item on every visit. */
export function VisitChecklistCard({ elderId }: { elderId: number }) {
  const [items, setItems] = useState<ChecklistItem[] | null>(null);
  const [suggestions, setSuggestions] = useState<ChecklistSuggestion[]>([]);
  const [draft, setDraft] = useState<ChecklistItem[]>([]);
  const [newLabel, setNewLabel] = useState("");
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getVisitChecklist(elderId)
      .then((r) => {
        setItems(r.items);
        setSuggestions(r.suggestions);
      })
      .catch(() => setItems([]));
  }, [elderId]);

  if (items === null) return null;

  function start() {
    setDraft(items ?? []);
    setEditing(true);
    setError("");
  }

  function add(item: ChecklistItem) {
    const label = item.label.trim();
    if (!label || draft.some((d) => d.label.toLowerCase() === label.toLowerCase())) return;
    setDraft([...draft, { ...item, label }]);
  }

  async function save() {
    try {
      const r = await saveVisitChecklist(elderId, draft);
      setItems(r.items);
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    }
  }

  const unused = suggestions.filter((s) => !draft.some((d) => d.label.toLowerCase() === s.label.toLowerCase()));

  return (
    <section className="card kt">
      <div className="kt-head">
        <h2>Visit checklist</h2>
        <span className="muted">Ticked by the caregiver on every visit</span>
        {can("edit") ? (
          <button type="button" className="secondary" onClick={() => (editing ? setEditing(false) : start())}>
            {editing ? "Cancel" : items.length ? "Edit" : "Set up"}
          </button>
        ) : null}
      </div>
      {editing ? (
        <div className="kt-form ir-check-form">
          <ol className="ir-check-edit">
            {draft.map((d, i) => (
              <li key={i}>
                <input
                  value={d.label}
                  maxLength={200}
                  aria-label={`Item ${i + 1}`}
                  onChange={(e) => setDraft(draft.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))}
                />
                <button type="button" className="secondary" onClick={() => setDraft(draft.filter((_, j) => j !== i))}>
                  Remove
                </button>
              </li>
            ))}
          </ol>
          <div className="ir-row">
            <input
              value={newLabel}
              maxLength={200}
              placeholder='e.g. "Give 9am medicines", "Check feet", "Walk 10 min"'
              onChange={(e) => setNewLabel(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  add({ id: "", label: newLabel });
                  setNewLabel("");
                }
              }}
            />
            <button
              type="button"
              className="secondary"
              onClick={() => {
                add({ id: "", label: newLabel });
                setNewLabel("");
              }}
            >
              Add
            </button>
          </div>
          {unused.length ? (
            <div>
              <p className="muted">From the assessment questions marked for visits:</p>
              <div className="ir-chips">
                {unused.map((s) => (
                  <button key={s.id} type="button" className="secondary" onClick={() => add({ id: "", label: s.label, source: s.source })}>
                    + {s.label}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          {error ? <p className="ir-error">{error}</p> : null}
          <div>
            <button type="button" onClick={() => void save()}>
              Save checklist
            </button>
          </div>
        </div>
      ) : items.length ? (
        <ol className="ir-check-view">
          {items.map((i) => (
            <li key={i.id}>{i.label}</li>
          ))}
        </ol>
      ) : (
        <p className="muted">No checklist yet. Add the tasks every visit should cover, such as medicines or a short walk.</p>
      )}
    </section>
  );
}
