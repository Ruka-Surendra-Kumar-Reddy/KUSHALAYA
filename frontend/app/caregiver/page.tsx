"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { startLiveSharing } from "@/lib/live-location";
import { Directions } from "@/components/Directions";
import { useRouter } from "next/navigation";
import { clearAuth, getStoredAuth } from "@/lib/api";
import { SosSiren } from "@/components/SosSiren";
import { isCaregiverRole } from "@/lib/auth";
import {
  fetchCaregiverMe,
  getOrCreateDeviceId,
  registerCaregiverPortalDevice,
  type CaregiverPortalMe,
} from "@/lib/caregiverPortal";
import {
  fetchCaregiverEarnings,
  fetchCaregiverPayslips,
  type CaregiverEarningsSummary,
  type CaregiverPayslipSummary,
} from "@/lib/caregiverPayroll";
import { myJobs, setMyJobStatus, type CareJob } from "@/lib/jobs";
import { greetingIST, isTodayIST } from "@/lib/ist";
import { isStaleCheckIn, staleLabel } from "@/lib/run-sheet";
import { PublicBrandMark } from "@/components/BrandLogo";
import { publicBrandName } from "@/lib/public-brand";
import { portalFont } from "@/components/portal-font";
import { VisitReportSheet } from "./VisitReportSheet";
import { LocationNeeded } from "./LocationNeeded";
import { requireLocation } from "@/lib/visit-location";
import { EmergencySheet, myEmergencies, type MyEmergency } from "./EmergencySheet";
import { IncidentSheet } from "./IncidentSheet";
import { ClientSheetPanel } from "./ClientSheetPanel";
import { LeaveCard } from "./LeaveCard";
import "./caregiver.css";

const inr = (n: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n);

const time = (iso: string | null) =>
  iso ? new Date(iso).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit", timeZone: "Asia/Kolkata" }) : "Any time";

const day = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short", timeZone: "Asia/Kolkata" }) : "";

const shortDate = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", timeZone: "Asia/Kolkata" });

function isToday(iso: string | null) {
  return isTodayIST(iso);
}

/**
 * Caregiver field app: today's jobs (visits, assessments, installs) with
 * On my way → Check in (GPS) → Complete, assessments in a simple step-by-step
 * screen, and pay. Signed in from the staff sign-in page; phone-first.
 */
