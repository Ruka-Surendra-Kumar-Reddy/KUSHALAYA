"use client";

import { pinFarFromAddress } from "@/lib/geo-distance";
import { safetyGradeFromScore } from "@/lib/livewell/assessment";
import { ClientHistory } from "@/components/ops/ClientHistory";
import "@/components/ops/clients.css";
import { ClientOrders } from "@/components/ops/ClientOrders";
import { PlanPaymentsCard } from "@/components/ops/PlanPaymentsCard";
import { CustomerOverview } from "@/components/ops/CustomerOverview";
import { ClientManagerPicker } from "@/components/ops/ClientManagerPicker";
import { CareTeamCard } from "@/components/ops/CareTeamCard";
import { ClientDocuments } from "@/components/ops/ClientDocuments";
import { ContractsPanel } from "@/components/contracts/ContractsPanel";
import { ClientAssessments } from "@/components/ops/ClientAssessments";
import { ClientAiPreviews } from "@/components/ops/ClientAiPreviews";
import { aiPreviewHref } from "@/lib/aiPreview";
import { ClientRoomCheck } from "@/components/ops/ClientRoomCheck";
import { HazardCountChip } from "@/components/livewell/AiHazardCheck";
import { ClientCareSheet } from "@/components/ops/ClientCareSheet";
import { ClientCarePlan, ClientHandovers, ClientRiskRegister } from "@/components/ops/ClientCarePlan";
import { ClientEditForm } from "@/components/ops/ClientEditForm";
import { FamilyLoginsCard } from "@/components/ops/FamilyLoginsCard";
import { ClientQuestionsCard, FamilyContactsCard } from "@/components/ops/ClientFamilyK2";
import { KnowThemCard } from "@/components/ops/KnowThemCard";
import { ClientIncidents } from "@/components/ops/ClientIncidents";
import { ClientDevicesCard } from "@/components/ops/ClientDevicesCard";
import { VisitChecklistCard } from "@/components/ops/VisitChecklistCard";
import { ScheduleJobs, type SchedulePrefill } from "@/components/ops/ScheduleJobs";
import { ClientAlertsPanel } from "@/components/ops/ClientAlertsPanel";
import { MessageThread } from "@/components/ops/MessageThread";
import "@/components/ops/messages.css";
import { formatIST } from "@/lib/ist";
import { listJobs, type CareJob } from "@/lib/jobs";
import { StartAssessmentButton } from "@/components/ops/StartAssessmentButton";
import { RaiseEmergencyModal } from "@/components/ops/RaiseEmergency";
import { MoreMenu } from "@/components/ops/MoreMenu";
import { BackLink } from "@/components/ops/PageActions";
import { Directions } from "@/components/Directions";
import { api } from "@/lib/api";
import { can, canOpen } from "@/lib/roles";
import { downloadInvoicePdf, inr, listInvoices, type Invoice } from "@/lib/business";
import { KushLifeTrend } from "@/components/KushLifeTrend";
import { KushLifeBaselineEditor, KushLifeWeeklyPanel } from "@/components/ops/KushLifeWeeklyPanel";
import { KushLifeQualityPanel } from "@/components/ops/KushLifeQualityPanel";
import { JourneySteps, type Journey } from "@/components/JourneySteps";
import { ScoreWhyButton } from "@/components/ScoreWhy";
import type { KushLifeView } from "@/lib/kushlife";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { VisitMap, type MapPin } from "@/components/livewell/VisitMap";
import { StaffVisitPhoto } from "@/components/ops/StaffVisitPhoto";
import {
  addVisitStaffFeedback,
  attachVisitPhotos,
  captureLocation,
  fetchClientProfile,
  formatPaise,
  mapsLink,
  saveHomeLocation,
  uploadVisitPhoto,
  type ClientProfile,
  type HomeLocation,
} from "@/lib/livewell/clientProfileApi";
import type { SafeHomeVisit } from "@/lib/livewell/visit-types";
import { publicSafetyScoreName } from "@/lib/public-brand";
import { plural } from "@/lib/run-sheet";

const TABS = [
  "Overview",
  "Details",
  "Visits & requests",
  "SOS & alerts",
  "Care",
  "Health",
  "Plan & payments",
  "Incidents",
  "Documents",
  "Messages",
] as const;
type Tab = (typeof TABS)[number];

