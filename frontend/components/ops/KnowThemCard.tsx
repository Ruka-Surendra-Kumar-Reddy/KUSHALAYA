"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import "./commerce.css";
import { can } from "@/lib/roles";

type Card = { approach: string; likes: string; avoid: string; routine: string; notes: string; updated_at?: string | null };

const FIELDS: { id: keyof Card; label: string; hint: string }[] = [
  { id: "approach", label: "How to approach", hint: "Morning or evening person? How do they like to be greeted?" },
  { id: "likes", label: "What they enjoy", hint: "Grandchildren's names, garden, serials, festivals, food" },
  { id: "avoid", label: "What to avoid", hint: "Topics or habits that upset them" },
  { id: "routine", label: "Their day", hint: "Wake time, meals, prayers, walks, naps" },
  { id: "notes", label: "Anything else", hint: "Ask the family — they know them best" },
];

/** "Know them" card: what any caregiver should read before knocking. */
export function KnowThemCard({ elderId }: { elderId: number }) {
  const [card, setCard] = useState<Card | null>(null);
  const [editing, setEditing] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api<Card>(`/api/v1/team/clients/${elderId}/know-them`).then(setCard).catch(() => undefined);
  }, [elderId]);

  if (!card) return null;
  const empty = FIELDS.every((f) => !card[f.id]);

  async function save() {
    if (!card) return;
    const next = await api<Card>(`/api/v1/team/clients/${elderId}/know-them`, {
      method: "PUT",
      body: JSON.stringify(card),
    });
    setCard(next);
    setEditing(false);
    setSaved(true);
  }

  return (
    <section className="card kt">
      <div className="kt-head">
        <h2>Know them</h2>
        <span className="muted">Shown to the caregiver before every visit</span>
        {can("edit") ? (
          <button type="button" className="secondary" onClick={() => setEditing((v) => !v)}>
            {editing ? "Cancel" : empty ? "Fill in" : "Edit"}
          </button>
        ) : null}
      </div>
      {editing ? (
        <div className="kt-form">
          {FIELDS.map((f) => (
            <label key={f.id}>
              {f.label}
              <textarea
                rows={2}
                placeholder={f.hint}
                value={card[f.id] ?? ""}
                onChange={(e) => setCard({ ...card, [f.id]: e.target.value })}
              />
            </label>
          ))}
          <div>
            <button type="button" onClick={() => void save()}>
              Save card
            </button>
          </div>
        </div>
      ) : empty ? (
        <p className="muted">Nothing yet. Ask the family how their parent likes to be approached, then fill this in.</p>
      ) : (
        <dl className="kt-view">
          {FIELDS.filter((f) => card[f.id]).map((f) => (
            <div key={f.id}>
              <dt>{f.label}</dt>
              <dd>{card[f.id]}</dd>
            </div>
          ))}
        </dl>
      )}
      {saved && !editing ? <small className="kt-saved">Saved</small> : null}
    </section>
  );
}
