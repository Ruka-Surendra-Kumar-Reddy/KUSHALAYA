"use client";

import { useId, useState } from "react";
import type { AssessmentInputType, ItemRating, RubricItemSource, ScoringScale } from "@/lib/livewell/assessment";
import { normalizeRating } from "@/lib/livewell/assessment";
import { lookForText, trainingForItem } from "@/lib/livewell/assessor-item-training";
import { questionAsk, questionOptions, type QuestionOption } from "@/lib/livewell/question-options";
import "./rating-control.css";

const OPTIONS: {
  key: ItemRating;
  icon: string;
  word: string;
  title: string;
}[] = [
  { key: "excellent", icon: "★", word: "Excellent", title: "Fully compliant" },
  { key: "acceptable", icon: "~", word: "Acceptable", title: "Minor improvement needed" },
  { key: "unsafe", icon: "✕", word: "Unsafe", title: "Immediate improvement required" },
  { key: "na", icon: "—", word: "N/A", title: "Not applicable" },
];

export function RatingControl({
  value,
  onChange,
  label,
  help,
  itemId,
  note,
  onNoteChange,
  scoringScale = "standard",
  inputType = "rating",
  ask,
  options: customOptions,
  answerLabel,
}: {
  value: ItemRating;
  /** label = the option tapped (several options may save the same rating). */
  onChange: (v: ItemRating, label?: string) => void;
  /** Admin-set question wording and options (rubric editor); else the standard ones. */
  ask?: string;
  options?: QuestionOption[];
  answerLabel?: string;
  label: string;
  help?: string;
  itemId?: string;
  note?: string;
  onNoteChange?: (note: string) => void;
  scoringScale?: ScoringScale;
  source?: RubricItemSource;
  inputType?: AssessmentInputType;
}) {
  const normalized = normalizeRating(value);
  const helpPanelId = useId();
  const [helpOpen, setHelpOpen] = useState(false);
  // "+ Add a note" link; the field stays open once a note exists (as in the caregiver app).
  const [noteOpen, setNoteOpen] = useState(false);
  const showNote = Boolean(onNoteChange) && (noteOpen || Boolean(note?.trim()));

  const training =
    (itemId ? trainingForItem(itemId) : undefined) || trainingForItem(label) || undefined;
  const hasHelp = Boolean(training || help?.trim());
  // Same question and options as the caregiver app (question-options.ts);
  // each still saves its rating, so scoring is unchanged.
  const qItem = { id: itemId || label, label, help, ask, options: customOptions };
  const opts = questionOptions(qItem);
  // The tapped option, else the first option that saves this rating (older answers).
  const onLabel =
    answerLabel && opts.some((o) => o.label === answerLabel && o.rating === normalized)
      ? answerLabel
      : opts.find((o) => o.rating === normalized)?.label;
  const ratingChoices = opts.map((o) => ({
    key: o.rating as ItemRating,
    icon: "",
    word: o.label,
    title: OPTIONS.find((x) => x.key === o.rating)?.title ?? "",
    on: normalized === o.rating && onLabel === o.label,
  }));

  return (
    <div className="home-safety-rating-block">
      <div className="home-safety-rating-label-row">
        <span className="home-safety-rating-label">
          <span>{questionAsk(qItem)}</span>
          {hasHelp ? (
            <button
              type="button"
              className={`home-safety-rating-help-btn${helpOpen ? " is-open" : ""}`}
              aria-expanded={helpOpen}
              aria-controls={helpPanelId}
              aria-label="How to rate"
              title="How to rate"
              onClick={() => setHelpOpen((open) => !open)}
            >
              <span aria-hidden>?</span>
            </button>
          ) : null}
          {scoringScale === "critical" ? (
            <span className="home-safety-rating-critical-tag">Critical</span>
          ) : null}
        </span>
      </div>
      {hasHelp && helpOpen ? (
        <div id={helpPanelId} className="home-safety-rating-help">
          {training ? (
            <>
              <p>
                <strong>Look for:</strong> {lookForText(training)}
              </p>
              <ul className="home-safety-rating-help-ratings">
                <li>
                  <strong>★ Excellent</strong> — {training.excellent}
                </li>
                <li>
                  <strong>~ Acceptable</strong> — {training.acceptable}
                </li>
                <li>
                  <strong>✕ Unsafe</strong> — {training.unsafe}
                </li>
                <li>
                  <strong>— N/A</strong> — {training.naWhen}
                </li>
              </ul>
              {training.tip ? (
                <p className="home-safety-rating-help-tip">
                  <strong>Tip:</strong> {training.tip}
                </p>
              ) : null}
            </>
          ) : (
            <p>{help}</p>
          )}
        </div>
      ) : null}
      {inputType === "text" ? (
        <textarea
          className="home-safety-notes"
          rows={2}
          value={note ?? ""}
          onChange={(e) => {
            const v = e.target.value;
            onNoteChange?.(v);
            onChange(v.trim() ? "acceptable" : null);
          }}
          placeholder="Answer"
          aria-label={label}
        />
      ) : (
        <div className="home-safety-rating-chips" role="group" aria-label={label}>
          {(inputType === "yesno"
            ? [
                { key: "excellent" as const, icon: "", word: "Yes", title: "Yes", on: normalized === "excellent" },
                { key: "unsafe" as const, icon: "", word: "No", title: "No", on: normalized === "unsafe" },
                { key: "na" as const, icon: "—", word: "N/A", title: "Not applicable", on: normalized === "na" },
              ]
            : ratingChoices
          ).map((opt, k) => (
            <button
              key={`${k}-${opt.word}`}
              type="button"
              className={`home-safety-rating-chip home-safety-rating-${opt.key}${opt.on ? " active" : ""}`}
              title={opt.title}
              aria-pressed={opt.on}
              onClick={() => (opt.on ? onChange(null) : onChange(opt.key, inputType === "yesno" ? undefined : opt.word))}
            >
              {opt.on ? (
                <span className="home-safety-rating-chip-check" aria-hidden>
                  ✓
                </span>
              ) : opt.icon ? (
                <span className="home-safety-rating-chip-icon" aria-hidden>
                  {opt.icon}
                </span>
              ) : null}
              <span className="home-safety-rating-chip-word">{opt.word}</span>
            </button>
          ))}
        </div>
      )}
      {inputType !== "text" && onNoteChange ? (
        showNote ? (
          <input
            type="text"
            className="home-safety-item-note"
            value={note ?? ""}
            onChange={(e) => onNoteChange(e.target.value)}
            placeholder="Note (optional)"
            aria-label={`Notes for ${label}`}
          />
        ) : (
          <button type="button" className="home-safety-add-note" onClick={() => setNoteOpen(true)}>
            + Add a note
          </button>
        )
      ) : null}
    </div>
  );
}
