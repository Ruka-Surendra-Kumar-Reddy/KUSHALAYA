"use client";

import { useEffect, useState } from "react";
import { inr } from "@/lib/business";
import { fetchAiUsage, type AiUsage } from "@/lib/aiPreview";

/** Owner dashboard: AI calls this month and estimated provider cost, per feature. */
export function AiUsageCard() {
  const [u, setU] = useState<AiUsage | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    fetchAiUsage().then(setU).catch(() => setFailed(true));
  }, []);
  return (
    <section className="card od-card">
      <h2>AI usage</h2>
      {failed ? (
        <p className="od-sub">Not available.</p>
      ) : !u ? (
        <p className="od-sub">Loading…</p>
      ) : (
        <>
          <span className="od-big">{inr(u.estimated_cost_paise)}</span>
          <p className="od-sub">estimated this month · {u.total_calls} AI calls</p>
          <ul className="od-rows">
            {u.features.map((f) => (
              <li key={f.feature}>
                <span>
                  {f.label} ({f.calls}
                  {f.cache_hits ? ` + ${f.cache_hits} reused` : ""})
                </span>
                <span>{inr(f.estimated_cost_paise)}</span>
              </li>
            ))}
          </ul>
          <p className="od-sub">
            Previews today {u.previews_today} of {u.daily_cap}
          </p>
        </>
      )}
    </section>
  );
}