/** ?tab= values. Old names (sheet, care-plan, timeline, assessments, orders, alerts…) land on the new tab. */
const TAB_KEYS: Record<string, Tab> = {
  overview: "Overview",
  details: "Details",
  profile: "Details",
  visits: "Visits & requests",
  requests: "Visits & requests",
  schedule: "Visits & requests",
  sos: "SOS & alerts",
  alerts: "SOS & alerts",
  devices: "SOS & alerts",
  care: "Care",
  sheet: "Care",
  "care-plan": "Care",
  risks: "Care",
  handovers: "Care",
  checklist: "Care",
  health: "Health",
  kushlife: "Health",
  vitals: "Health",
  assessments: "Health",
  timeline: "Health",
  history: "Health",
  money: "Plan & payments",
  orders: "Plan & payments",
  wallet: "Plan & payments",
  invoices: "Plan & payments",
  plan: "Plan & payments",
  payments: "Plan & payments",
  incidents: "Incidents",
  documents: "Documents",
  messages: "Messages",
};
const TAB_KEY: Record<Tab, string> = {
  Overview: "overview",
  Details: "details",
  "Visits & requests": "visits",
  "SOS & alerts": "sos",
  Care: "care",
  Health: "health",
  "Plan & payments": "plan",
  Incidents: "incidents",
  Documents: "documents",
  Messages: "messages",
};

const CLOSED_REQUEST = new Set(["done", "completed", "cancelled", "declined", "closed", "resolved"]);
const STATUS_WORD: Record<string, string> = {
  ACTIVE: "Active",
  INACTIVE: "Inactive",
  PENDING: "Pending",
  ON_HOLD: "On hold",
  open: "Open",
  acknowledged: "Acknowledged",
  escalated: "Escalated",
  resolved: "Closed",
  closed: "Closed",
  requested: "Requested",
  scheduled: "Scheduled",
  completed: "Completed",
  cancelled: "Cancelled",
  declined: "Declined",
  done: "Completed",
  paid: "Paid",
  pending: "Pending",
  failed: "Failed",
  refunded: "Refunded",
};
const ALERT_KIND: Record<string, string> = {
  sos: "SOS button pressed",
  fall: "Possible fall",
  fall_detected: "Possible fall",
  no_motion: "No movement noticed",
  inactivity: "No movement noticed",
  door_open: "Door left open",
  low_battery: "Band battery low",
  offline: "Band offline",
  device_offline: "Band offline",
  vitals: "Vital signs out of range",
  kushlife: "KushLife concern",
};

type ClientRequest = ClientProfile["service_requests"][number] & {
  service_type?: string;
  service_label?: string;
  notes?: string;
  preferred_at?: string;
};

function requestLabel(r: ClientRequest): string {
  return r.service_label || r.title || r.service_name || word(r.service_type || "request");
}

/** Same kind rule as the Dashboard's Schedule link. */
function requestKind(r: ClientRequest): SchedulePrefill["kind"] {
  const t = String(r.service_type || "");
  return /assess/.test(t) ? "assessment" : t === "product" ? "install" : "visit";
}

