"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Flash } from "@/components/Flash";
import {
  newCategoryId,
  newItemId,
  normalizeRubric,
  normalizeRubricWithSources,
} from "@/lib/livewell/rubric";
import { DEFAULT_SAFETY_CATEGORIES } from "@/lib/livewell/rubric-defaults";
import { fetchAdminRubric, saveAdminRubric } from "@/lib/livewell/rubricApi";
import type {
  AssessmentCategory,
  AssessmentInputType,
  AssessmentItem,
  OptionRating,
  QuestionOption,
  RubricItemSource,
} from "@/lib/livewell/assessment";
import {
  MAX_ASK,
  MAX_OPTION_LABEL,
  MAX_OPTIONS,
  OPTION_RATINGS,
  RATING_MEANS,
  cleanOptions,
  joinHelp,
  questionAsk,
  questionOptions,
  splitHelp,
  standardAsk,
  standardOptions,
} from "@/lib/livewell/question-options";
import { RUBRIC_SOURCE_ORDER } from "@/lib/livewell/rubric-sources";
import { publicBrandName } from "@/lib/public-brand";
import { useSafetySolutions } from "@/lib/livewell/useSafetySolutions";
import "@/components/ops/rubric.css";

type ItemPatch = Partial<{
  label: string;
  maxPoints: number;
  source: RubricItemSource;
  inputType: AssessmentInputType;
  help: string;
  hidden: boolean;
  visitQuestion: boolean;
}>;

/** The drawer's working copy of one question; applied on Save, dropped on Cancel. */
type Draft = {
  id: string;
  ask: string;
  label: string;
  inputType: AssessmentInputType;
  options: QuestionOption[];
  lookFor: string;
  guide: string;
  maxPoints: number;
  source: RubricItemSource;
  visitQuestion: boolean;
  hidden: boolean;
  /** Help as loaded, to tell whether it was edited. */
  helpBefore: string;
};

// Answer types and the fixed choices each one shows the caregiver (same words as the
// caregiver app and reports; scoring is unchanged).
const ANSWER_TYPES: { value: AssessmentInputType; label: string }[] = [
  { value: "rating", label: "Rating" },
  { value: "yesno", label: "Yes / No" },
  { value: "text", label: "Text" },
];
type Opt = { word: string; tone: "good" | "warn" | "bad" | "na"; title: string };
/** Chip colour per rating: green Safe, amber Needs attention, red Risk, grey Doesn't apply. */
const TONE: Record<OptionRating, Opt["tone"]> = { excellent: "good", acceptable: "warn", unsafe: "bad", na: "na" };
const YESNO_OPTIONS: Opt[] = [
  { word: "Yes", tone: "good", title: "Full points" },
  { word: "No", tone: "bad", title: "No points" },
  { word: "N/A", tone: "na", title: "Left out of the score" },
];

