"use client";

import { useEffect, useState } from "react";
import type { AssessmentCategory, AssessmentInputType } from "@/lib/livewell/assessment";
import { fetchAdminRubric, saveAdminRubric } from "@/lib/livewell/rubricApi";
import { newItemId } from "@/lib/livewell/rubric";

const TYPES: { value: AssessmentInputType; label: string }[] = [
  { value: "rating", label: "Rating" },
  { value: "yesno", label: "Yes / No" },
  { value: "text", label: "Text" },
];

export function SectionQuestionsEditor({
  categoryId,
  onClose,
}: {
  categoryId: string;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState<AssessmentCategory | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void fetchAdminRubric()
      .then((cats) => {
        if (cancelled) return;
        const cat = cats.find((c) => c.id === categoryId);
        setDraft(cat ? { ...cat, items: cat.items.map((i) => ({ ...i })) } : null);
        if (!cat) setError("This stage is not in the saved checklist.");
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Could not load questions");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [categoryId]);

  function updateItem(
    itemId: string,
    patch: Partial<{ label: string; inputType: AssessmentInputType; group: string }>,
  ) {
    if (!draft) return;
    setDraft({
      ...draft,
      items: draft.items.map((i) => (i.id === itemId ? { ...i, ...patch } : i)),
    });
  }

  function addItem() {
    if (!draft) return;
    const label = "New question";
    setDraft({
      ...draft,
      items: [
        ...draft.items,
        {
          id: newItemId(draft.id, label),
          label,
          maxPoints: 5,
          inputType: "rating",
          source: "safehome360",
        },
      ],
    });
  }

  function removeItem(itemId: string) {
    if (!draft) return;
    setDraft({ ...draft, items: draft.items.filter((i) => i.id !== itemId) });
  }

  async function save() {
    if (!draft) return;
    setBusy(true);
    setError("");
    try {
      const cats = await fetchAdminRubric();
      const next = cats.map((c) => (c.id === draft.id ? draft : c));
      await saveAdminRubric(next);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="home-safety-stage-editor">
      <p className="muted" style={{ marginTop: 0 }}>
        Add, edit, or remove questions for this stage. Only admin can do this.
      </p>
      {error ? <p className="error">{error}</p> : null}
      {loading ? <p className="muted">Loading questions…</p> : null}
      {draft
        ? draft.items.map((item) => (
            <div key={item.id} className="home-safety-stage-editor-row">
              <input
                value={item.label}
                onChange={(e) => updateItem(item.id, { label: e.target.value })}
                aria-label="Question"
              />
              <select
                value={item.inputType || "rating"}
                onChange={(e) =>
                  updateItem(item.id, { inputType: e.target.value as AssessmentInputType })
                }
                aria-label="Question type"
              >
                {TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
              <button type="button" className="secondary danger" onClick={() => removeItem(item.id)}>
                Remove
              </button>
            </div>
          ))
        : null}
      <div className="home-safety-stage-editor-actions">
        <button type="button" className="secondary" onClick={addItem} disabled={!draft || busy}>
          + Add question
        </button>
        <button type="button" className="primary" onClick={() => void save()} disabled={!draft || busy}>
          {busy ? "Saving…" : "Save questions"}
        </button>
        <button type="button" className="secondary" onClick={onClose} disabled={busy}>
          Cancel
        </button>
      </div>
    </div>
  );
}