function ageFrom(dob?: string | null): number | null {
  if (!dob) return null;
  const d = new Date(dob);
  if (Number.isNaN(d.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - d.getFullYear();
  if (now.getMonth() < d.getMonth() || (now.getMonth() === d.getMonth() && now.getDate() < d.getDate())) age -= 1;
  return age >= 0 && age < 130 ? age : null;
}

function word(value?: string | null): string {
  if (!value) return "Not recorded";
  return STATUS_WORD[value] ?? STATUS_WORD[value.toLowerCase()] ?? value.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

function day(value?: string | null): string {
  return value ? formatIST(value, { dateOnly: true }) : "Not recorded";
}

function dayTime(value?: string | null): string {
  return value ? formatIST(value) : "Not recorded";
}

function Stars({ value }: { value: number }) {
  return (
    <span className="cp-stars" aria-label={`${value} out of 5`}>
      {"★".repeat(value)}
      <span className="cp-stars-off">{"★".repeat(5 - value)}</span>
    </span>
  );
}

function Field({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="cp-field">
      <span>{label}</span>
      <strong>{value?.trim() || "Not recorded"}</strong>
    </div>
  );
}

/** Photos need the auth header, so they load as blobs. */
function StaffPhoto({ id }: { id: number }) {
  // Thumbnail + the care team's "Hide from family" switch.
  return <StaffVisitPhoto id={id} />;
}

/** Set or move the client's home pin: current GPS position, or a click on the map. */
function HomeLocationCard({
  elderId,
  home,
  addressPoint,
  onSaved,
}: {
  elderId: number;
  home: HomeLocation | null;
  addressPoint?: { lat: number; lng: number } | null;
  onSaved: () => void;
}) {
  const [draft, setDraft] = useState<HomeLocation | null>(home);
  const canEdit = can("edit");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const dirty = JSON.stringify(draft) !== JSON.stringify(home);

  async function useHere() {
    setNote("");
    try {
      const here = await captureLocation();
      setDraft({ lat: here.lat, lng: here.lng, radius_m: draft?.radius_m ?? 100 });
    } catch (e) {
      setNote(e instanceof Error ? e.message : "Could not get location");
    }
  }

  async function save() {
    if (!draft) return;
    setBusy(true);
    setNote("");
    try {
      await saveHomeLocation(elderId, draft);
      setNote("Home location saved. New visits are checked against it.");
      onSaved();
    } catch (e) {
      setNote(e instanceof Error ? e.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card cp-home">
      <h2>Home location</h2>
      <p className="muted">
        {!canEdit
          ? draft
            ? `Visits logged within ${draft.radius_m} m count as at home.`
            : "Not set yet."
          : draft
            ? "Click the map to move the pin. Visits logged inside the circle count as at home."
            : "Not set yet. Stand at the client's home and use your current location, or click the map."}
      </p>
      {(() => {
        const far = pinFarFromAddress(draft, addressPoint);
        return far ? (
          <p className="cp-home-warn" role="status">
            The pin is {(far / 1000).toFixed(1)} km from the saved address. Check-ins are measured from the pin, so
            move it to the client&apos;s home before relying on &quot;at home&quot;.
          </p>
        ) : null;
      })()}
      <VisitMap
        pins={[]}
        home={draft}
        height={260}
        onPick={canEdit ? (lat, lng) => setDraft({ lat, lng, radius_m: draft?.radius_m ?? 100 }) : undefined}
      />
      {canEdit ? (
      <div className="cp-home-actions">
        <button type="button" className="secondary" onClick={() => void useHere()}>
          Use my current location
        </button>
        <label>
          Radius{" "}
          <select
            value={draft?.radius_m ?? 100}
            disabled={!draft}
            onChange={(e) => draft && setDraft({ ...draft, radius_m: Number(e.target.value) })}
          >
            {[50, 100, 150, 250, 500].map((r) => (
              <option key={r} value={r}>
                {r} m
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="primary" disabled={!draft || !dirty || busy} onClick={() => void save()}>
          {busy ? "Saving…" : "Save home location"}
        </button>
      </div>
      ) : null}
      {note ? <p className="muted">{note}</p> : null}
    </section>
  );
}

function VisitCard({
  elderId,
  visit,
  onChanged,
  onShowOnMap,
}: {
  elderId: number;
  visit: SafeHomeVisit;
  onChanged: () => void;
  onShowOnMap: (visitId: string) => void;
}) {
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const loc = visit.location;
  const completed = visit.status === "completed";

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await action();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  async function addPhotos(files: FileList | null) {
    if (!files?.length) return;
    await run(async () => {
      const ids: number[] = [];
      for (const file of Array.from(files).slice(0, 10)) ids.push(await uploadVisitPhoto(elderId, file));
      await attachVisitPhotos(elderId, visit.id, ids);
    });
  }

  return (
    <li className="card cp-visit">
      <div className="cp-visit-head">
        <div>
          <strong>{visit.visit_type}</strong>
          <span className="muted"> · {dayTime(visit.visited_at)}</span>
          {visit.staff_name ? <span className="muted"> · {visit.staff_name}</span> : null}
        </div>
        <span className={`cp-pill cp-pill-${visit.status}`}>{word(visit.status)}</span>
      </div>
      {visit.summary ? <p>{visit.summary}</p> : null}

      <div className="cp-visit-grid">
        <div>
          <span className="cp-label">Location</span>
          {loc ? (
            <p>
              {loc.at_home === true ? <span className="cp-ok">At the client&apos;s home</span> : null}
              {loc.at_home === false ? (
                <span className="cp-warn">{loc.distance_from_home_m} m from home</span>
              ) : null}
              {loc.at_home == null ? <span>Location recorded</span> : null}
              {loc.accuracy_m != null ? <span className="muted"> (±{loc.accuracy_m} m)</span> : null}
              {" · "}
              <button type="button" className="cp-linkbtn" onClick={() => onShowOnMap(visit.id)}>
                Show on map
              </button>
              {" · "}
              <a href={mapsLink(loc.lat, loc.lng)} target="_blank" rel="noopener noreferrer">
                Google Maps
              </a>
            </p>
          ) : (
            <p className="muted">{completed ? "Not recorded" : "Recorded when the visit is completed"}</p>
          )}
        </div>
        <div>
          <span className="cp-label">Family feedback</span>
          {visit.experience_rating ? (
            <p>
              <Stars value={visit.experience_rating} />
              {visit.experience_comment ? <span> “{visit.experience_comment}”</span> : null}
            </p>
          ) : (
            <p className="muted">{completed ? "Waiting for the family to rate" : "After the visit"}</p>
          )}
        </div>
      </div>

      <div>
        <span className="cp-label">Photos</span>
        <div className="cp-photos">
          {visit.photo_ids.map((id) => (
            <StaffPhoto key={id} id={id} />
          ))}
          <label className={`secondary cp-add-photo${busy ? " is-disabled" : ""}`}>
            + Add
            <input
              type="file"
              accept="image/*"
              multiple
              hidden
              disabled={busy}
              onChange={(e) => {
                void addPhotos(e.target.files);
                e.target.value = "";
              }}
            />
          </label>
        </div>
      </div>

      <div>
        <span className="cp-label">Care manager feedback (staff only)</span>
        {visit.staff_feedback ? (
          <p>
            <Stars value={visit.staff_feedback.rating} />
            {visit.staff_feedback.comment ? <span> “{visit.staff_feedback.comment}”</span> : null}
            <span className="muted"> — {visit.staff_feedback.by_name}, {day(visit.staff_feedback.at)}</span>
          </p>
        ) : completed ? (
          <div className="cp-feedback-form">
            <select value={rating} onChange={(e) => setRating(Number(e.target.value))} aria-label="Rating">
              {[5, 4, 3, 2, 1].map((n) => (
                <option key={n} value={n}>
                  {n} star{n === 1 ? "" : "s"}
                </option>
              ))}
            </select>
            <input
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="How did the visit and the household go?"
              maxLength={1000}
            />
            <button
              type="button"
              className="primary"
              disabled={busy}
              onClick={() => void run(() => addVisitStaffFeedback(elderId, visit.id, { rating, comment }))}
            >
              Save feedback
            </button>
          </div>
        ) : (
          <p className="muted">Available once the visit is completed.</p>
        )}
      </div>
      {error ? <p className="error-text">{error}</p> : null}
    </li>
  );
}

export default function ClientProfilePage() {
  const params = useParams<{ id: string }>();
  const elderId = Number(params.id);
  // View-only staff see the whole record; every add/edit/schedule control is hidden.
  const edit = can("edit");
  const [data, setData] = useState<ClientProfile | null>(null);
  const [error, setError] = useState("");
  const [tab, setTabState] = useState<Tab>("Overview");
  const [focusId, setFocusId] = useState<string | null>(null);
  const [showMap, setShowMap] = useState(false);
  const [jobs, setJobs] = useState<CareJob[]>([]);
  const [prefill, setPrefill] = useState<SchedulePrefill | null>(null);

  // ?tab=orders, ?tab=assessments… — read once on load, kept in the URL as tabs change.
  useEffect(() => {
    const key = new URLSearchParams(window.location.search).get("tab");
    if (key && TAB_KEYS[key.toLowerCase()]) setTabState(TAB_KEYS[key.toLowerCase()]);
  }, []);

  const setTab = useCallback((t: Tab) => {
    setTabState(t);
    const url = new URL(window.location.href);
    if (t === "Overview") url.searchParams.delete("tab");
    else url.searchParams.set("tab", TAB_KEY[t]);
    window.history.replaceState(window.history.state, "", url.toString());
  }, []);

  // Only once the client has loaded, so a wrong id makes one 404 call, not several.
  const loaded = data !== null;
  useEffect(() => {
    if (loaded && Number.isFinite(elderId)) listJobs({ elder_id: elderId }).then(setJobs).catch(() => undefined);
  }, [elderId, loaded]);

  const pins = useMemo<MapPin[]>(
    () =>
      (data?.visits || [])
        .filter((v) => v.location)
        .map((v) => {
          const loc = v.location!;
          return {
            id: v.id,
            lat: loc.lat,
            lng: loc.lng,
            tone: loc.at_home === true ? "ok" : loc.at_home === false ? "warn" : "neutral",
            lines: [
              v.visit_type,
              dayTime(v.visited_at) + (v.staff_name ? ` · ${v.staff_name}` : ""),
              loc.at_home === true
                ? "At the client's home"
                : loc.at_home === false
                  ? `${loc.distance_from_home_m} m from home`
                  : "No home location to compare with",
              ...(v.experience_rating ? [`Family rating: ${v.experience_rating}/5`] : []),
              ...(v.summary ? [v.summary.slice(0, 120)] : []),
            ],
          } satisfies MapPin;
        }),
    [data],
  );

  const [toast, setToast] = useState("");
  const [emergency, setEmergency] = useState(false);
  const hasData = useRef(false);
  const load = useCallback(() => {
    fetchClientProfile(elderId)
      .then((d) => {
        hasData.current = true;
        setData(d);
        setToast("");
      })
      .catch((e) => {
        const msg = e instanceof Error ? e.message : "Could not load client";
        // After a save, keep the page and say the refresh failed; only a first load shows the error page.
        if (hasData.current) setToast(`Saved, but the page could not refresh: ${msg}`);
        else setError(msg);
      });
  }, [elderId]);

  useEffect(() => {
    if (Number.isFinite(elderId)) load();
  }, [elderId, load]);

  if (error || !Number.isFinite(elderId)) {
    const missing = !Number.isFinite(elderId) || /not found|404/i.test(error);
    return (
      <div className="ks-frame">
        <p className="ks-back-row">
          <Link href="/kushalaya/customers">← All customers</Link>
        </p>
        <section className="card ks-empty-state">
          <h1>{missing ? "Client not found" : "Could not load this client"}</h1>
          <p className="muted">
            {missing
              ? "This client may have been removed, or the link is out of date."
              : error}
          </p>
          <Link className="ks-empty-action" href="/kushalaya/customers">
            ← All customers
          </Link>
        </section>
      </div>
    );
  }
  if (!data) return <p className="muted">Loading client…</p>;

  const p = data.person;
  const name = `${p.first_name} ${p.last_name}`.trim();
  const openAlerts = data.incidents.filter((i) => !["resolved", "closed"].includes(i.status)).length;
  const openRequestRows = (data.service_requests as ClientRequest[]).filter(
    (r) => !CLOSED_REQUEST.has(String(r.status || "requested")),
  );
  const openRequests = openRequestRows.length;
  const openSos = data.incidents.filter(
    (i) => i.severity === "critical" && !["resolved", "closed"].includes(i.status),
  ).length;
  const age = ageFrom(p.date_of_birth);
  const familyPhone = p.emergency_contact_phone?.trim() || "";
  const now = Date.now();
  const nextVisit = jobs
    .filter((j) => j.scheduled_at && !["completed", "cancelled", "missed"].includes(j.status) && new Date(j.scheduled_at).getTime() >= now)
    .sort((a, b) => new Date(a.scheduled_at!).getTime() - new Date(b.scheduled_at!).getTime())[0];
  const lastVisitAt = [
    ...jobs.filter((j) => j.status === "completed").map((j) => j.completed_at ?? j.scheduled_at),
    ...data.visits.filter((v) => v.status === "completed").map((v) => v.visited_at),
  ]
    .filter((d): d is string => !!d)
    .sort()
    .pop();
  const assessmentDue = !!(data.reassessment && !data.reassessment.booked_at && (data.reassessment.overdue || data.reassessment.needs_first));

  // Higher is safer: unless critical findings cap it, the band follows the score
  // (shared LWA_INDEPENDENCE_BANDS) so a stale "High Risk" never sits beside 91.
  const shownBand =
    data.score_band && data.safety_score?.total != null && !/critical finding/i.test(data.score_band)
      ? safetyGradeFromScore(data.safety_score.total).grade
      : data.score_band;
  // Same rule as the family SafetyScoreCard: when critical findings cap the band,
  // say what needs doing instead of a "High risk" label beside a high score.
  const urgentFixes = Number(/(\d+)\s+critical finding/i.exec(data.score_band || "")?.[1] || 0);
  return (
    <div className="cp">
      <p className="cp-back">
        <BackLink href="/kushalaya/customers" label="All customers" />
      </p>
      <header className="card cp-head">
        <div className="cp-title">
          <h1>
            {name}
            {age != null ? <span className="cp-age">, {age}</span> : null}
          </h1>
          <span className={`cp-pill ${p.status === "INACTIVE" ? "cp-pill-cancelled" : "cp-pill-completed"}`}>
            {p.status ? word(p.status) : "Active"}
          </span>
          <ClientManagerPicker key={data.manager_user_id ?? 0} elderId={p.id} managerId={data.manager_user_id} managerName={data.manager_name} />
          <HazardCountChip elderId={p.id} />
          {openSos ? (
            <button type="button" className="cp-flag is-sos" onClick={() => setTab("SOS & alerts")}>
              {openSos} SOS open
            </button>
          ) : null}
          {openRequests ? (
            <button type="button" className="cp-flag is-req" onClick={() => setTab("Visits & requests")}>
              {openRequests} request{openRequests === 1 ? "" : "s"}
            </button>
          ) : null}
        </div>
        {p.address || data.home_location ? (
          <div className="cp-addr">
            <span className={p.address ? "" : "muted"}>{p.address || "Home pin saved on the map"}</span>
            <Directions home={data.home_location} address={p.address} name={name} />
          </div>
        ) : null}
        <div className="cp-stats">
          <div>
            <span>{publicSafetyScoreName()}</span>
            <strong>
              {data.safety_score?.total == null
                ? "Not assessed yet"
                : `${data.safety_score.total}/100`}
            </strong>
            {urgentFixes ? (
              <small className="cp-bad">
                {urgentFixes} urgent fix{urgentFixes === 1 ? "" : "es"} needed
              </small>
            ) : shownBand ? (
              <small className={/critical|high risk/i.test(shownBand) ? "cp-bad" : "muted"}>{shownBand}</small>
            ) : null}
            {data.safety_score?.total != null ? (
              <small className="muted">
                {data.safety_score.assessed_at ? `${day(data.safety_score.assessed_at)} · ` : ""}
                <ScoreWhyButton url={`/api/v1/home-safety/clients/${p.id}/score-explain`} label="Why?" />
              </small>
            ) : null}
          </div>
          <div>
            <span>Next visit</span>
            <strong>{nextVisit ? day(nextVisit.scheduled_at) : "None booked"}</strong>
          </div>
          <div>
            <span>Next assessment</span>
            <strong className={assessmentDue ? "cp-bad" : ""}>{nextAssessment(data.reassessment)}</strong>
          </div>
          <div>
            <span>Last visit</span>
            <strong>{lastVisitAt ? day(lastVisitAt) : "No visits yet"}</strong>
            {lastVisitAt ? (
              <button type="button" className="cp-linkbtn" onClick={() => setTab("Health")}>
                View
              </button>
            ) : null}
          </div>
          <div>
            <span>Open items</span>
            <strong className={openAlerts + openRequests ? "cp-warn" : ""}>{openAlerts + openRequests}</strong>
            <small className="muted">
              {openAlerts} alert{openAlerts === 1 ? "" : "s"} · {openRequests} request{openRequests === 1 ? "" : "s"}
            </small>
          </div>
        </div>
        {/* One primary action; Call family stays visible, the rest sit under More. */}
        <div className="cp-actions">
          {!edit ? null : data.reassessment?.booked_job_id ? (
            <StartAssessmentButton
              job={{
                id: data.reassessment.booked_job_id,
                status: jobs.find((j) => j.id === data.reassessment!.booked_job_id)?.status,
                scheduled_at: data.reassessment.booked_at,
              }}
            />
          ) : (
            <Link className="cp-go" href={`/kushalaya/visits/log?elder=${p.id}`}>
              Log a visit
            </Link>
          )}
          {familyPhone ? (
            <a className="secondary cp-act-sm" href={`tel:${familyPhone.replace(/[^\d+]/g, "")}`}>
              Call family{p.emergency_contact_name ? ` (${p.emergency_contact_name})` : ""}
            </a>
          ) : null}
          {edit ? (
            // Emergencies must be one tap away, not inside "More".
            <button type="button" className="danger" onClick={() => setEmergency(true)}>
              SOS — raise emergency
            </button>
          ) : null}
          <MoreMenu>
            {!edit ? null : data.reassessment?.booked_job_id ? (
              <Link className="ks-more-item" role="menuitem" href={`/kushalaya/visits/log?elder=${p.id}`}>
                Log a visit
              </Link>
            ) : (
              <Link className="ks-more-item" role="menuitem" href={`/kushalaya/visits?schedule=1&elder=${p.id}&kind=assessment`}>
                Book assessment
              </Link>
            )}
            <Link className="ks-more-item" role="menuitem" href={aiPreviewHref({ elder: p.id })}>
              See it in their home (AI preview)
            </Link>
            <button type="button" className="ks-more-item" role="menuitem" onClick={() => setTab("Messages")}>
              Message family{data.messages.count ? ` (${data.messages.count})` : ""}
            </button>
            {edit ? (
              <button type="button" className="ks-more-item is-danger" role="menuitem" onClick={() => setEmergency(true)}>
                Raise emergency
              </button>
            ) : null}
          </MoreMenu>
        </div>
      </header>
      {emergency ? (
        <RaiseEmergencyModal
          elderId={p.id}
          elderName={name}
          onClose={() => setEmergency(false)}
          onRaised={(row) => {
            setEmergency(false);
            window.location.href = `/kushalaya/alerts?open=${row.id}`;
          }}
        />
      ) : null}

      {toast ? (
        <p className="cp-toast" role="status">
          {toast}{" "}
          <button type="button" className="cp-linkbtn" onClick={load}>
            Try again
          </button>
        </p>
      ) : null}

      <nav className="cp-tabs" aria-label="Client sections" role="tablist">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={t === tab}
            className={t === tab ? "is-active" : ""}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </nav>

      {tab === "Overview" ? <CustomerOverview data={data} jobs={jobs} onTab={setTab} /> : null}

      {tab === "Details" ? (
        <>
          <CareTeamCard elderId={p.id} onChanged={load} />
          <div className="cp-cols">
            <ClientEditForm
              person={p}
              carePlan={data.care_pathway?.membership_name}
              careStatus={data.care_status?.headline}
              onSaved={load}
            />
            <FamilyLoginsCard elderId={p.id} primaryIds={data.family.filter((f) => f.is_primary).map((f) => f.id)} />
            <FamilyContactsCard elderId={p.id} />
            <ClientQuestionsCard elderId={p.id} />
            <section className="card">
              <h2>Feedback</h2>
              <div className="cp-fields">
                <Field
                  label="From the family"
                  value={
                    data.feedback.family_average != null
                      ? `${data.feedback.family_average} / 5 over ${plural(data.feedback.family_count, "visit")}`
                      : "No ratings yet"
                  }
                />
                <Field
                  label="From care managers"
                  value={
                    data.feedback.staff_average != null
                      ? `${data.feedback.staff_average} / 5 over ${plural(data.feedback.staff_count, "visit")}`
                      : "No feedback yet"
                  }
                />
              </div>
            </section>
          </div>
          <KnowThemCard elderId={p.id} />
          <HomeLocationCard elderId={p.id} home={data.home_location} addressPoint={data.address_point} onSaved={load} />
        </>
      ) : null}

      {tab === "Visits & requests" ? (
        <>
          <section className="card">
            <h2>Open family requests</h2>
            {openRequestRows.length === 0 ? <p className="muted">No open requests.</p> : null}
            <ul className="cp-list cp-reqs">
              {openRequestRows.map((r) => (
                <li key={r.id}>
                  <div className="cp-req-text">
                    <strong>{requestLabel(r)}</strong>
                    <span className={`cp-pill cp-pill-${r.status || "requested"}`}>{word(r.status || "requested")}</span>
                    <span className="muted">
                      {" "}
                      · asked {day(r.created_at)}
                      {r.preferred_at || r.preferred_date ? ` · wants ${day(r.preferred_at || r.preferred_date)}` : ""}
                    </span>
                    {r.notes ? <p className="muted cp-req-notes">{r.notes}</p> : null}
                  </div>
                  {edit && String(r.status || "requested") === "requested" ? (
                    <button
                      type="button"
                      className="primary"
                      onClick={() => {
                        setPrefill({
                          elder_id: p.id,
                          kind: requestKind(r),
                          request_id: r.id,
                          title: requestLabel(r),
                          tasks: r.notes || undefined,
                        });
                        window.setTimeout(
                          () => document.getElementById("cp-schedule")?.scrollIntoView({ behavior: "smooth", block: "start" }),
                          50,
                        );
                      }}
                    >
                      Schedule
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          </section>
          <div id="cp-schedule">
            <ScheduleJobs elderId={p.id} title="Visits" prefill={prefill} />
          </div>
          <p>
            <button type="button" className="cp-linkbtn" onClick={() => setTab("Health")}>
              Visit reports, photos and feedback: Health → Visit history
            </button>
          </p>
        </>
      ) : null}

      {tab === "Health" ? (
        <>
          {/* AI first: room hazard check and the before/after preview. */}
          <ClientRoomCheck elderId={p.id} />
          <ClientAiPreviews elderId={p.id} />
          <ClientKushLife elderId={p.id} />
          <ClientAssessments elderId={p.id} />
          <h2 className="cp-section-title">Visit history</h2>
          <ClientHistory
            elderId={p.id}
            visits={data.visits}
            assessments={data.assessments ?? []}
            requests={data.service_requests}
          />
          {data.visits.length ? (
            <p>
              <button type="button" className="cp-linkbtn" onClick={() => setShowMap((v) => !v)}>
                {showMap ? "Hide visit map and visit details" : `Show visit map and visit details (${data.visits.length})`}
              </button>
            </p>
          ) : null}
          {showMap && data.visits.length ? (
            <>
              <section className="card cp-map">
                <div className="cp-visit-head">
                  <h2>Visit map</h2>
                  <span className="muted">
                    {pins.length} of {data.visits.length} visits have a location
                  </span>
                </div>
                <VisitMap pins={pins} home={data.home_location} focusId={focusId} />
                <p className="muted cp-map-legend">
                  <span className="cp-dot cp-dot-ok" /> at home <span className="cp-dot cp-dot-warn" /> away from home{" "}
                  <span className="cp-dot cp-dot-neutral" /> no home set <span className="cp-dot cp-dot-home" /> client&apos;s home
                </p>
              </section>
              <ul className="cp-visits">
                {data.visits.map((v) => (
                  <VisitCard
                    key={v.id}
                    elderId={p.id}
                    visit={v}
                    onChanged={load}
                    onShowOnMap={(id) => setFocusId(id)}
                  />
                ))}
              </ul>
            </>
          ) : null}
        </>
      ) : null}

      {tab === "Plan & payments" ? (
        <div className="cm-money">
          <PlanPaymentsCard elderId={p.id} name={name} />
          <ClientOrders elderId={p.id} />
          <section className="card cm-wallet">
            <h2>Wallet balance: {formatPaise(data.wallet.balance_minor)}</h2>
            {data.receipts.length === 0 ? (
              <p className="muted">No payments yet.</p>
            ) : (
              <div className="cp-table-wrap">
                <table className="cp-table">
                  <thead>
                    <tr>
                      <th>Receipt</th>
                      <th>Date</th>
                      <th>Description</th>
                      <th>Status</th>
                      <th className="cp-num">Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.receipts.map((r) => (
                      <tr key={r.id}>
                        <td>{r.receipt_number}</td>
                        <td>{day(r.date)}</td>
                        <td>
                          {r.description}
                          {/* "Wallet top-up / Wallet top-up": the type line only when it adds something. */}
                          {r.kind_label && r.kind_label.trim().toLowerCase() !== (r.description || "").trim().toLowerCase() ? (
                            <div className="muted">{r.kind_label}</div>
                          ) : null}
                        </td>
                        <td>{word(r.status)}</td>
                        <td className="cp-num">{r.amount_display}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
          <ClientInvoices elderId={p.id} />
        </div>
      ) : null}

      {tab === "SOS & alerts" ? (
        <>
        <ClientAlertsPanel elderId={p.id} onChanged={load} />
        <div className="cp-cols">
          <section className="card">
            <h2>Recent alerts</h2>
            {data.incidents.length === 0 ? <p className="muted">No alerts so far.</p> : null}
            <ul className="cp-list">
              {data.incidents.map((i) => (
                <li key={i.id}>
                  <strong>{ALERT_KIND[i.kind] ?? word(i.kind)}</strong>
                  <span className={`cp-pill cp-pill-${i.status}`}>{word(i.status)}</span>
                  <span className="muted"> · {dayTime(i.opened_at)}</span>
                  {i.outcome ? <span className="muted"> · {word(i.outcome)}</span> : null}
                </li>
              ))}
            </ul>
            <p>
              <Link className="secondary cp-inline-btn" href="/kushalaya/alerts">Open the alerts queue →</Link>
            </p>
          </section>
          <ClientDevicesCard elderId={p.id} devices={data.devices} formatSeen={dayTime} onChanged={load} />
        </div>
        </>
      ) : null}

      {tab === "Incidents" ? <ClientIncidents elderId={p.id} /> : null}

      {tab === "Care" ? (
        <>
          <ClientCareSheet elderId={p.id} />
          <ClientCarePlan elderId={p.id} />
          <ClientRiskRegister elderId={p.id} />
          <ClientHandovers elderId={p.id} onMoved={load} />
          <VisitChecklistCard elderId={p.id} />
        </>
      ) : null}

      {tab === "Messages" ? (
        <section className="cp-msgs">
          <MessageThread elderId={p.id} embedded showClientLink={false} onChanged={load} />
          <p>
            <Link className="secondary cp-inline-btn" href={`/kushalaya/messages?elder=${p.id}`}>Open in Messages →</Link>
          </p>
        </section>
      ) : null}

      {tab === "Documents" ? (
        <section className="card">
          <h2>Documents</h2>
          <ClientDocuments elderId={p.id} docs={data.documents} onChanged={load} day={day} />
          <ContractsPanel kind="client" elderId={p.id} partyName={`${p.first_name} ${p.last_name}`.trim()} canEdit={edit} />
          {data.documents.some((d) => d.document_type === "HOME_SAFETY_PHOTO") ? (
            <>
              <h3 className="cd-photos-title">Visit photos</h3>
              <div className="cp-photos">
                {data.documents.filter((d) => d.document_type === "HOME_SAFETY_PHOTO").map((d) => (
                  <StaffPhoto key={d.id} id={d.id} />
                ))}
              </div>
            </>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

function nextAssessment(r: ClientProfile["reassessment"]) {
  if (!r) return "Not recorded";
  if (r.booked_at) return `Booked ${day(r.booked_at)}`;
  if (r.needs_first) return "First assessment needed";
  return `${r.overdue ? "Overdue · " : ""}${day(r.due_at)}`;
}

/** Money tab: this client's GST invoices and credit notes (hidden when the role can't list invoices). */
function ClientInvoices({ elderId }: { elderId: number }) {
  const [rows, setRows] = useState<Invoice[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    listInvoices()
      .then((r) => setRows(r.invoices.filter((i) => i.elder_id === elderId)))
      .catch(() => setRows(null));
  }, [elderId]);
  if (rows === null) return null;
  return (
    <section className="card">
      <h2>Invoices</h2>
      {error ? <p className="error-text">{error}</p> : null}
      {rows.length === 0 ? (
        <p className="muted">No invoices yet.</p>
      ) : (
        <ul className="cp-list">
          {rows.map((r) => (
            <li key={r.id} className="cp-inv">
              <strong>{r.number}</strong>
              <span className="muted">
                {" "}
                · {r.title} · {r.issued_at ? day(r.issued_at) : "Not issued"} ·{" "}
                {inr(r.kind === "credit_note" ? -Math.abs(r.total_paise) : r.total_paise)}
              </span>
              <button
                type="button"
                className="secondary"
                onClick={() => downloadInvoicePdf(r).catch((e) => setError(e instanceof Error ? e.message : "Download failed"))}
              >
                PDF
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** Client Overview: KushLife over the last 12 visits (with flags to acknowledge) and the care journey. */
function ClientKushLife({ elderId }: { elderId: number }) {
  const [kl, setKl] = useState<KushLifeView | null>(null);
  const [journey, setJourney] = useState<Journey | null>(null);
  const load = useCallback(() => {
    api<KushLifeView>(`/api/v1/home-safety/clients/${elderId}/kushlife?limit=12`).then(setKl).catch(() => undefined);
    api<Journey>(`/api/v1/home-safety/clients/${elderId}/journey`).then(setJourney).catch(() => undefined);
  }, [elderId]);
  useEffect(() => load(), [load]);
  return (
    <div className="cp-cols cp-kl">
      <section className="card">
        {kl ? (
          <KushLifeTrend
            view={kl}
            staff
            ackUrl={can("edit") ? `/api/v1/home-safety/clients/${elderId}/kushlife/acknowledge` : undefined}
            onChanged={load}
          />
        ) : (
          <p className="muted">Loading KushLife…</p>
        )}
        {can("edit") ? <KushLifeBaselineEditor elderId={elderId} onSaved={load} /> : null}
        <KushLifeWeeklyPanel elderId={elderId} />
        <KushLifeQualityPanel elderId={elderId} />
      </section>
      {journey ? (
        <section className="card">
          <JourneySteps journey={journey} />
        </section>
      ) : null}
    </div>
  );
}
