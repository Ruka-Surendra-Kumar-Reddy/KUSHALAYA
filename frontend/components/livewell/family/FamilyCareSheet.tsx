"use client";

import { useEffect, useState } from "react";
import { familyApi } from "@/lib/livewell/familyApi";
import { CareSheetView } from "@/components/CareSheetView";
import { shortDate, type FamilyCareView } from "@/lib/clientCare";
import { istToday } from "@/lib/schedule";

/** Family: the care sheet (read-only, no keys/access) and the care plan goals in plain words. */
export function FamilyCareSheet() {
  const [view, setView] = useState<FamilyCareView | null>(null);

  useEffect(() => {
    familyApi<FamilyCareView>("/care-sheet").then(setView).catch(() => undefined);
  }, []);

  if (!view) return null;
  return (
    <>
      <CareSheetView sheet={view.sheet} showContacts={false} />
      <h3 style={{ margin: "1.2rem 0 0.4rem" }}>Care plan goals</h3>
      {view.goals.length ? (
        <ul className="cc-list">
          {view.goals.map((g) => (
            <li key={g.id}>
              <div className="cc-row">
                <strong>{g.goal}</strong>
                <span className={`cc-tag ${g.status === "achieved" ? "is-good" : ""}`}>{g.status_label}</span>
                {g.target_date ? <span className="cc-small">by {shortDate(g.target_date)}</span> : null}
              </div>
              {g.interventions.length ? (
                <p className="cc-small" style={{ margin: "0.3rem 0 0" }}>
                  What we do: {g.interventions.join("; ")}
                </p>
              ) : null}
              {g.progress ? <p style={{ margin: "0.3rem 0 0" }}>How it is going: {g.progress}</p> : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">Goals are agreed with you after the home assessment.</p>
      )}
      {view.next_review ? (
        view.next_review.slice(0, 10) < istToday() ? (
          <p className="muted">Care plan review due soon — your Family Partner will be in touch.</p>
        ) : (
          <p className="muted">Next care plan review: {shortDate(view.next_review)}</p>
        )
      ) : null}
    </>
  );
}
