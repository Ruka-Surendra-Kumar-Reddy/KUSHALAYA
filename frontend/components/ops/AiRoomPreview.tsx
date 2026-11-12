"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BeforeAfterSlider } from "@/components/BeforeAfterSlider";
import { BackLink } from "@/components/ops/PageActions";
import { postFormData } from "@/lib/api";
import { inr } from "@/lib/business";
import { useAuthedImage } from "@/components/useAuthedImage";
import { can } from "@/lib/roles";
import { assessmentOptionLabel, stripAssessmentIdSuffix } from "@/lib/livewell/assessmentDisplay";
import {
  aiPreviewHref,
  createPreview,
  downloadPreview,
  fetchPreviewContext,
  getPreview,
  listPreviews,
  progressText,
  reviewPreview,
  type CatalogPick,
  type PreviewContext,
  type PreviewJob,
} from "@/lib/aiPreview";
import "./ai-preview.css";

const ROOMS = ["bathroom", "bedroom", "kitchen", "living", "hallway", "entry", "other"];
const STATUS_WORD: Record<string, string> = {
  queued: "Waiting",
  running: "Making",
  needs_review: "Ready for review",
  completed: "Approved",
  failed: "Failed",
  awaiting_provider: "AI not connected",
};

function roomWord(room: string) {
  return (room || "room").replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

function Thumb({ url, alt }: { url: string; alt: string }) {
  const src = useAuthedImage(url);
  // eslint-disable-next-line @next/next/no-img-element
  return src ? <img src={src} alt={alt} /> : <span className="ap-thumb-wait" aria-label={`Loading ${alt}`} />;
}

export type AiRoomPreviewProps = {
  assessment?: string | null;
  elder?: number | null;
  photo?: number | null;
  products?: string[];
  job?: string | null;
  /** "room-checks" when opened from that tab, so Back returns there. */
  from?: string | null;
};

/** Ops page: pick photo → products → package → Generate; watch progress; review with a slider. */
export function AiRoomPreview(props: AiRoomPreviewProps) {
  const editor = can("edit");
  const [ctx, setCtx] = useState<PreviewContext | null>(null);
  const [assessment, setAssessment] = useState<string | null>(props.assessment ?? null);
  const [photoId, setPhotoId] = useState<number | null>(props.photo ?? null);
  const [room, setRoom] = useState("bathroom");
  const [codes, setCodes] = useState<string[]>(props.products ?? []);
  const [tier, setTier] = useState("comfort");
  const [search, setSearch] = useState("");
  const [jobs, setJobs] = useState<PreviewJob[]>([]);
  const [current, setCurrent] = useState<PreviewJob | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploadRoom, setUploadRoom] = useState("bathroom");
  const fileRef = useRef<HTMLInputElement>(null);
  const preselected = useRef(Boolean(props.products?.length));

  const load = useCallback(async () => {
    setError("");
    try {
      const c = await fetchPreviewContext({ assessment, elder: props.elder });
      setCtx(c);
      if (c.assessment_id && c.assessment_id !== assessment) setAssessment(c.assessment_id);
      const list = await listPreviews({ assessment: c.assessment_id || assessment });
      setJobs(list);
      return c;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load the preview");
      return null;
    }
  }, [assessment, props.elder]);

  useEffect(() => {
    void load();
  }, [load]);

  // Photo + room + products preselection once the context arrives.
  useEffect(() => {
    if (!ctx) return;
    const photo = ctx.photos.find((p) => p.document_id === photoId) ?? (photoId ? null : ctx.photos[0]);
    if (photo) {
      if (photo.document_id !== photoId) setPhotoId(photo.document_id);
      const r = photo.room_type || "bathroom";
      setRoom(r);
      if (!preselected.current) setCodes(ctx.recommended[r] ?? []);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctx]);

  useEffect(() => {
    if (props.job) getPreview(props.job).then(setCurrent).catch(() => undefined);
  }, [props.job]);

  // Poll the open job while it renders; the user can leave and come back (job list).
  useEffect(() => {
    if (!current?.progress.running) return;
    const t = window.setInterval(() => {
      getPreview(current.ai_job_id)
        .then((j) => {
          setCurrent(j);
          if (!j.progress.running) setJobs((list) => list.map((x) => (x.ai_job_id === j.ai_job_id ? j : x)));
        })
        .catch(() => undefined);
    }, 1500);
    return () => window.clearInterval(t);
  }, [current?.ai_job_id, current?.progress.running]);

  const byCode = useMemo(() => {
    const m = new Map<string, CatalogPick>();
    for (const p of ctx?.catalog ?? []) m.set(p.product_code, p);
    return m;
  }, [ctx]);
  const picked = codes.map((c) => byCode.get(c)).filter((p): p is CatalogPick => Boolean(p));
  const matches = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return [];
    return (ctx?.catalog ?? [])
      .filter((p) => !codes.includes(p.product_code))
      .filter((p) => `${p.name} ${p.product_code} ${p.category}`.toLowerCase().includes(q))
      .slice(0, 8);
  }, [ctx, search, codes]);
  const total = picked.reduce((s, p) => s + (p.priced ? p.price_with_gst_paise : 0), 0);

  function pickPhoto(id: number) {
    setPhotoId(id);
    const p = ctx?.photos.find((x) => x.document_id === id);
    if (p) {
      const r = p.room_type || room;
      setRoom(r);
      setCodes(ctx?.recommended[r] ?? []);
      preselected.current = false;
    }
  }

  async function upload(file: File) {
    if (!ctx?.assessment_id) return;
    setBusy(true);
    setError("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("assessment_id", ctx.assessment_id);
      fd.append("room_type", uploadRoom);
      if (ctx.client?.elder_id) fd.append("elder_id", String(ctx.client.elder_id));
      if (ctx.client?.prospect_id) fd.append("prospect_id", String(ctx.client.prospect_id));
      const doc = await postFormData<{ id: number }>("/api/v1/home-safety/photos", fd);
      const c = await load();
      if (c) {
        setPhotoId(doc.id);
        setRoom(uploadRoom);
        setCodes(c.recommended[uploadRoom] ?? []);
      }
      setNote("Photo added.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function generate(force = false) {
    if (!ctx?.assessment_id || !photoId) return;
    setBusy(true);
    setError("");
    setNote("");
    try {
      const j = await createPreview({
        assessment_id: ctx.assessment_id,
        source_document_id: photoId,
        room_type: room,
        package_level: tier,
        product_codes: codes,
        force,
      });
      setCurrent(j);
      setJobs((list) => [j, ...list.filter((x) => x.ai_job_id !== j.ai_job_id)]);
      if (j.cache_hit) setNote("The same photo, products and package were done before — showing that result (no new cost).");
      window.history.replaceState(null, "", aiPreviewHref({ assessment: ctx.assessment_id, job: j.ai_job_id }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the preview");
    } finally {
      setBusy(false);
    }
  }

  async function review(action: "approve" | "reject" | "regenerate") {
    if (!current) return;
    setBusy(true);
    setError("");
    setNote("");
    try {
      const j = await reviewPreview(current.ai_job_id, action);
      setCurrent(j);
      setJobs((list) => [j, ...list.filter((x) => x.ai_job_id !== j.ai_job_id && x.ai_job_id !== current.ai_job_id)]);
      if (action === "approve") setNote("Approved. The family sees it on their Safety page.");
      if (action === "reject") setNote("Rejected. It stays hidden from the family.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  const firstName = ctx?.client?.first_name || "";
  const fromRoomChecks = props.from === "room-checks";
  const backHref = fromRoomChecks
    ? "/kushalaya/room-checks?tab=history"
    : ctx?.client?.elder_id
      ? `/kushalaya/customers/${ctx.client.elder_id}?tab=health`
      : "/kushalaya/assessments";

  return (
    <div className="ap">
      <BackLink href={backHref} label={fromRoomChecks ? "Back to Room checks" : firstName ? `Back to ${firstName}` : "Back"} />
      <header className="ap-head">
        <h1>See it in their home</h1>
        <p className="muted">
          AI preview{firstName ? ` for ${firstName}` : ""}: the room photo with the suggested safety products added. Staff check every
          image before the family sees it.
        </p>
      </header>

      {error ? (
        <p className="ap-msg ap-msg-err" role="alert">
          {error}
        </p>
      ) : null}
      {note ? (
        <p className="ap-msg" role="status">
          {note}
        </p>
      ) : null}

      {!ctx ? (
        <p className="muted">Loading…</p>
      ) : !ctx.assessment_id ? (
        <p className="card">No assessment yet for this client. Finish an assessment with room photos first.</p>
      ) : (
        <div className="ap-grid">
          <section className="card ap-setup" aria-label="Set up the preview">
            {ctx.assessments.length > 1 ? (
              <label className="ap-field">
                <span>Assessment</span>
                <select value={ctx.assessment_id} onChange={(e) => setAssessment(e.target.value)}>
                  {ctx.assessments.map((a) => (
                    <option key={a.assessment_id} value={a.assessment_id}>
                      {assessmentOptionLabel(a)}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}

            <h2 className="ap-step">1. Room photo</h2>
            {ctx.photos.length === 0 ? <p className="muted">No room photos on this assessment yet.</p> : null}
            <ul className="ap-photos">
              {ctx.photos.map((p) => (
                <li key={p.document_id}>
                  <button
                    type="button"
                    className={`ap-photo${p.document_id === photoId ? " is-on" : ""}`}
                    aria-pressed={p.document_id === photoId}
                    onClick={() => pickPhoto(p.document_id)}
                  >
                    <Thumb url={p.image_url} alt={p.caption || roomWord(p.room_type)} />
                    <span>{(p.caption && stripAssessmentIdSuffix(p.caption)) || roomWord(p.room_type)}</span>
                  </button>
                </li>
              ))}
            </ul>
            {editor ? (
              <div className="ap-upload">
                <select aria-label="Room of the new photo" value={uploadRoom} onChange={(e) => setUploadRoom(e.target.value)}>
                  {ROOMS.map((r) => (
                    <option key={r} value={r}>
                      {roomWord(r)}
                    </option>
                  ))}
                </select>
                <label className="secondary ap-upload-btn">
                  Upload a new photo
                  <input
                    ref={fileRef}
                    type="file"
                    accept="image/*"
                    capture="environment"
                    hidden
                    disabled={busy}
                    onChange={(e) => e.target.files?.[0] && void upload(e.target.files[0])}
                  />
                </label>
              </div>
            ) : null}

            <h2 className="ap-step">2. Products to show</h2>
            <label className="ap-field ap-inline">
              <span>Room</span>
              <select
                value={room}
                onChange={(e) => {
                  setRoom(e.target.value);
                  setCodes(ctx.recommended[e.target.value] ?? []);
                }}
                disabled={!editor}
              >
                {ROOMS.map((r) => (
                  <option key={r} value={r}>
                    {roomWord(r)}
                  </option>
                ))}
              </select>
            </label>
            {picked.length === 0 ? (
              <p className="muted">Nothing picked. The assessment found no fix for this room — add products below.</p>
            ) : (
              <ol className="ap-picked">
                {picked.map((p) => (
                  <li key={p.product_code}>
                    <span className="ap-picked-name">
                      {p.name} <small className="muted">{p.product_code}</small>
                    </span>
                    <span className="ap-price">{p.priced ? inr(p.price_with_gst_paise) : "Price on request"}</span>
                    {editor ? (
                      <button
                        type="button"
                        className="ap-x"
                        aria-label={`Remove ${p.name}`}
                        onClick={() => setCodes((c) => c.filter((x) => x !== p.product_code))}
                      >
                        ×
                      </button>
                    ) : null}
                  </li>
                ))}
              </ol>
            )}
            {picked.length ? (
              <p className="ap-total">
                Total incl. 18% GST <strong>{inr(total)}</strong>
                {unpricedNote(picked.filter((p) => !p.priced).length)}
              </p>
            ) : null}
            {editor ? (
              <div className="ap-search">
                <input
                  type="search"
                  placeholder="Add a product: search grab bar, mat, light…"
                  aria-label="Search the product catalog"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                {matches.length ? (
                  <ul className="ap-matches">
                    {matches.map((p) => (
                      <li key={p.product_code}>
                        <button
                          type="button"
                          onClick={() => {
                            setCodes((c) => (c.length >= 12 ? c : [...c, p.product_code]));
                            setSearch("");
                          }}
                        >
                          <span>
                            {p.name} <small className="muted">{p.product_code}</small>
                          </span>
                          <span className="ap-price">{p.priced ? inr(p.price_with_gst_paise) : ""}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : null}

            <h2 className="ap-step">3. Package</h2>
            <div className="ap-tabs" role="tablist" aria-label="Package">
              {ctx.tiers.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={tier === t.id}
                  className={tier === t.id ? "is-on" : ""}
                  onClick={() => setTier(t.id)}
                >
                  {t.name}
                </button>
              ))}
            </div>

            {editor ? (
              <button
                type="button"
                className="primary ap-go"
                disabled={busy || !photoId || codes.length === 0}
                onClick={() => void generate()}
              >
                {busy ? "Starting…" : "Generate preview"}
              </button>
            ) : (
              <p className="muted">View only: ask a manager to make previews.</p>
            )}
            <p className="muted ap-caps">
              Today {ctx.caps.today} of {ctx.caps.daily_cap} images · up to {ctx.caps.max_photos} photos × 3 packages per assessment ·{" "}
              {ctx.caps.max_regenerations_per_tier} re-runs per package
              {ctx.provider === "local_stub" ? " · offline stub (no AI connected)" : ""}
            </p>
          </section>

          <section className="ap-result" aria-live="polite">
            {current ? (
              <JobPanel job={current} editor={editor} busy={busy} onReview={review} />
            ) : (
              <div className="card ap-empty">
                <p>Pick a photo and products, then Generate. It takes about 15 seconds; you can leave this page and come back.</p>
              </div>
            )}

            <div className="card ap-list">
              <h2>Previews for this assessment</h2>
              {jobs.length === 0 ? (
                <p className="muted">None yet.</p>
              ) : (
                <ul>
                  {jobs.map((j) => (
                    <li key={j.ai_job_id}>
                      <button
                        type="button"
                        className={current?.ai_job_id === j.ai_job_id ? "is-on" : ""}
                        onClick={() => setCurrent(j)}
                      >
                        <span>
                          {roomWord(j.room_type)} · {j.package_level} · {j.items.length} item{j.items.length === 1 ? "" : "s"}
                        </span>
                        <span className={`ap-chip ap-chip-${j.review_status === "approved" ? "ok" : j.status}`}>
                          {j.review_status === "rejected" ? "Rejected" : STATUS_WORD[j.status] || j.status}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function JobPanel({
  job,
  editor,
  busy,
  onReview,
}: {
  job: PreviewJob;
  editor: boolean;
  busy: boolean;
  onReview: (a: "approve" | "reject" | "regenerate") => void;
}) {
  const before = useAuthedImage(job.before_url);
  const after = useAuthedImage(job.after_url);
  const p = job.progress;
  const est = Math.max(1, p.estimate_seconds);
  // Time-based fill while generating, so the bar keeps moving between stages.
  const pct = p.running ? Math.min(95, Math.max(p.percent, Math.round(((p.elapsed_seconds ?? 0) / est) * 85))) : p.percent;
  const ready = job.status === "needs_review" || job.status === "completed";
  const missing = job.missing ?? [];
  const changes = job.changes ?? [];
  const blocked = missing.length > 0 || changes.length > 0;

  return (
    <div className="card ap-job">
      <div className="ap-job-head">
        <h2>
          {roomWord(job.room_type)} · {job.package_level.replace(/^\w/, (c) => c.toUpperCase())}
        </h2>
        <span className="muted">{job.ai_job_id}</span>
      </div>

      {p.running || job.status === "failed" || job.status === "awaiting_provider" ? (
        <div className="ap-progress">
          <div
            className="ap-bar"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={pct}
            aria-label="Preview progress"
          >
            <span style={{ width: `${pct}%` }} className={job.status === "failed" ? "is-err" : ""} />
          </div>
          <p className={job.status === "failed" ? "ap-msg-err" : "muted"}>
            {job.status === "failed" || job.status === "awaiting_provider" ? job.error_message || "Failed" : progressText(p)}
          </p>
        </div>
      ) : null}

      {ready && before && after ? (
        <BeforeAfterSlider
          beforeSrc={before}
          afterSrc={after}
          beforeAlt={`${roomWord(job.room_type)} now`}
          afterAlt={`${roomWord(job.room_type)} with the suggested products (illustration)`}
          markers={job.markers}
        />
      ) : ready ? (
        <p className="muted">Loading images…</p>
      ) : null}

      {ready ? (
        <>
          <ul className="ap-checks">
            {job.similarity_score != null ? (
              <li className={job.room_changed ? "is-bad" : "is-ok"}>
                {job.room_changed ? "✗" : "✓"} Room kept the same ({Math.round(job.similarity_score * 100)}% match)
              </li>
            ) : null}
            {job.items.map((i) =>
              i.shown == null ? null : (
                <li key={i.n} className={i.shown ? "is-ok" : "is-bad"}>
                  {i.shown ? "✓" : "✗"} {i.name} {i.shown ? "shown" : "not shown — regenerate or edit the products"}
                </li>
              ),
            )}
            {job.qa_status && job.qa_status !== "checked" ? (
              <li className="is-warn">Product check unavailable — look carefully before approving.</li>
            ) : null}
            {changes.map((c) => (
              <li key={c} className="is-bad">
                ✗ Room changed: {c}
              </li>
            ))}
            {job.render_attempts > 1 ? <li className="muted">Retried automatically once.</li> : null}
            {job.is_stub ? <li className="is-warn">Offline stub image: families never see stub images.</li> : null}
          </ul>

          <ol className="ap-items">
            {job.items.map((i) => (
              <li key={i.n}>
                <span className="ap-n">{i.n}</span>
                <span className="ap-picked-name">{i.name}</span>
                <span className="ap-price">{i.priced ? inr(i.price_with_gst_paise) : "Price on request"}</span>
              </li>
            ))}
          </ol>
          <p className="ap-total">
            Total incl. 18% GST <strong>{inr(job.total_paise)}</strong>
            <small className="muted"> · GST {inr(job.gst_paise)}</small>
            {unpricedNote(job.items.filter((i) => !i.priced).length)}
          </p>

          <div className="ap-actions">
            {editor && job.status === "needs_review" ? (
              <>
                <button
                  type="button"
                  className="primary"
                  disabled={busy || blocked}
                  title={
                    missing.length
                      ? "Some products are not shown in the image"
                      : changes.length
                        ? "The picture changed the room — regenerate first"
                        : undefined
                  }
                  onClick={() => onReview("approve")}
                >
                  Approve for family
                </button>
                <button type="button" className="secondary" disabled={busy} onClick={() => onReview("reject")}>
                  Reject
                </button>
              </>
            ) : null}
            {editor && job.review_status !== "approved" ? (
              <button
                type="button"
                className="secondary"
                disabled={busy || job.regenerations_left === 0}
                onClick={() => onReview("regenerate")}
              >
                Regenerate{job.regenerations_left != null ? ` (${job.regenerations_left} left)` : ""}
              </button>
            ) : null}
            <button type="button" className="secondary" onClick={() => void downloadPreview(job.ai_job_id, "image")}>
              Download image
            </button>
            <button type="button" className="secondary" onClick={() => void downloadPreview(job.ai_job_id, "pdf")}>
              PDF
            </button>
          </div>
          {job.review_status === "approved" ? <p className="ap-msg">Approved — visible to the family.</p> : null}
        </>
      ) : null}
    </div>
  );
}

/** The total leaves out "Price on request" items: say so. */
function unpricedNote(n: number) {
  return n ? (
    <small className="ap-total-note">
      {" "}+ {n} item{n === 1 ? "" : "s"} price on request (not in the total)
    </small>
  ) : null;
}
