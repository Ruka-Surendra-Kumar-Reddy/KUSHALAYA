"use client";

/**
 * AI room hazard check: numbered boxes over the photo, a hazard list staff confirm
 * or reject, room-by-room chips, and "Show it fixed" links to the AI room preview.
 * Nothing is applied until a person confirms it.
 */
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./ai-hazard.css";
import { fetchStaffPhotoBlob } from "@/lib/livewell/aiVisualizations";
import {
  bandText,
  carryOverHazards,
  decideHazard,
  defaultRating,
  getHazardCheck,
  isRunning,
  listHazardChecks,
  pendingCarryOver,
  previewProductCodes,
  roomChipText,
  rupeesInclGst,
  showItFixedHref,
  splitByBand,
  startHazardCheck,
  type CarriedHazard,
  type HazardCheck,
  type HazardRating,
  type HazardSummary,
  type PendingCarryOver,
  type RoomHazard,
} from "@/lib/livewell/aiHazardCheck";

export const HAZARDS_CHANGED_EVENT = "ks-hazards-changed";

function announceChange() {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(HAZARDS_CHANGED_EVENT));
}

/** Re-runs `load` whenever any hazard panel on the page changes something. */
function useOnHazardsChanged(load: () => void) {
  useEffect(() => {
    window.addEventListener(HAZARDS_CHANGED_EVENT, load);
    return () => window.removeEventListener(HAZARDS_CHANGED_EVENT, load);
  }, [load]);
}

export type ApplyHazard = { rubricItemId: string; rating: HazardRating; note: string };

// --- photo with numbered boxes ---------------------------------------------------

export function HazardPhotoOverlay({
  src,
  hazards,
  activeN,
  onPick,
  alt,
}: {
  src: string | null;
  hazards: RoomHazard[];
  activeN?: number | null;
  onPick?: (n: number) => void;
  alt?: string;
}) {
  const boxed = hazards.filter((h) => h.box);
  return (
    <figure className="hz-photo">
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt={alt || "Room photo"} />
      ) : (
        <div className="hz-photo-empty">Loading photo…</div>
      )}
      {src && boxed.length > 0 ? (
        <svg className="hz-photo-svg" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          {boxed.map((h) => {
            const [x, y, w, hgt] = h.box!;
            return (
              <rect
                key={h.n}
                className={`hz-box hz-box-${h.severity}${activeN === h.n ? " is-active" : ""}${
                  h.decision === "rejected" ? " is-rejected" : ""
                }`}
                x={x * 100}
                y={y * 100}
                width={w * 100}
                height={hgt * 100}
                vectorEffect="non-scaling-stroke"
                rx={0.8}
              />
            );
          })}
        </svg>
      ) : null}
      {src
        ? boxed.map((h) => (
            <button
              key={h.n}
              type="button"
              className={`hz-pin hz-pin-${h.severity}${activeN === h.n ? " is-active" : ""}${
                h.decision === "rejected" ? " is-rejected" : ""
              }`}
              style={{ left: `${h.box![0] * 100}%`, top: `${h.box![1] * 100}%` }}
              onClick={() => onPick?.(h.n)}
              aria-label={`Hazard ${h.n}: ${h.label}`}
            >
              {h.n}
            </button>
          ))
        : null}
    </figure>
  );
}

// --- room chips ------------------------------------------------------------------

export function RoomHazardChips({ summary }: { summary: HazardSummary | null }) {
  if (!summary || summary.rooms.length === 0) return null;
  return (
    <ul className="hz-chips" aria-label="Confirmed hazards by room">
      {summary.rooms.map((r) => (
        <li key={r.room} className={`hz-chip${r.urgent ? " has-urgent" : ""}`}>
          {roomChipText(r)}
        </li>
      ))}
    </ul>
  );
}

/** Small "N AI-checked hazards" count for headers (assessment + client page). */
export function HazardCountChip({ assessmentId, elderId }: { assessmentId?: string | null; elderId?: number | null }) {
  const [summary, setSummary] = useState<HazardSummary | null>(null);
  const load = useCallback(() => {
    if (!assessmentId && elderId == null) return;
    listHazardChecks({ assessmentId, elderId })
      .then((r) => setSummary(r.summary))
      .catch(() => setSummary(null));
  }, [assessmentId, elderId]);
  useEffect(load, [load]);
  useOnHazardsChanged(load);
  if (!summary || summary.total_confirmed === 0) return null;
  return (
    <span className={`hz-count${summary.total_urgent ? " has-urgent" : ""}`} title="Hazards confirmed from AI room checks">
      {summary.total_confirmed} confirmed hazard{summary.total_confirmed === 1 ? "" : "s"}
      {summary.total_urgent ? ` · ${summary.total_urgent} urgent` : ""}
    </span>
  );
}