export default function CaregiverHome() {
  const router = useRouter();
  const [me, setMe] = useState<CaregiverPortalMe | null>(null);
  const [jobs, setJobs] = useState<CareJob[] | null>(null);
  // Phone's clock only: the server renders in UTC, so the greeting and date wait for the browser.
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => setNow(new Date()), []);
  const [earnings, setEarnings] = useState<CaregiverEarningsSummary | null>(null);
  const [slips, setSlips] = useState<CaregiverPayslipSummary[]>([]);
  const [busy, setBusy] = useState<number | null>(null);
  const [note, setNote] = useState<{ tone: "ok" | "warn"; text: string } | null>(null);
  const [error, setError] = useState("");
  const [reporting, setReporting] = useState<CareJob | null>(null);
  const [emergencyFor, setEmergencyFor] = useState<CareJob | null>(null);
  const [incidentFor, setIncidentFor] = useState<CareJob | null>(null);
  const [emergencies, setEmergencies] = useState<MyEmergency[]>([]);
  const loadEmergencies = useCallback(() => myEmergencies().then(setEmergencies).catch(() => undefined), []);

  const loadJobs = useCallback(() => myJobs().then(setJobs), []);

  // Live location: shared only while a job is "on the way" and this app is open.
  const sharing = useRef(new Map<number, () => void>());
  const [locDenied, setLocDenied] = useState(false);
  const [locNeed, setLocNeed] = useState<{ job: CareJob; status: "checked_in" | "completed" } | null>(null);
  useEffect(() => {
    const active = new Set((jobs ?? []).filter((j) => j.status === "on_the_way").map((j) => j.id));
    for (const [id, stop] of sharing.current) {
      if (!active.has(id)) {
        stop();
        sharing.current.delete(id);
      }
    }
    for (const id of active) {
      if (sharing.current.has(id)) continue;
      const stop = startLiveSharing(id, {
        onDenied: () => setLocDenied(true),
        onStopped: () => sharing.current.delete(id),
      });
      sharing.current.set(id, stop);
    }
  }, [jobs]);
  useEffect(() => {
    const all = sharing.current;
    return () => {
      for (const stop of all.values()) stop();
      all.clear();
    };
  }, []);

  useEffect(() => {
    const auth = getStoredAuth();
    if (!auth || !isCaregiverRole(auth.role)) {
      router.replace("/login");
      return;
    }
    fetchCaregiverMe().then(setMe).catch((e) => setError(String(e?.message || e)));
    loadJobs().catch((e) => setError(String(e?.message || e)));
    fetchCaregiverEarnings().then(setEarnings).catch(() => undefined);
    fetchCaregiverPayslips().then(setSlips).catch(() => undefined);
    registerCaregiverPortalDevice(getOrCreateDeviceId(), "Caregiver phone").catch(() => undefined);
    void loadEmergencies();
  }, [router, loadJobs, loadEmergencies]);

  async function move(job: CareJob, status: "on_the_way" | "checked_in" | "completed") {
    setBusy(job.id);
    setNote(null);
    setLocNeed(null);
    try {
      let extra: { latitude?: number; longitude?: number; accuracy?: number | null; note?: string } = {};
      if (status !== "on_the_way") {
        // Check-in and finishing must say where they happened: no location, no step.
        try {
          extra = await requireLocation();
        } catch {
          setLocNeed({ job, status });
          return;
        }
      }
      if (status === "completed") {
        const text = window.prompt("Anything the family should know? (optional)") ?? "";
        if (text.trim()) extra.note = text.trim();
      }
      await setMyJobStatus(job.id, status, extra);
      setNote({
        tone: "ok",
        text:
          status === "on_the_way"
            ? `The family knows you're on the way to ${job.elder_name}. Your location is shared with them and your care manager until you check in.`
            : status === "checked_in"
              ? `Checked in at ${job.elder_name}'s home.`
              : `${job.title} completed. The family has been told.`,
      });
      await loadJobs();
    } catch (e) {
      setNote({ tone: "warn", text: e instanceof Error ? e.message : "Could not update" });
    } finally {
      setBusy(null);
    }
  }

  function signOut() {
    clearAuth();
    router.replace("/login");
  }

  const today = (jobs ?? []).filter((j) => isToday(j.scheduled_at));
  // Checked in (or on the way) on an earlier day and never finished: always shown first.
  const unfinished = (jobs ?? []).filter(
    (j) => !isToday(j.scheduled_at) && (j.status === "checked_in" || j.status === "on_the_way") && new Date(j.scheduled_at ?? 0) <= new Date(),
  );
  const weekEnd = Date.now() + 7 * 86_400_000;
  const later = (jobs ?? []).filter(
    (j) => !isToday(j.scheduled_at) && new Date(j.scheduled_at ?? 0) > new Date() && new Date(j.scheduled_at ?? 0).getTime() <= weekEnd,
  );
  const done = today.filter((j) => j.status === "completed").length;
  const greet = now ? greetingIST(now) : "Hello";

  const card = (j: CareJob) => {
    const finished = j.status === "completed";
    return (
      <li key={j.id} className={`cg-visit is-${j.status}${finished ? " is-done" : ""}`}>
        <div className="cg-visit-head">
          <span className="cg-time">
            {isToday(j.scheduled_at) ? time(j.scheduled_at) : `${day(j.scheduled_at)} · ${time(j.scheduled_at)}`}
          </span>
          <span className={`cg-status${isStaleCheckIn(j) ? " is-stale" : ""}`}>{isStaleCheckIn(j) ? staleLabel(j) : j.status_label}</span>
        </div>
        <p className="cg-kind">{j.title}</p>
        <h3>{j.elder_name}</h3>
        {j.location || j.elder_address ? <p className="cg-addr">{j.location || j.elder_address}</p> : null}
        {j.tasks ? <p className="cg-tasks">{j.tasks}</p> : null}
        {j.know_them && !finished && Object.entries(j.know_them).some(([k, v]) => k !== "updated_at" && v) ? (
          <details className="cg-know">
            <summary>Before you knock — know {j.elder_name.split(" ")[0]}</summary>
            {j.know_them.approach ? <p><strong>Approach:</strong> {j.know_them.approach}</p> : null}
            {j.know_them.likes ? <p><strong>Likes:</strong> {j.know_them.likes}</p> : null}
            {j.know_them.avoid ? <p><strong>Avoid:</strong> {j.know_them.avoid}</p> : null}
            {j.know_them.routine ? <p><strong>Routine:</strong> {j.know_them.routine}</p> : null}
            {j.know_them.notes ? <p>{j.know_them.notes}</p> : null}
          </details>
        ) : null}
        {isToday(j.scheduled_at) && !finished ? <ClientSheetPanel jobId={j.id} /> : null}
        {j.status === "on_the_way" ? (
          <p className="lv-note" role="status">
            {locDenied
              ? "Location is off, so the family can't see you on the map. That's fine — the visit still works. To share, allow location for this site in your phone settings."
              : "Sharing your location with the family and your care manager while you're on the way. It stops when you check in."}
          </p>
        ) : null}
        <div className="cg-actions">
          {j.status === "scheduled" ? (
            <>
              <button type="button" className="cg-btn is-soft" disabled={busy !== null} onClick={() => move(j, "on_the_way")}>
                On my way
              </button>
              <button type="button" className="cg-btn" disabled={busy !== null} onClick={() => move(j, "checked_in")}>
                {busy === j.id ? "Getting location…" : "Check in"}
              </button>
            </>
          ) : null}
          {j.status === "on_the_way" ? (
            // On the way: directions first and big, so the caregiver can start the route in one tap.
            <Directions
              home={j.elder_home}
              address={j.elder_address}
              location={j.location}
              name={j.elder_name}
              label="Get directions"
              className="cg-directions is-inline is-primary"
              summaryClassName="cg-btn"
            />
          ) : null}
          {j.status === "on_the_way" ? (
            <button type="button" className="cg-btn is-soft" disabled={busy !== null} onClick={() => move(j, "checked_in")}>
              {busy === j.id ? "Getting location…" : "Check in"}
            </button>
          ) : null}
          {j.status === "checked_in" && j.kind === "assessment" ? (
            <Link className="cg-btn is-out" href={`/caregiver/assess/${j.id}`}>
              {j.assessment_id ? "Continue assessment" : "Start assessment"}
            </Link>
          ) : null}
          {j.status === "checked_in" && j.kind !== "assessment" ? (
            <button type="button" className="cg-btn is-out" disabled={busy !== null} onClick={() => setReporting(j)}>
              Complete
            </button>
          ) : null}
          {!finished && j.elder_phone ? (
            <a className="cg-btn is-ghost" href={`tel:${j.elder_phone.replace(/[^\d+]/g, "")}`}>
              Call
            </a>
          ) : null}
          {!finished && j.status !== "on_the_way" ? (
            <Directions
              home={j.elder_home}
              address={j.elder_address}
              location={j.location}
              name={j.elder_name}
              className="cg-directions is-inline"
              summaryClassName="cg-btn is-ghost"
            />
          ) : null}
          {j.status === "checked_in" || finished ? (
            <button type="button" className="cg-btn is-ghost" onClick={() => setIncidentFor(j)}>
              Report incident
            </button>
          ) : null}
          <button type="button" className="cg-btn is-emg" onClick={() => setEmergencyFor(j)}>
            Emergency
          </button>
        </div>
      </li>
    );
  };

  return (
    <div className={`cg-app ${portalFont.variable}`}>
      <SosSiren />
      <header className="cg-bar">
        <PublicBrandMark variant="header" className="cg-logo" />
        <span className="cg-bar-title">{publicBrandName()}</span>
        <button type="button" className="cg-signout" onClick={signOut}>
          Sign out
        </button>
      </header>

      {reporting ? (
        <VisitReportSheet
          job={reporting}
          onClose={() => setReporting(null)}
          onDone={(msg) => {
            setReporting(null);
            setNote({ tone: "ok", text: msg });
            void loadJobs();
          }}
        />
      ) : null}

      {incidentFor ? (
        <IncidentSheet
          job={incidentFor}
          onClose={() => setIncidentFor(null)}
          onDone={(msg) => {
            setIncidentFor(null);
            setNote({ tone: "ok", text: msg });
          }}
        />
      ) : null}

      {emergencyFor ? (
        <EmergencySheet
          job={emergencyFor}
          onClose={() => setEmergencyFor(null)}
          onDone={(msg) => {
            setEmergencyFor(null);
            setNote({ tone: "warn", text: msg });
            void loadEmergencies();
          }}
        />
      ) : null}

      <main className="cg-main">
        <section className="cg-hero">
          <p className="cg-eyebrow">Care team · field app</p>
          <h1>
            {greet}
            {me ? `, ${me.first_name}` : ""}
          </h1>
          <p className="cg-hero-sub">
            {now ? now.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", timeZone: "Asia/Kolkata" }) : ""}
            {jobs ? ` · ${today.length} today · ${done} done` : ""}
          </p>
        </section>

        {emergencies.map((e) => {
          const name = jobs?.find((j) => j.elder_id === e.elder_id)?.elder_name || "your client";
          return (
            <p key={e.id} className="cg-emg-banner" role="status">
              <strong>Emergency — {name}{e.type_label ? ` (${e.type_label})` : ""}.</strong>{" "}
              {e.owner_name ? `${e.owner_name} is handling it.` : "The team is handling it."}
              {e.steps_done.length ? ` Done so far: ${e.steps_done.join(", ")}.` : ""}
            </p>
          );
        })}
        {error ? <p className="cg-note is-warn">{error}</p> : null}
        {note ? <p className={`cg-note is-${note.tone}`}>{note.text}</p> : null}
        {locNeed ? (
          <LocationNeeded
            action={locNeed.status}
            busy={busy !== null}
            onRetry={() => void move(locNeed.job, locNeed.status)}
            onCancel={() => setLocNeed(null)}
          />
        ) : null}

        {unfinished.length ? (
          <section aria-labelledby="cg-unfinished">
            <h2 id="cg-unfinished" className="cg-h2">Finish this visit</h2>
            <p className="cg-note is-warn">
              {unfinished.length === 1 ? "This visit is" : "These visits are"} still open. Write the report to close{" "}
              {unfinished.length === 1 ? "it" : "them"}, or tell your manager if it didn&apos;t happen.
            </p>
            <ul className="cg-list">{unfinished.map(card)}</ul>
          </section>
        ) : null}

        <section aria-labelledby="cg-today">
          <h2 id="cg-today" className="cg-h2">Today</h2>
          {jobs === null ? (
            <p className="cg-empty">Loading your day…</p>
          ) : today.length === 0 ? (
            <p className="cg-empty">Nothing scheduled today. Your manager will add work here.</p>
          ) : (
            <ul className="cg-list">{today.map(card)}</ul>
          )}
        </section>

        {later.length ? (
          <section aria-labelledby="cg-next">
            <h2 id="cg-next" className="cg-h2">Next 7 days</h2>
            <ul className="cg-week">
              {later.map((j) => (
                <li key={j.id}>
                  <span className="cg-week-when">
                    <strong>{day(j.scheduled_at)}</strong>
                    <small>{time(j.scheduled_at)}</small>
                  </span>
                  <span className="cg-week-who">
                    <strong>{j.elder_name}</strong>
                    <small>{j.title}</small>
                  </span>
                  <span className="cg-week-act">
                    {j.elder_phone ? (
                      <a className="cg-btn is-ghost" href={`tel:${j.elder_phone.replace(/[^\d+]/g, "")}`} aria-label={`Call ${j.elder_name}`}>
                        Call
                      </a>
                    ) : null}
                    <Directions
                      home={j.elder_home}
                      address={j.elder_address}
                      location={j.location}
                      name={j.elder_name}
                      className="cg-directions is-inline"
                      summaryClassName="cg-btn is-ghost"
                    />
                  </span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        <LeaveCard />

        <section aria-labelledby="cg-pay" className="cg-pay">
          <h2 id="cg-pay" className="cg-h2">My pay</h2>
          <div className="cg-pay-grid">
            <div>
              <small>Paid this year</small>
              <strong>{earnings ? inr(earnings.ytd_net) : "—"}</strong>
            </div>
            <div>
              <small>Hours this year</small>
              <strong>{earnings ? Math.round(earnings.ytd_hours) : "—"}</strong>
            </div>
            <div>
              <small>Last pay</small>
              <strong>{earnings?.last_period ? inr(earnings.last_period.net) : "—"}</strong>
            </div>
          </div>
          {slips.length ? (
            <ul className="cg-slips">
              {slips.slice(0, 6).map((p) => (
                <li key={p.run_id}>
                  <span>
                    {shortDate(p.period_start)} – {shortDate(p.period_end)}
                  </span>
                  <span>{Math.round(p.hours)} h</span>
                  <strong>{inr(p.net)}</strong>
                </li>
              ))}
            </ul>
          ) : (
            <p className="cg-empty">Payslips appear here once a pay run is finalised.</p>
          )}
        </section>
      </main>
    </div>
  );
}
