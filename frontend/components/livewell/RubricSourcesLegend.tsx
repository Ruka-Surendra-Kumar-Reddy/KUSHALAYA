"use client";

import type { AssessmentCategory } from "@/lib/livewell/assessment";
import {
  RUBRIC_SOURCES,
  RUBRIC_SOURCE_ORDER,
  countItemsBySource,
} from "@/lib/livewell/rubric-sources";
import { RubricSourceBadge } from "@/components/livewell/RubricSourceBadge";
import { publicBrandName } from "@/lib/public-brand";

export function RubricSourcesLegend({
  categories,
  compact = false,
}: {
  categories: AssessmentCategory[];
  compact?: boolean;
}) {
  const allItems = categories.flatMap((c) => c.items);
  const counts = countItemsBySource(allItems);

  return (
    <div className={`home-safety-sources-legend${compact ? " compact" : ""}`}>
      <p className="home-safety-sources-legend-intro muted">
        Checklist items are drawn from established fall-prevention frameworks and the{" "}
        {publicBrandName()} standard ({allItems.length} items).
      </p>
      <div className="home-safety-sources-legend-grid">
        {RUBRIC_SOURCE_ORDER.map((id) => {
          const meta = RUBRIC_SOURCES[id];
          return (
            <div key={id} className="home-safety-sources-legend-card">
              <div className="home-safety-sources-legend-head">
                <RubricSourceBadge source={id} />
                <strong>{meta.label}</strong>
                <span className="muted home-safety-sources-count">{counts[id]} items</span>
              </div>
              {!compact && (
                <>
                  <p className="muted home-safety-sources-desc">{meta.description}</p>
                  <p className="muted home-safety-sources-ref">{meta.reference}</p>
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