export function RubricAdminEditor({ header }: { header?: ReactNode } = {}) {
  const [categories, setCategories] = useState<AssessmentCategory[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [newCatTitle, setNewCatTitle] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const [editing, setEditing] = useState<{ catId: string; itemId: string } | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const closeEditor = useCallback(() => {
    setEditing(null);
    setDraft(null);
  }, []);
  // Drawer: Esc closes it and the page behind does not scroll.
  useEffect(() => {
    if (!editing) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeEditor();
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [editing, closeEditor]);
  // Close the section menu on any outside click or Escape.
  useEffect(() => {
    if (!menuFor) return;
    const close = (e: Event) => {
      if (e instanceof KeyboardEvent) {
        if (e.key !== "Escape") return;
      } else if (e.target instanceof Element && e.target.closest(".rubric-menu-wrap")) return;
      setMenuFor(null);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [menuFor]);
  const solutions = useSafetySolutions();
  // "Suggests: <product>" - first solution that this question triggers.
  const suggestsByItem = useMemo(() => {
    const map = new Map<string, string>();
    for (const sol of solutions.solutions ?? []) {
      const product = sol.recommendedSolutions?.[0] || sol.name || "";
      if (!product) continue;
      for (const id of sol.rubricItemIds ?? []) if (!map.has(id)) map.set(id, product);
    }
    return map;
  }, [solutions]);

  // Warn before leaving the page with unsaved changes.
  useEffect(() => {
    if (!dirty) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [dirty]);
  // Sections start folded: 80+ questions on one screen was unreadable.
  const [openCats, setOpenCats] = useState<Set<string>>(new Set());
  const toggleCat = (id: string) =>
    setOpenCats((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  useEffect(() => {
    setLoading(true);
    fetchAdminRubric()
      .then((loaded) => setCategories(loaded))
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load the questions"))
      .finally(() => setLoading(false));
  }, []);

  const persistLocal = useCallback((next: AssessmentCategory[]) => {
    setCategories(normalizeRubric(next));
    setDirty(true);
  }, []);

  async function saveRubric() {
    setBusy(true);
    setError("");
    try {
      const saved = await saveAdminRubric(categories);
      setCategories(saved);
      setDirty(false);
      setMessage("Saved. Caregivers get these questions on their next assessment.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function resetRubric() {
    if (!window.confirm("Replace all questions with the standard set? Your changes will be lost.")) return;
    setBusy(true);
    setError("");
    try {
      const saved = await saveAdminRubric(DEFAULT_SAFETY_CATEGORIES);
      setCategories(saved);
      setDirty(false);
      setMessage("Questions reset to the standard set.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reset failed");
    } finally {
      setBusy(false);
    }
  }

  function addCategory() {
    const title = newCatTitle.trim();
    if (!title) return;
    const id = newCategoryId(title);
    persistLocal([
      ...categories,
      { id, title, maxPoints: 0, items: [{ id: newItemId(id, "New item"), label: "New item", maxPoints: 5 }] },
    ]);
    setNewCatTitle("");
  }

  function removeCategory(catId: string) {
    persistLocal(categories.filter((c) => c.id !== catId));
  }

  /** Hide or show every question in a section (nothing is deleted). */
  function setCategoryHidden(catId: string, hidden: boolean) {
    persistLocal(
      categories.map((c) => (c.id === catId ? { ...c, items: c.items.map((i) => ({ ...i, hidden })) } : c)),
    );
  }

  function updateCategoryTitle(catId: string, title: string) {
    persistLocal(categories.map((c) => (c.id === catId ? { ...c, title } : c)));
  }

  function addItem(catId: string) {
    const label = "New question";
    const item: AssessmentItem = { id: newItemId(catId, label), label, maxPoints: 5, source: "safehome360", inputType: "rating" };
    persistLocal(categories.map((c) => (c.id === catId ? { ...c, items: [...c.items, item] } : c)));
    openEditor(catId, item);
  }

  /** Help used for "Reset to standard" (its ★/~/✕ lines are a fallback source). */
  function draftHelpItem(d: Draft) {
    return { id: d.id, label: d.label, help: joinHelp(d.lookFor, d.guide) };
  }

  function openEditor(catId: string, item: AssessmentItem) {
    const help = item.help ?? "";
    const { lookFor, rest } = splitHelp(help);
    const custom = cleanOptions(item.options);
    setDraft({
      id: item.id,
      ask: questionAsk(item),
      label: item.label,
      inputType: item.inputType || "rating",
      options: custom.length ? custom : standardOptions(item),
      lookFor,
      guide: rest,
      maxPoints: item.maxPoints,
      source: item.source ?? "safehome360",
      visitQuestion: Boolean(item.visitQuestion),
      hidden: Boolean(item.hidden),
      helpBefore: help,
    });
    setEditing({ catId, itemId: item.id });
  }

  function setOption(index: number, patch: Partial<QuestionOption>) {
    setDraft((d) => (d ? { ...d, options: d.options.map((o, k) => (k === index ? { ...o, ...patch } : o)) } : d));
  }

  function applyDraft() {
    if (!editing || !draft) return;
    const base = { id: draft.id, label: draft.label };
    const help = joinHelp(draft.lookFor, draft.guide);
    const before = splitHelp(draft.helpBefore);
    const helpChanged = help !== joinHelp(before.lookFor, before.rest);
    const options = cleanOptions(draft.options);
    // Standard options and wording are not stored, so they follow future wording updates.
    const standard = standardOptions({ ...base, help: draft.helpBefore });
    const sameAsStandard = JSON.stringify(options) === JSON.stringify(standard);
    const ask = draft.ask.trim().slice(0, MAX_ASK);
    persistLocal(
      categories.map((c) =>
        c.id !== editing.catId
          ? c
          : {
              ...c,
              items: c.items.map((i) => {
                if (i.id !== editing.itemId) return i;
                const next: AssessmentItem = {
                  ...i,
                  label: draft.label.trim() || i.label,
                  inputType: draft.inputType,
                  maxPoints: Math.max(1, Math.round(draft.maxPoints)),
                  source: draft.source,
                  visitQuestion: draft.visitQuestion,
                  ask: ask && ask !== standardAsk(base) ? ask : undefined,
                  options: draft.inputType === "rating" && options.length && !sameAsStandard ? options : undefined,
                };
                if (helpChanged) next.help = help;
                return next;
              }),
            },
      ),
    );
    closeEditor();
  }

  function removeItem(catId: string, itemId: string, label: string): boolean {
    if (
      !window.confirm(
        `Remove "${label}" for good?\n\nTip: use Hide instead. Hidden questions are not asked, and old reports keep them.`,
      )
    )
      return false;
    persistLocal(
      categories.map((c) => {
        if (c.id !== catId) return c;
        return { ...c, items: c.items.filter((i) => i.id !== itemId) };
      }),
    );
    return true;
  }

  function moveItem(catId: string, itemId: string, dir: -1 | 1) {
    persistLocal(
      categories.map((c) => {
        if (c.id !== catId) return c;
        const idx = c.items.findIndex((i) => i.id === itemId);
        const to = idx + dir;
        if (idx < 0 || to < 0 || to >= c.items.length) return c;
        const items = [...c.items];
        [items[idx], items[to]] = [items[to], items[idx]];
        return { ...c, items };
      }),
    );
  }

  function updateItem(catId: string, itemId: string, patch: ItemPatch) {
    persistLocal(
      categories.map((c) => {
        if (c.id !== catId) return c;
        return {
          ...c,
          items: c.items.map((i) => (i.id === itemId ? { ...i, ...patch } : i)),
        };
      }),
    );
  }

  const normalized = normalizeRubricWithSources(categories);
  const totalQuestions = normalized.reduce((n, c) => n + c.items.length, 0);
  const activeQuestions = normalized.reduce((n, c) => n + c.items.filter((i) => !i.hidden).length, 0);
  const visitQuestions = normalized.reduce(
    (n, c) => n + c.items.filter((i) => i.visitQuestion && !i.hidden).length,
    0,
  );

  if (loading) return <>{header}<p className="muted">Loading questions…</p></>;

  return (
    <div className="home-safety-rubric-admin">
      <div className="ks-head-row">
        {header ?? <div />}
        <div className="ks-head-actions">
          <button
            type="button"
            disabled={busy || !dirty}
            onClick={() => void saveRubric()}
            aria-label="Save questions"
            title={dirty ? "Save questions" : "No changes to save"}
          >
            <span className="ks-ha-icon" aria-hidden="true">✓</span>
            <span className="ks-ha-label">{busy ? "Saving…" : "Save"}</span>
          </button>
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={() => void resetRubric()}
            aria-label="Use standard questions"
            title="Replace all questions with the standard set"
          >
            <span className="ks-ha-icon" aria-hidden="true">↺</span>
            <span className="ks-ha-label">Use standard set</span>
          </button>
        </div>
      </div>
      <Flash message={message} error={error} onClear={() => { setMessage(""); setError(""); }} />

      <p className="muted rubric-stats">
        <strong>{activeQuestions} active</strong> · {totalQuestions} total ·{" "}
        <span title="Questions ticked “Ask on every visit” are also asked by the caregiver on each routine visit (KushLife check).">
          {visitQuestions
            ? `${visitQuestions} also asked on every visit`
            : "none asked on every visit yet"}
        </span>
      </p>

      {normalized.length === 0 ? (
        <div className="card home-safety-empty">
          <p>No questions yet.</p>
          <p className="muted">
            Press <strong>Use standard set</strong> above to start with the standard set.
          </p>
        </div>
      ) : null}

      {normalized.map((cat) => (
        <section key={cat.id} className="card" style={{ marginBottom: "1rem" }}>
          <div
            className="rubric-cat-head"
            style={{ marginBottom: openCats.has(cat.id) ? "0.75rem" : 0 }}
          >
            {renaming === cat.id ? (
              <input
                className="rubric-cat-title"
                value={cat.title}
                autoFocus
                onChange={(e) => updateCategoryTitle(cat.id, e.target.value)}
                onBlur={() => setRenaming(null)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === "Escape") setRenaming(null);
                }}
                aria-label="Section name"
              />
            ) : (
              <span className="rubric-cat-name">
                <strong>{cat.title || "Untitled section"}</strong>
              </span>
            )}
            <span className="muted rubric-cat-meta">
              {cat.items.filter((i) => !i.hidden).length} of {cat.items.length} asked · {cat.maxPoints} points
            </span>
            <span className="rubric-cat-btns">
              <button
                type="button"
                className="secondary"
                aria-expanded={openCats.has(cat.id)}
                onClick={() => toggleCat(cat.id)}
              >
                {openCats.has(cat.id) ? "Close" : "Open"}{" "}
                <span aria-hidden="true">{openCats.has(cat.id) ? "▴" : "›"}</span>
              </button>
              <span className="rubric-menu-wrap">
                <button
                  type="button"
                  className="secondary rubric-menu-btn"
                  aria-haspopup="menu"
                  aria-expanded={menuFor === cat.id}
                  aria-label={`More for ${cat.title}`}
                  onClick={() => setMenuFor(menuFor === cat.id ? null : cat.id)}
                >
                  ⋯
                </button>
                {menuFor === cat.id ? (
                  <span className="rubric-menu" role="menu">
                    <button type="button" role="menuitem" onClick={() => { setMenuFor(null); setRenaming(cat.id); }}>
                      Rename
                    </button>
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => {
                        setMenuFor(null);
                        setCategoryHidden(cat.id, !cat.items.every((i) => i.hidden));
                      }}
                    >
                      {cat.items.length && cat.items.every((i) => i.hidden) ? "Show section" : "Hide section"}
                    </button>
                    <button
                      type="button"
                      role="menuitem"
                      className="is-danger"
                      onClick={() => {
                        setMenuFor(null);
                        if (window.confirm(`Remove the whole "${cat.title}" section and its questions?`)) removeCategory(cat.id);
                      }}
                    >
                      Remove section
                    </button>
                  </span>
                ) : null}
              </span>
            </span>
          </div>
          {openCats.has(cat.id) ? (
          <>
          <ol className="rq-list">
            {cat.items.map((item, idx) => {
              const type = item.inputType || "rating";
              const suggests = suggestsByItem.get(item.id);
              const chips: { label: string; tone: string }[] =
                type === "text"
                  ? [{ label: "Typed answer", tone: "text" }]
                  : type === "yesno"
                    ? YESNO_OPTIONS.map((o) => ({ label: o.word, tone: o.tone }))
                    : questionOptions(item).map((o) => ({ label: o.label, tone: TONE[o.rating] }));
              return (
                <li key={item.id} className={`rq-row${item.hidden ? " is-hidden" : ""}`}>
                  <span className="rq-num" aria-hidden="true">{idx + 1}</span>
                  <div className="rq-main">
                    <p className="rq-ask">{questionAsk(item)}</p>
                    <p className="rq-sub">
                      {ANSWER_TYPES.find((t) => t.value === type)?.label} · {item.maxPoints} pt
                      {item.maxPoints === 1 ? "" : "s"}
                      {item.visitQuestion ? " · Every visit" : ""}
                      {item.hidden ? <span className="badge rq-hidden-tag">Hidden</span> : null}
                      {suggests ? <span className="rq-suggests"> · Suggests: {suggests}</span> : null}
                    </p>
                    <span className="rq-options" aria-label="Answers the caregiver sees">
                      {chips.map((c, k) => (
                        <span key={k} className={`rq-opt rq-opt-${c.tone}`} title={c.label}>
                          {c.label}
                        </span>
                      ))}
                    </span>
                  </div>
                  <span className="rq-row-btns">
                    <button
                      type="button"
                      className="secondary rq-icon-btn"
                      disabled={idx === 0}
                      onClick={() => moveItem(cat.id, item.id, -1)}
                      aria-label="Move up"
                      title="Move up"
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      className="secondary rq-icon-btn"
                      disabled={idx === cat.items.length - 1}
                      onClick={() => moveItem(cat.id, item.id, 1)}
                      aria-label="Move down"
                      title="Move down"
                    >
                      ↓
                    </button>
                    <button
                      type="button"
                      className="secondary rq-edit-btn"
                      onClick={() => openEditor(cat.id, item)}
                      aria-label={`Edit question ${idx + 1}`}
                    >
                      Edit
                    </button>
                  </span>
                </li>
              );
            })}
          </ol>
          <button type="button" className="secondary rq-add" onClick={() => addItem(cat.id)}>
            + Add question
          </button>
          </>
          ) : null}
        </section>
      ))}

      <div className="rq-new-section">
        <input
          placeholder="New section name"
          value={newCatTitle}
          onChange={(e) => setNewCatTitle(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") addCategory();
          }}
          aria-label="New section name"
        />
        <button type="button" className="secondary" onClick={addCategory} disabled={!newCatTitle.trim()}>
          + Add section
        </button>
      </div>

      {dirty ? (
        <div className="rubric-savebar rq-savebar">
          <span className="rq-savebar-note">You have unsaved changes.</span>
          <button type="button" className="primary" disabled={busy} onClick={() => void saveRubric()}>
            {busy ? "Saving…" : "Save questions"}
          </button>
        </div>
      ) : null}
      {editing && draft && typeof document !== "undefined"
        ? createPortal(
            <>
              <div className="ks-side-drawer-scrim" onMouseDown={closeEditor} />
              <aside className="ks-side-drawer rq-drawer" role="dialog" aria-modal="true" aria-label="Edit question">
                <header className="ks-side-drawer-head">
                  <h2>Edit question</h2>
                  <button type="button" className="secondary rq-drawer-x" onClick={closeEditor} aria-label="Close">
                    ✕
                  </button>
                </header>
                <label>
                  Question
                  <textarea
                    rows={2}
                    maxLength={MAX_ASK}
                    value={draft.ask}
                    onChange={(e) => setDraft({ ...draft, ask: e.target.value })}
                    placeholder="As you would ask it in the home"
                  />
                </label>
                <label>
                  Short name
                  <input
                    value={draft.label}
                    onChange={(e) => setDraft({ ...draft, label: e.target.value })}
                    placeholder="Used in reports and lists"
                  />
                </label>
                <div className="rq-field-block">
                  <span className="rq-field-label">Answer type</span>
                  <span className="rq-types" role="radiogroup" aria-label="Answer type">
                    {ANSWER_TYPES.map((t) => (
                      <button
                        key={t.value}
                        type="button"
                        role="radio"
                        aria-checked={draft.inputType === t.value}
                        className={`rq-type${draft.inputType === t.value ? " is-on" : ""}`}
                        onClick={() => setDraft({ ...draft, inputType: t.value })}
                      >
                        {t.label}
                      </button>
                    ))}
                  </span>
                </div>
                {draft.inputType === "rating" ? (
                  <div className="rq-field-block">
                    <span className="rq-field-label">Answer options</span>
                    {draft.options.length ? (
                      <ul className="rq-opt-edit">
                        {draft.options.map((o, k) => (
                          <li key={k} className={`rq-opt-row rq-opt-row-${TONE[o.rating]}`}>
                            <input
                              value={o.label}
                              maxLength={MAX_OPTION_LABEL}
                              onChange={(e) => setOption(k, { label: e.target.value })}
                              placeholder="What the caregiver sees"
                              aria-label={`Option ${k + 1}`}
                            />
                            <select
                              value={o.rating}
                              onChange={(e) => setOption(k, { rating: e.target.value as OptionRating })}
                              aria-label={`Option ${k + 1} means`}
                              title="Means"
                            >
                              {OPTION_RATINGS.map((r) => (
                                <option key={r} value={r}>
                                  {RATING_MEANS[r]}
                                </option>
                              ))}
                            </select>
                            <button
                              type="button"
                              className="secondary rq-icon-btn rq-opt-x"
                              onClick={() => setDraft({ ...draft, options: draft.options.filter((_, j) => j !== k) })}
                              aria-label={`Remove option ${k + 1}`}
                              title="Remove"
                            >
                              ✕
                            </button>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="muted rq-note">No options. Add one, or the standard options are used.</p>
                    )}
                    <span className="rq-opt-actions">
                      <button
                        type="button"
                        className="secondary"
                        disabled={draft.options.length >= MAX_OPTIONS}
                        onClick={() =>
                          setDraft({ ...draft, options: [...draft.options, { label: "", rating: "excellent" }] })
                        }
                      >
                        + Add option
                      </button>
                      <button
                        type="button"
                        className="secondary"
                        disabled={!draft.options.length}
                        onClick={() => setDraft({ ...draft, options: [] })}
                      >
                        Clear all
                      </button>
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => setDraft({ ...draft, options: standardOptions(draftHelpItem(draft)) })}
                      >
                        Reset to standard
                      </button>
                    </span>
                  </div>
                ) : (
                  <p className="muted rq-note">
                    {draft.inputType === "yesno" ? "The caregiver sees Yes, No and N/A." : "The caregiver types an answer."}
                  </p>
                )}
                <label>
                  What to look for
                  <textarea
                    rows={2}
                    value={draft.lookFor}
                    onChange={(e) => setDraft({ ...draft, lookFor: e.target.value })}
                    placeholder="One short line for the caregiver"
                  />
                </label>
                {draft.guide ? (
                  <details className="rq-guide">
                    <summary>Full guide for assessors</summary>
                    <textarea
                      rows={6}
                      value={draft.guide}
                      onChange={(e) => setDraft({ ...draft, guide: e.target.value })}
                      aria-label="Full guide for assessors"
                    />
                  </details>
                ) : null}
                <div className="rq-drawer-grid">
                  <label>
                    Points
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={draft.maxPoints}
                      onChange={(e) => setDraft({ ...draft, maxPoints: Number(e.target.value) || 1 })}
                    />
                  </label>
                  <label>
                    Source
                    <select
                      value={draft.source}
                      onChange={(e) => setDraft({ ...draft, source: e.target.value as RubricItemSource })}
                    >
                      {RUBRIC_SOURCE_ORDER.map((src) => (
                        <option key={src} value={src}>
                          {src === "aarp" ? "AARP" : src === "cdc" ? "CDC" : `${publicBrandName()} standard`}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <label className="rq-check">
                  <input
                    type="checkbox"
                    checked={draft.visitQuestion}
                    onChange={(e) => setDraft({ ...draft, visitQuestion: e.target.checked })}
                  />
                  Ask on every visit
                </label>
                <div className="rq-drawer-danger">
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => {
                      updateItem(editing.catId, editing.itemId, { hidden: !draft.hidden });
                      closeEditor();
                    }}
                    title={draft.hidden ? "Ask this question again" : "Stop asking this question (old reports keep it)"}
                  >
                    {draft.hidden ? "Show question" : "Hide question"}
                  </button>
                  <button
                    type="button"
                    className="secondary rq-remove"
                    onClick={() => {
                      if (removeItem(editing.catId, editing.itemId, draft.label)) closeEditor();
                    }}
                  >
                    Remove
                  </button>
                </div>
                <div className="rq-drawer-foot">
                  <button type="button" className="secondary" onClick={closeEditor}>
                    Cancel
                  </button>
                  <button type="button" className="primary" onClick={applyDraft}>
                    Save
                  </button>
                </div>
              </aside>
            </>,
            document.body,
          )
        : null}
    </div>
  );
}
