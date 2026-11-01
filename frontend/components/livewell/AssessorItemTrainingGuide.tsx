"use client";

import { useMemo, useState } from "react";
import type { AssessmentCategory } from "@/lib/livewell/assessment";
import {
  lookForText,
  trainingByCategoryId,
  trainingForItem,
  type AssessorItemTraining,
} from "@/lib/livewell/assessor-item-training";

function TrainingItem({ entry }: { entry: AssessorItemTraining }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`home-safety-training-item${open ? " is-open" : ""}`}>
      <button
        type="button"
        className="home-safety-training-item-toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span>{entry.label}</span>
        <span aria-hidden>{open ? "−" : "+"}</span>
      </button>
      {open ? (
        <div className="home-safety-training-item-body">
          <p>
            <strong>Look for:</strong> {lookForText(entry)}
          </p>
          <ul className="home-safety-training-ratings">
            <li>
              <span className="home-safety-training-rating-key">★ Excellent</span>
              {entry.excellent}
            </li>
            <li>
              <span className="home-safety-training-rating-key">~ Acceptable</span>
              {entry.acceptable}
            </li>
            <li>
              <span className="home-safety-training-rating-key">✕ Unsafe</span>
              {entry.unsafe}
            </li>
            <li>
              <span className="home-safety-training-rating-key">— N/A</span>
              {entry.naWhen}
            </li>
          </ul>
          {entry.tip ? (
            <p className="home-safety-training-tip">
              <strong>Tip:</strong> {entry.tip}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function AssessorItemTrainingGuide({
  categories,
  defaultOpen = false,
}: {
  categories: AssessmentCategory[];
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const [query, setQuery] = useState("");
  const sections = useMemo(() => {
    const q = query.trim().toLowerCase();
    return categories
      .map((cat) => {
        let items = trainingByCategoryId(cat.id);
        if (!items.length) {
          items = cat.items
            .map((item) => trainingForItem(item.id) || trainingForItem(item.label))
            .filter(Boolean) as AssessorItemTraining[];
        }
        if (q) {
          items = items.filter(
            (t) =>
              t.label.toLowerCase().includes(q) ||
              t.lookFor.toLowerCase().includes(q) ||
              t.excellent.toLowerCase().includes(q),
          );
        }
        return { cat, items };
      })
      .filter((s) => s.items.length > 0);
  }, [categories, query]);

  const total = sections.reduce((n, s) => n + s.items.length, 0);

  return (
    <section className="card home-safety-guide home-safety-training-guide">
      <button
        type="button"
        className="home-safety-guide-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span>Assessor item training — what to look for &amp; how to rate</span>
        <span aria-hidden>{open ? "▲" : "▼"}</span>
      </button>
      {open ? (
        <div className="home-safety-guide-body">
          <p>
            For every checklist item: what to observe, and how to choose{" "}
            <strong>Excellent</strong>, <strong>Acceptable</strong>, <strong>Unsafe</strong>, or{" "}
            <strong>N/A</strong>. Same guidance appears behind the <strong>?</strong> on each
            question during an assessment.
          </p>
          <label className="home-safety-training-search">
            <span className="muted">Search items</span>
            <input aria-label="Search items"
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. transfer, grab bar, SOS…"
            />
          </label>
          <p className="muted home-safety-training-count">
            Showing {total} item{total === 1 ? "" : "s"}
          </p>
          {sections.map(({ cat, items }) => (
            <div key={cat.id} className="home-safety-training-section">
              <h3>
                {cat.sectionNumber ? `${cat.sectionNumber}. ` : ""}
                {cat.title}
              </h3>
              {items.map((entry) => (
                <TrainingItem key={entry.id} entry={entry} />
              ))}
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
