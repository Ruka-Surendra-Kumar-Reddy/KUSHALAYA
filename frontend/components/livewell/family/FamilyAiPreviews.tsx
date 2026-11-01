"use client";

import { useEffect, useState } from "react";
import { BeforeAfterSlider } from "@/components/BeforeAfterSlider";
import { useAuthedImage } from "@/components/useAuthedImage";
import { inr } from "@/lib/business";
import { withPublicBrand } from "@/lib/public-brand";
import { downloadPreview, fetchFamilyPreviews, requestPreviewFixes, type FamilyPreview } from "@/lib/aiPreview";
import "./ai-preview.css";

function PreviewCard({ v }: { v: FamilyPreview }) {
  const before = useAuthedImage(v.before_url);
  const after = useAuthedImage(v.after_url);
  const [state, setState] = useState<"idle" | "busy" | "done">("idle");
  const [error, setError] = useState("");

  async function request() {
    setState("busy");
    setError("");
    try {
      await requestPreviewFixes(v.id);
      setState("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not send the request");
      setState("idle");
    }
  }

  return (
    <article className="fh-ap-card" aria-label={v.label}>
      <h4 className="fh-ap-title">{v.label}</h4>
      {before && after ? (
        <BeforeAfterSlider
          beforeSrc={before}
          afterSrc={after}
          beforeAlt={`${v.label}: the room now`}
          afterAlt={`${v.label}: illustration with the suggested safety products`}
          markers={v.markers}
        />
      ) : (
        <div className="fh-ap-wait" role="status">
          Loading pictures…
        </div>
      )}
      {v.items.length ? (
        <>
          <ol className="fh-ap-items">
            {v.items.map((i) => (
              <li key={i.n}>
                <span className="fh-ap-n" aria-hidden="true">
                  {i.n}
                </span>
                <span className="fh-ap-name">{i.name}</span>
                <span className="fh-ap-price">{i.priced ? inr(i.price_with_gst_paise) : "Price on request"}</span>
              </li>
            ))}
          </ol>
          {/* One total on the page: the fixes total under "What to fix and the cost".
              This picture shows more than the findings need, so it lists prices only. */}
          <p className="fh-ap-total">
            <span>Prices incl. GST. The total for your fixes is under &ldquo;What to fix and the cost&rdquo;.</span>
          </p>
        </>
      ) : null}
      <div className="fh-ap-actions">
        {v.items.length ? (
          state === "done" ? (
            <p className="fh-ap-ok" role="status">
              Request sent. Your care team will call to confirm the work and the date.
            </p>
          ) : (
            <button type="button" className="primary" disabled={state === "busy"} onClick={() => void request()}>
              {state === "busy" ? "Sending…" : "Request these fixes"}
            </button>
          )
        ) : null}
        <button type="button" className="secondary" onClick={() => void downloadPreview(v.id, "image", true)}>
          Download picture
        </button>
        <button type="button" className="secondary" onClick={() => void downloadPreview(v.id, "pdf", true)}>
          PDF
        </button>
      </div>
      {error ? (
        <p className="fh-ap-err" role="alert">
          {error}
        </p>
      ) : null}
      <p className="fh-ap-note">{v.disclaimer}</p>
    </article>
  );
}

/** Approved AI room previews (Safety page → Photos → Before and after). */
export function FamilyAiPreviews() {
  const [rows, setRows] = useState<FamilyPreview[] | null>(null);
  useEffect(() => {
    fetchFamilyPreviews()
      .then(setRows)
      .catch(() => setRows([]));
  }, []);
  if (rows === null) return <p className="muted">Loading…</p>;
  if (rows.length === 0) {
    return (
      <p className="muted">
        {withPublicBrand(
          "When your LiveWell360 team shows a room with suggested safety changes, the before and after pictures appear here.",
        )}
      </p>
    );
  }
  return (
    <ul className="fh-ap-list">
      {rows.map((v) => (
        <li key={v.id}>
          <PreviewCard v={v} />
        </li>
      ))}
    </ul>
  );
}
