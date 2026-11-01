"use client";

import { useState } from "react";
import {
  SAFEHOME360_GRADE_TABLE,
  SAFEHOME360_TITLE,
  SAFEHOME360_VERSION,
  type AssessmentCategory,
} from "@/lib/livewell/assessment";
import { RubricSourcesLegend } from "@/components/livewell/RubricSourcesLegend";
import { RubricSourceBadge } from "@/components/livewell/RubricSourceBadge";
import { countItemsBySource } from "@/lib/livewell/rubric-sources";
import { publicBrandName, publicSafetyScoreName } from "@/lib/public-brand";

export function ScoringGuide({
  categories,
  defaultOpen = false,
}: {
  categories: AssessmentCategory[];
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const rawMax = categories.reduce((s, c) => s + c.maxPoints, 0);
  const sourceCounts = countItemsBySource(categories.flatMap((c) => c.items));

  return (
    <section className="card home-safety-guide">
      <button
        type="button"
        className="home-safety-guide-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span>{SAFEHOME360_TITLE} scoring (v{SAFEHOME360_VERSION})</span>
        <span aria-hidden>{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="home-safety-guide-body">
          <p>
            Each applicable question is rated and normalized to a{" "}
            <strong>{publicSafetyScoreName()} (0–100)</strong>. Section weights total{" "}
            <strong>{rawMax}</strong> raw points across {categories.length} scored sections.
            Conditional logic skips irrelevant items (stairs, smart home, etc.).
          </p>
          <table className="home-safety-guide-table">
            <thead>
              <tr>
                <th>Rating</th>
                <th>Standard (2/1/0)</th>
                <th>Critical (4/2/0)</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Excellent ★</td>
                <td>100%</td>
                <td>100%</td>
              </tr>
              <tr>
                <td>Acceptable ~</td>
                <td>50%</td>
                <td>50%</td>
              </tr>
              <tr>
                <td>Unsafe ✕</td>
                <td>0%</td>
                <td>0%</td>
              </tr>
              <tr>
                <td>N/A —</td>
                <td colSpan={2}>Excluded from score</td>
              </tr>
            </tbody>
          </table>
          <h3>Checklist sources</h3>
          <RubricSourcesLegend categories={categories} compact />
          <h3>Safety grade</h3>
          <table className="home-safety-guide-table">
            <thead>
              <tr>
                <th>Score</th>
                <th>Grade</th>
              </tr>
            </thead>
            <tbody>
              {SAFEHOME360_GRADE_TABLE.map((row) => (
                <tr key={row.grade}>
                  <td>{row.min === 0 ? "Below 65" : `${row.min}–100`}</td>
                  <td>
                    <strong>{row.grade}</strong>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <h3>Sections</h3>
          <ul className="home-safety-guide-cats">
            {categories.map((cat) => {
              const catCounts = countItemsBySource(cat.items);
              // "safehome360" is the legacy id for the in-house source; count both.
              const catBrandCount = catCounts.livewell360 + catCounts.safehome360;
              return (
                <li key={cat.id}>
                  <strong>
                    {cat.sectionNumber ? `${cat.sectionNumber}. ` : ""}
                    {cat.title}
                  </strong>{" "}
                  — {cat.maxPoints} pts ({cat.items.length} items)
                  <span className="home-safety-guide-cat-sources">
                    {catCounts.aarp > 0 && <RubricSourceBadge source="aarp" title={`${catCounts.aarp} AARP items`} />}
                    {catCounts.cdc > 0 && <RubricSourceBadge source="cdc" title={`${catCounts.cdc} CDC items`} />}
                    {catBrandCount > 0 && (
                      <RubricSourceBadge
                        source="livewell360"
                        title={`${catBrandCount} ${publicBrandName()} items`}
                      />
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
          <p className="muted home-safety-guide-source-total">
            Total: {sourceCounts.aarp} AARP · {sourceCounts.cdc} CDC ·{" "}
            {sourceCounts.livewell360 + sourceCounts.safehome360} {publicBrandName()}
          </p>
        </div>
      )}
    </section>
  );
}
