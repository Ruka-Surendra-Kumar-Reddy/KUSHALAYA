"use client";

import { useEffect, useState } from "react";
import { RatingControl } from "@/components/livewell/RatingControl";
import {
  type AssessmentCategory,
  type HomeSafetyAssessment,
  type ItemRating,
} from "@/lib/livewell/assessment";
import type { ResidentProfile } from "@/lib/livewell/resident-profile";

export function AssessmentSectionPanel({
  category,
  draft,
  onRating,
  onNote,
}: {
  category: AssessmentCategory;
  draft: HomeSafetyAssessment;
  profile: ResidentProfile;
  /** label = the option tapped; keep it in draft.answerLabels for the report. */
  onRating: (itemId: string, rating: ItemRating, label?: string) => void;
  onNote: (itemId: string, note: string) => void;
  onMarkSectionNa?: () => void;
}) {
  let lastGroup: string | undefined;

  return (
    <div className="home-safety-section-panel">
      <div className="home-safety-section-panel-head">
        <h2 className="home-safety-section-panel-title">{category.title}</h2>
      </div>

      {category.items.length === 0 ? (
        <p className="muted">No questions in this stage.</p>
      ) : (
        <div className="home-safety-rating-list">
          {category.items.map((item) => {
            const groupEl =
              item.group && item.group !== lastGroup ? (
                <h3 key={`g-${item.group}`} className="home-safety-item-group">
                  {item.group}
                </h3>
              ) : null;
            if (item.group) lastGroup = item.group;
            return (
              <div key={item.id}>
                {groupEl}
                <RatingControl
                  label={item.label}
                  help={item.help}
                  itemId={item.id}
                  value={draft.ratings[item.id] ?? null}
                  onChange={(v, label) => onRating(item.id, v, label)}
                  ask={item.ask}
                  options={item.options}
                  answerLabel={draft.answerLabels?.[item.id]}
                  note={draft.itemNotes[item.id]}
                  onNoteChange={(note) => onNote(item.id, note)}
                  scoringScale={item.scoringScale ?? "standard"}
                  source={item.source}
                  inputType={item.inputType || "rating"}
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