// --- one hazard row --------------------------------------------------------------

function HazardRow({
  h,
  check,
  canEdit,
  ticked,
  onTick,
  rating,
  onRating,
  active,
  onFocus,
  onReject,
  busy,
}: {
  h: RoomHazard;
  check: HazardCheck;
  canEdit: boolean;
  ticked: boolean;
  onTick: (v: boolean) => void;
  rating: HazardRating;
  onRating: (r: HazardRating) => void;
  active: boolean;
  onFocus: () => void;
  onReject: () => void;
  busy: boolean;
}) {
  const codes = previewProductCodes(h.products);
  return (
    <li
      className={`hz-item hz-item-${h.decision}${active ? " is-active" : ""}`}
      onMouseEnter={onFocus}
      onFocus={onFocus}
    >
      <div className="hz-item-head">
        <span className={`hz-num hz-num-${h.severity}`}>{h.n}</span>
        <div className="hz-item-title">
          <strong>{h.label}</strong>
          <span className="hz-item-meta">
            {h.room_label}
            <span className={`hz-sev hz-sev-${h.severity}`}>{h.severity_label}</span>
            <span className={`hz-conf hz-conf-${h.band}`}>
              {h.confidence}% · {bandText(h.band)}
            </span>
            {!h.box ? <span className="hz-nobox">no single spot in photo</span> : null}
          </span>
        </div>
      </div>
      {h.evidence ? <p className="hz-evidence">AI saw: {h.evidence}</p> : null}
      {h.question ? (
        <p className="hz-question">
          Assessment question: <em>{h.question}</em>
        </p>
      ) : null}

      {h.decision === "pending" && canEdit ? (
        <div className="hz-actions">
          <label className="hz-tick">
            <input type="checkbox" checked={ticked} onChange={(e) => onTick(e.target.checked)} disabled={busy} />
            Confirm
          </label>
          {h.rubric_item_id ? (
            <select
              value={rating}
              onChange={(e) => onRating(e.target.value as HazardRating)}
              aria-label="Rating to record"
              disabled={busy}
            >
              <option value="unsafe">Risk</option>
              <option value="acceptable">Needs attention</option>
            </select>
          ) : null}
          <button type="button" className="secondary hz-reject" onClick={onReject} disabled={busy}>
            Not right
          </button>
        </div>
      ) : null}
      {h.decision === "pending" && !canEdit ? <p className="hz-status">Waiting for staff to check</p> : null}
      {h.decision === "rejected" ? (
        <p className="hz-status">Marked not right{h.decided_by ? ` by ${h.decided_by}` : ""}</p>
      ) : null}

      {h.decision === "confirmed" ? (
        <div className="hz-fix">
          <p className="hz-status hz-status-ok">
            {h.source || "Confirmed"} · {h.rating === "acceptable" ? "Needs attention" : "Risk"}
            {h.applied_to ? " · added to the assessment" : h.rubric_item_id ? " · kept for the next assessment" : ""}
          </p>
          {h.products.length ? (
            <ul className="hz-products">
              {h.products.slice(0, 4).map((p) => (
                <li key={p.product_code}>
                  <span>{p.name}</span>
                  <span className="hz-price">{rupeesInclGst(p)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="hz-status">No catalog product linked yet — {h.solution_name}</p>
          )}
          {codes.length ? (
            <Link
              className="hz-show-fixed"
              href={showItFixedHref({ assessmentId: check.assessment_id, documentId: check.document_id, productCodes: codes })}
            >
              Show it fixed →
            </Link>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

// --- the panel -------------------------------------------------------------------

export function HazardCheckPanel({
  documentId,
  roomType,
  assessmentId,
  canEdit,
  photoSrc,
  initialCheck,
  autoStart,
  onApplied,
}: {
  documentId: number;
  roomType?: string | null;
  assessmentId?: string | null;
  canEdit: boolean;
  photoSrc?: string | null;
  initialCheck?: HazardCheck | null;
  autoStart?: boolean;
  /** Called after confirm so the open assessment draft shows the rating straight away. */
  onApplied?: (items: ApplyHazard[]) => void;
}) {
  const [check, setCheck] = useState<HazardCheck | null>(initialCheck ?? null);
  const [loaded, setLoaded] = useState(Boolean(initialCheck));
  const [src, setSrc] = useState<string | null>(photoSrc ?? null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showLow, setShowLow] = useState(false);
  const [activeN, setActiveN] = useState<number | null>(null);
  const [ticks, setTicks] = useState<Record<number, boolean>>({});
  const [ratings, setRatings] = useState<Record<number, HazardRating>>({});
  const started = useRef(false);

  useEffect(() => {
    if (photoSrc !== undefined) {
      setSrc(photoSrc);
      return;
    }
    let url: string | null = null;
    let cancelled = false;
    fetchStaffPhotoBlob(documentId)
      .then((u) => {
        url = u;
        if (!cancelled) setSrc(u);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
      if (url?.startsWith("blob:")) URL.revokeObjectURL(url);
    };
  }, [documentId, photoSrc]);

  useEffect(() => {
    if (initialCheck) return;
    let cancelled = false;
    listHazardChecks({ documentId })
      .then((r) => {
        if (!cancelled) setCheck(r.checks[0] ?? null);
      })
      .catch(() => undefined)
      .finally(() => !cancelled && setLoaded(true));
    return () => {
      cancelled = true;
    };
  }, [documentId, initialCheck]);

  // Pre-tick the high-confidence ones; never auto-confirm.
  useEffect(() => {
    if (!check || check.status !== "succeeded") return;
    setTicks((prev) => {
      const next = { ...prev };
      for (const h of check.hazards) if (next[h.n] === undefined) next[h.n] = h.band === "high";
      return next;
    });
    setRatings((prev) => {
      const next = { ...prev };
      for (const h of check.hazards) if (!next[h.n]) next[h.n] = defaultRating(h);
      return next;
    });
  }, [check]);

  // Poll while the background job runs.
  useEffect(() => {
    if (!check || !isRunning(check)) return;
    let tries = 0;
    const t = window.setInterval(() => {
      tries += 1;
      getHazardCheck(check.id)
        .then((c) => {
          setCheck(c);
          if (!isRunning(c)) announceChange();
        })
        .catch(() => undefined);
      if (tries > 60) window.clearInterval(t);
    }, 1500);
    return () => window.clearInterval(t);
  }, [check]);

  const run = useCallback(
    async (force = false) => {
      setError("");
      setBusy(true);
      try {
        const c = await startHazardCheck({ documentId, roomType, assessmentId, force });
        setTicks({});
        setRatings({});
        setCheck(c);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not start the check.");
      } finally {
        setBusy(false);
      }
    },
    [documentId, roomType, assessmentId],
  );

  useEffect(() => {
    if (autoStart && loaded && !check && canEdit && !started.current) {
      started.current = true;
      void run();
    }
  }, [autoStart, loaded, check, canEdit, run]);

  const { shown, low } = useMemo(() => splitByBand(check?.hazards ?? []), [check]);
  const visible = showLow ? [...shown, ...low] : shown;
  const tickedPending = visible.filter((h) => h.decision === "pending" && ticks[h.n]);

  async function decide(list: RoomHazard[], decision: "confirm" | "reject") {
    if (!check || !list.length) return;
    setBusy(true);
    setError("");
    try {
      let latest = check;
      const applied: ApplyHazard[] = [];
      for (const h of list) {
        latest = await decideHazard(check.id, h.n, decision, decision === "confirm" ? ratings[h.n] : undefined);
        const after = latest.hazards.find((x) => x.n === h.n);
        if (decision === "confirm" && after?.applied_to && after.rubric_item_id) {
          applied.push({ rubricItemId: after.rubric_item_id, rating: after.rating || "unsafe", note: after.source || "" });
        }
      }
      setCheck(latest);
      if (applied.length) onApplied?.(applied);
      announceChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  }

  if (!loaded) return <div className="hz-panel"><p className="muted">Loading…</p></div>;

  return (
    <div className="hz-panel">
      {error ? (
        <p className="hz-error" role="alert">
          {error}
        </p>
      ) : null}

      {!check ? (
        <div className="hz-start">
          <p className="muted">AI looks for hazards from our checklist. You confirm each one; nothing is added by itself.</p>
          {canEdit ? (
            <button type="button" onClick={() => void run()} disabled={busy}>
              {busy ? "Starting…" : "Check this room with AI"}
            </button>
          ) : (
            <p className="muted">Not checked yet.</p>
          )}
        </div>
      ) : isRunning(check) ? (
        <div className="hz-progress" aria-live="polite">
          <div className="hz-progress-bar">
            <span style={{ width: check.stage === "Checking hazards…" ? "70%" : "30%" }} />
          </div>
          <p>{check.stage || "Working…"} This usually takes 5–15 seconds.</p>
        </div>
      ) : check.status === "failed" ? (
        <div className="hz-start">
          <p className="hz-error">{check.error_message || "The check did not finish."}</p>
          {canEdit ? (
            <button type="button" onClick={() => void run()} disabled={busy}>
              Try again
            </button>
          ) : null}
        </div>
      ) : (
        <div className="hz-result">
          <HazardPhotoOverlay src={src} hazards={visible} activeN={activeN} onPick={setActiveN} />
          <div className="hz-list-wrap">
            <div className="hz-list-head">
              <strong>
                {shown.length ? `${shown.length} possible hazard${shown.length === 1 ? "" : "s"}` : "No clear hazards found"}
              </strong>
              {check.cache_hit ? <span className="muted"> · same photo checked before</span> : null}
            </div>
            {visible.length ? (
              <ol className="hz-list">
                {visible.map((h) => (
                  <HazardRow
                    key={h.n}
                    h={h}
                    check={check}
                    canEdit={canEdit}
                    ticked={Boolean(ticks[h.n])}
                    onTick={(v) => setTicks((t) => ({ ...t, [h.n]: v }))}
                    rating={ratings[h.n] || defaultRating(h)}
                    onRating={(r) => setRatings((x) => ({ ...x, [h.n]: r }))}
                    active={activeN === h.n}
                    onFocus={() => setActiveN(h.n)}
                    onReject={() => void decide([h], "reject")}
                    busy={busy}
                  />
                ))}
              </ol>
            ) : (
              <p className="muted">The AI did not see anything from our checklist. Check the room yourself as usual.</p>
            )}
            {low.length ? (
              <button type="button" className="hz-link" onClick={() => setShowLow((v) => !v)}>
                {showLow ? "Hide low-confidence" : `Show low-confidence (${low.length})`}
              </button>
            ) : null}
            {canEdit && tickedPending.length ? (
              <div className="hz-confirm-bar">
                <button type="button" onClick={() => void decide(tickedPending, "confirm")} disabled={busy}>
                  {busy ? "Saving…" : `Confirm ticked (${tickedPending.length})`}
                </button>
              </div>
            ) : null}
            {canEdit ? (
              <button type="button" className="hz-link" onClick={() => void run(true)} disabled={busy}>
                Check again
              </button>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}

// --- carry-over prompt (reassessment) ---------------------------------------------

export function HazardCarryOver({
  elderId,
  assessmentId,
  onApplied,
}: {
  elderId: number;
  assessmentId: string;
  onApplied: (items: ApplyHazard[]) => void;
}) {
  const [items, setItems] = useState<PendingCarryOver[]>([]);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<CarriedHazard[] | null>(null);
  useEffect(() => {
    pendingCarryOver(elderId, assessmentId)
      .then((r) => setItems(r.hazards))
      .catch(() => setItems([]));
  }, [elderId, assessmentId]);
  if (done) {
    return <p className="hz-carry hz-status-ok">Added {done.length} hazard{done.length === 1 ? "" : "s"} from earlier room checks.</p>;
  }
  if (!items.length) return null;
  return (
    <div className="hz-carry">
      <p>
        <strong>{items.length}</strong> hazard{items.length === 1 ? "" : "s"} confirmed in earlier room checks:{" "}
        {items.map((i) => `${i.label} (${i.room_label})`).join("; ")}
      </p>
      <button
        type="button"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            const r = await carryOverHazards(assessmentId);
            onApplied(r.applied.map((a) => ({ rubricItemId: a.rubric_item_id, rating: a.rating, note: a.note })));
            setDone(r.applied);
            announceChange();
          } finally {
            setBusy(false);
          }
        }}
      >
        Add to this assessment
      </button>
    </div>
  );
}

// --- assessment summary block ------------------------------------------------------

export function AssessmentHazardSummary({ assessmentId }: { assessmentId: string }) {
  const [summary, setSummary] = useState<HazardSummary | null>(null);
  const load = useCallback(() => {
    listHazardChecks({ assessmentId })
      .then((r) => setSummary(r.summary))
      .catch(() => setSummary(null));
  }, [assessmentId]);
  useEffect(load, [load]);
  useOnHazardsChanged(load);
  if (!summary || (summary.total_confirmed === 0 && summary.pending === 0)) return null;
  return (
    <div className="hz-summary">
      <span className="hz-summary-title">AI room check</span>
      <RoomHazardChips summary={summary} />
      {summary.pending ? <span className="hz-pending">{summary.pending} waiting for you to check</span> : null}
    </div>
  );
}
