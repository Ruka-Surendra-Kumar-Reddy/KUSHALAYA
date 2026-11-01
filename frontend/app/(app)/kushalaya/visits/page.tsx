"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { Flash } from "@/components/Flash";
import { OpsModal } from "@/components/ops/OpsModal";
import { api } from "@/lib/api";
import { createJob, isClash, JOB_KIND_LABEL, listJobs, staffProgress, staffShareLocation, updateJob, type CareJob, type JobKind } from "@/lib/jobs";
import { LiveVisitMap } from "@/components/LiveVisitMap";
import { trackUrl } from "@/lib/live-location";
import { copyText } from "@/lib/share";
import { updateStaffServiceRequest } from "@/lib/livewell/familyApi";
import { OpsLiveBadge } from "@/components/ops/OpsLiveBadge";
import { Directions } from "@/components/Directions";
import { istInputToISO, istInputValue, timeIST, whenIST } from "@/lib/ist";
import { VisitReportSheet } from "@/app/caregiver/VisitReportSheet";
import "@/components/ops/schedule.css";
import { can } from "@/lib/roles";
import { arrivalAt, isStaleCheckIn, staleLabel } from "@/lib/run-sheet";

type Client = { id: number; first_name: string; last_name: string };
type Caregiver = { id: number; first_name: string; last_name: string };
type Request = {
  elder_id: number;
  elder_name: string;
  id: string;
  label: string;
  group?: string;
  notes: string;
  preferred_at?: string;
  created_at: string;
  requested_by?: string;
};

type Tab = "today" | "upcoming" | "requests" | "missed" | "past";

const TABS: { id: Tab; label: string }[] = [
  { id: "today", label: "Today" },
  { id: "upcoming", label: "Upcoming" },
  { id: "requests", label: "Requests" },
  { id: "missed", label: "Missed" },
  { id: "past", label: "Past" },
];

const MORE_LINKS = [
  { href: "/kushalaya/visits/roster", label: "Repeating visits" },
  { href: "/kushalaya/visits/leave", label: "Leave & cover" },
  { href: "/kushalaya/visits/log", label: "Log a past visit" },
  { href: "/kushalaya/assessments", label: "Assessment reports" },
];

const CLOSED = new Set(["completed", "cancelled", "missed"]);
// Reschedule and cancel stay open until the visit has actually begun.
const MOVABLE = new Set(["scheduled", "on_the_way"]);
const DAY = 86400000;
const UNFINISHED_AFTER = 4 * 3600000;
// Missed visits stay on the Missed tab for a month, so they can be rebooked.
const MISSED_DAYS = 30;

const EMPTY_FORM = {
  elder_id: "",
  kind: "visit" as JobKind,
  date: "",
  time: "10:00",
  caregiver_id: "",
  tasks: "",
  request_id: "",
  title: "",
};

type Reassessment = {
  elder_id: number;
  elder_name: string;
  label: string;
  due_at: string | null;
  overdue: boolean;
  needs_first: boolean;
  has_draft?: boolean;
};

/** "YYYY-MM-DDTHH:MM" in India time for an ISO instant (everything is shown in IST). */
function istValue(iso: string) {
  return istInputValue(new Date(iso).getTime() - Date.now());
}

function istTime(iso: string) {
  return timeIST(iso);
}

function istWhen(iso: string) {
  return new Date(iso).toLocaleString("en-IN", { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit", timeZone: "Asia/Kolkata" });
}

function since(iso: string) {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (Number.isNaN(mins)) return "";
  if (mins < 60) return `${mins || 1} min ago`;
  if (mins < 1440) return `${Math.round(mins / 60)} h ago`;
  const days = Math.round(mins / 1440);
  return days === 1 ? "yesterday" : `${days} days ago`;
}

function dayKey(iso: string | null) {
  if (!iso) return "No date";
  return istValue(iso).slice(0, 10);
}

function dayLabel(key: string) {
  if (key === "No date") return key;
  const d = new Date(`${key}T00:00:00Z`);
  const today = new Date(`${istInputValue().slice(0, 10)}T00:00:00Z`);
  const diff = Math.round((d.getTime() - today.getTime()) / DAY);
  const name = d.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" });
  if (diff === 0) return `Today · ${name}`;
  if (diff === 1) return `Tomorrow · ${name}`;
  if (diff === -1) return `Yesterday · ${name}`;
  return name;
}

/** Date and time inputs (India time) → ISO, or an error when it's in the past. */
function futureISO(date: string, time: string): { iso: string } | { error: string } {
  const iso = istInputToISO(`${date}T${time || "10:00"}`);
  if (Number.isNaN(new Date(iso).getTime())) return { error: "Pick a date and time" };
  if (new Date(iso).getTime() < Date.now() - 5 * 60000) {
    return { error: "That time has already passed. Pick a later time, or use “Log a past visit”." };
  }
  return { iso };
}

function errText(e: unknown, fallback: string) {
  return e instanceof Error && e.message ? e.message : fallback;
}

function todayStart() {
  return new Date(istInputToISO(`${istInputValue().slice(0, 10)}T00:00`)).getTime();
}

/** Which tab a visit lives on. Never-started visits from earlier days count as missed. */
function tabOf(j: CareJob, start: number): Exclude<Tab, "requests"> {
  const at = j.scheduled_at ? new Date(j.scheduled_at).getTime() : null;
  if (j.status === "missed" || (j.status === "scheduled" && at !== null && at < start)) return "missed";
  if (at !== null && at >= start && at < start + DAY) return "today";
  // A cancelled visit that was booked for a later day stays with the upcoming ones.
  if (j.status === "cancelled" && at !== null && at >= start + DAY) return "upcoming";
  if (CLOSED.has(j.status) || (at !== null && at < start)) return "past";
  return "upcoming";
}

function asTab(v: string | null): Tab | null {
  if (v === "today" || v === "upcoming" || v === "requests" || v === "missed" || v === "past") return v;
  // Older links used ?range=
  if (v === "week") return "upcoming";
  return null;
}

/**
 * Visits: today's visits, family requests waiting to be booked, what's coming
 * up, what was missed and what happened — one list per tab (?tab=…).
 */
/** localStorage: the visit this browser is sharing its location for (survives a reload). */
const SHARE_KEY = "ks-sharing-job";

export default function VisitsPage() {
  // View-only staff see every visit; booking and visit steps are for staff who can act.
  const edit = can("edit");
  const [jobs, setJobs] = useState<CareJob[] | null>(null);
  const [clients, setClients] = useState<Client[]>([]);
  const [caregivers, setCaregivers] = useState<Caregiver[]>([]);
  const [requests, setRequests] = useState<Request[]>([]);
  const [tab, setTabState] = useState<Tab>("today");
  const [kind, setKind] = useState<JobKind | "all">("all");
  const [cg, setCg] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [sheet, setSheet] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [reporting, setReporting] = useState<CareJob | null>(null);
  const [clash, setClash] = useState("");
  const [moving, setMoving] = useState<{ id: number; date: string; time: string } | null>(null);
  // Roster chips link here with ?job=<id> — open its tab and highlight that visit.
  const [focusJob, setFocusJob] = useState<number | null>(null);
  // Live location: a care manager who taps "On the way" here shares this browser's position
  // (the family follows it on the tracking link); the Live map shows whoever is on the way.
  const [sharing, setSharing] = useState<{ id: number; name: string; trackPath: string | null } | null>(null);
  const [mapJobId, setMapJobId] = useState<number | null>(null);
  const [roadEta, setRoadEta] = useState<{ minutes: number; km: number } | null>(null);
  const shareStartedAt = useRef(0);

  function setTab(t: Tab) {
    setTabState(t);
    setSheet(false);
    try {
      const u = new URL(window.location.href);
      u.searchParams.set("tab", t);
      u.searchParams.delete("range");
      window.history.replaceState(window.history.state, "", u.toString());
    } catch {
      /* the tab still changes */
    }
  }

  function say(msg: string) {
    setError("");
    setMessage(msg);
  }

  function fail(e: unknown, fallback: string) {
    setMessage("");
    setError(errText(e, fallback));
  }

  function startSharing(j: CareJob) {
    shareStartedAt.current = Date.now();
    setSharing({ id: j.id, name: j.elder_name, trackPath: j.live?.track_path ?? null });
    try {
      localStorage.setItem(SHARE_KEY, String(j.id));
    } catch {
      /* sharing still runs while this page is open */
    }
  }

  function stopSharing() {
    setSharing(null);
    try {
      localStorage.removeItem(SHARE_KEY);
    } catch {
      /* nothing stored */
    }
  }

  async function copyTrack(path: string | null | undefined) {
    const url = trackUrl(path);
    if (url && (await copyText(url))) say("Tracking link copied — paste it into WhatsApp or a message.");
    else fail(null, "Couldn't copy the tracking link");
  }

  async function progress(j: CareJob, status: "on_the_way" | "checked_in") {
    if (status === "checked_in" && !window.confirm("Tell the family you've arrived?")) return;
    try {
      await staffProgress(j.id, status);
      if (status === "on_the_way") startSharing(j);
      else if (sharing?.id === j.id) stopSharing();
      say(
        status === "on_the_way"
          ? `The family knows you're on the way to ${j.elder_name} — your live location is shared with them.`
          : `Arrived at ${j.elder_name}'s home — the family has been told. ${j.kind === "assessment" ? "Start the assessment" : "Write the report"} when you're ready.`,
      );
      await load();
    } catch (e) {
      fail(e, "Could not update");
    }
  }

  /** After "I've arrived": open the assessment, or the visit report sheet. */
  function openWork(j: CareJob) {
    if (j.kind === "assessment") {
      window.location.href = `/caregiver/assess/${j.id}`;
      return;
    }
    setReporting(j);
  }

  function openForm(next: typeof EMPTY_FORM) {
    setClash("");
    setForm(next);
    setOpen(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  /** A missed job is rebooked as a new one: same client, kind, title, caregiver and family request. */
  function rebook(j: CareJob) {
    openForm({
      ...EMPTY_FORM,
      elder_id: String(j.elder_id),
      kind: j.kind,
      title: j.title,
      tasks: j.tasks,
      caregiver_id: j.caregiver_id ? String(j.caregiver_id) : "",
      request_id: j.request_id || "",
    });
  }

  const load = useCallback(async () => {
    const [j, attn] = await Promise.all([
      listJobs(),
      api<{ requests: Request[]; reassessments?: Reassessment[] }>("/api/v1/home-safety/dashboard/attention"),
    ]);
    setJobs(j);
    // 6-monthly reassessments wait here alongside family requests until booked.
    const due: Request[] = (attn.reassessments || []).map((r) => ({
      id: "",
      elder_id: r.elder_id,
      elder_name: r.elder_name,
      label: r.label,
      group: "assessment",
      created_at: "",
      notes: r.needs_first
        ? r.has_draft
          ? "Assessment started — draft not finished"
          : "No assessment on record yet"
        : `${r.overdue ? "Overdue since" : "Due"} ${new Date(r.due_at as string).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kolkata" })}`,
    }));
    setRequests([...(attn.requests || []), ...due]);
  }, []);

  // Send this browser's position while sharing (every 15 s at most); stop once arrived.
  const sharingId = sharing?.id ?? null;
  useEffect(() => {
    if (sharingId == null || typeof navigator === "undefined" || !("geolocation" in navigator)) return;
    let last = 0;
    let stopped = false;
    const watch = navigator.geolocation.watchPosition(
      (p) => {
        const now = Date.now();
        if (now - last < 15_000) return;
        last = now;
        staffShareLocation(sharingId, { latitude: p.coords.latitude, longitude: p.coords.longitude, accuracy: p.coords.accuracy })
          .then((r) => {
            if (stopped) return;
            if (!r.tracking) stopSharing();
            else if (r.track_path) setSharing((cur) => (cur && cur.id === sharingId ? { ...cur, trackPath: r.track_path ?? null } : cur));
          })
          .catch(() => undefined);
      },
      (err) => {
        if (err.code === err.PERMISSION_DENIED) {
          setError("Location is blocked in this browser, so the family can't see you on the map. Allow location for this site to share it.");
          stopSharing();
        }
      },
      { enableHighAccuracy: true, maximumAge: 10_000, timeout: 30_000 },
    );
    return () => {
      stopped = true;
      navigator.geolocation.clearWatch(watch);
    };
  }, [sharingId]);

  // After a reload: keep sharing for the visit this browser was on the way to.
  useEffect(() => {
    if (!jobs) return;
    let id = 0;
    try {
      id = Number(localStorage.getItem(SHARE_KEY)) || 0;
    } catch {
      return;
    }
    if (!id) return;
    const j = jobs.find((x) => x.id === id);
    if (j && j.status === "on_the_way") {
      setSharing((cur) => cur ?? { id, name: j.elder_name, trackPath: j.live?.track_path ?? null });
    } else if (j?.status === "scheduled" && Date.now() - shareStartedAt.current < 20_000) {
      // A list fetched just before the tap still says "scheduled": not a reason to stop.
    } else stopSharing();
  }, [jobs]);

  // While anyone is on the way, refresh every 30 s so the live map and ETA move.
  const anyMoving = !!jobs?.some((j) => j.status === "on_the_way");
  useEffect(() => {
    if (!anyMoving) return;
    const t = window.setInterval(() => {
      if (document.visibilityState === "visible") load().catch(() => undefined);
    }, 30_000);
    return () => window.clearInterval(t);
  }, [anyMoving, load]);

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : String(e)));
    api<Client[]>("/api/v1/team/clients").then(setClients).catch(() => undefined);
    api<Caregiver[]>("/api/v1/team/caregivers").then(setCaregivers).catch(() => undefined);
    // Dashboard links arrive with ?tab=… or ?schedule=1&elder=…&request=…
    const q = new URLSearchParams(window.location.search);
    const t0 = asTab(q.get("tab")) || asTab(q.get("range"));
    if (t0) setTabState(t0);
    if (q.get("job")) setFocusJob(Number(q.get("job")) || null);
    if (q.get("schedule")) {
      const at = q.get("at") ? new Date(q.get("at") as string) : null;
      const ok = at && !Number.isNaN(at.getTime());
      const v = ok ? istValue(at.toISOString()) : "";
      setForm({
        ...EMPTY_FORM,
        elder_id: q.get("elder") || "",
        kind: (q.get("kind") as JobKind) || "visit",
        request_id: q.get("request") || "",
        title: q.get("title") || "",
        tasks: q.get("notes") || "",
        date: v.slice(0, 10),
        time: v ? v.slice(11, 16) : "10:00",
      });
      setOpen(true);
    }
  }, [load]);

  // ?job= : switch to the tab that visit is on, then scroll to it.
  useEffect(() => {
    if (!focusJob || !jobs) return;
    const j = jobs.find((x) => x.id === focusJob);
    if (j) setTabState(tabOf(j, todayStart()));
  }, [focusJob, jobs]);

  useEffect(() => {
    if (!focusJob || !jobs) return;
    document.getElementById(`job-${focusJob}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [focusJob, jobs, tab]);

  // Close the More menu on an outside click or Escape.
  useEffect(() => {
    if (!moreOpen && !sheet) return;
    const onDown = (e: MouseEvent) => {
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) setMoreOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMoreOpen(false);
        setSheet(false);
      }
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [moreOpen, sheet]);

  function scheduleRequest(r: Request) {
    const v = r.preferred_at ? istValue(r.preferred_at) : "";
    openForm({
      ...EMPTY_FORM,
      elder_id: String(r.elder_id),
      kind: r.group === "assessment" ? "assessment" : r.group === "product" ? "install" : "visit",
      request_id: r.id,
      title: r.label,
      tasks: r.notes,
      // A preferred day already gone is left for the manager to pick.
      date: v && v.slice(0, 10) >= istInputValue().slice(0, 10) ? v.slice(0, 10) : "",
      time: v ? v.slice(11, 16) : "10:00",
    });
  }

  async function declineRequest(r: Request) {
    const note = window.prompt(`Decline “${r.label}” for ${r.elder_name}? The family will be told.\n\nOptional note for the family:`, "");
    if (note === null) return;
    try {
      await updateStaffServiceRequest(r.elder_id, r.id, { status: "declined", staff_note: note.trim() || undefined });
      say(`${r.label} for ${r.elder_name} declined — the family has been told.`);
      await load();
    } catch (e) {
      fail(e, "Could not decline the request");
    }
  }

  async function save(e: { preventDefault(): void }, force = false) {
    e.preventDefault();
    const when = futureISO(form.date, form.time);
    if ("error" in when) {
      fail(null, when.error);
      return;
    }
    setSaving(true);
    setError("");
    try {
      const job = await createJob({
        elder_id: Number(form.elder_id),
        kind: form.kind,
        scheduled_at: when.iso,
        caregiver_id: form.caregiver_id ? Number(form.caregiver_id) : null,
        tasks: form.tasks,
        title: form.title || undefined,
        request_id: form.request_id || undefined,
        force,
      });
      say(`${job.title} booked for ${job.elder_name}. The family has been told.${job.note ? ` ${job.note}` : ""}`);
      setClash("");
      setForm(EMPTY_FORM);
      setOpen(false);
      await load();
    } catch (err) {
      // Double-booked: show the server's message with a "Book anyway" button.
      if (isClash(err)) setClash(err.message);
      else fail(err, "Could not schedule");
    } finally {
      setSaving(false);
    }
  }

  /** PATCH a job; on a double-booking, ask and resend with force. */
  async function patch(j: CareJob, body: Parameters<typeof updateJob>[1]) {
    try {
      return await updateJob(j.id, body);
    } catch (e) {
      if (isClash(e) && window.confirm(e.message)) return updateJob(j.id, { ...body, force: true });
      throw e;
    }
  }

  async function reassign(j: CareJob, value: string) {
    const to = caregivers.find((c) => String(c.id) === value);
    const ask = to
      ? `Assign ${j.title} for ${j.elder_name} to ${to.first_name}? The family will be told.`
      : `Leave ${j.title} for ${j.elder_name} unassigned?`;
    if (!window.confirm(ask)) return;
    try {
      await patch(j, { caregiver_id: to ? to.id : null });
      say(to ? `Assigned to ${to.first_name} — family told.` : "Caregiver removed.");
      await load();
    } catch (e) {
      fail(e, "Could not change the caregiver");
    }
  }

  function startMove(j: CareJob) {
    const v = j.scheduled_at ? istValue(j.scheduled_at) : istInputValue(DAY);
    setMoving({ id: j.id, date: v.slice(0, 10), time: v.slice(11, 16) });
  }

  async function reschedule(j: CareJob) {
    if (!moving) return;
    const when = futureISO(moving.date, moving.time);
    if ("error" in when) {
      fail(null, when.error);
      return;
    }
    try {
      await patch(j, { scheduled_at: when.iso });
      setMoving(null);
      say("Rescheduled — the family has been told.");
      await load();
    } catch (e) {
      fail(e, "Could not reschedule");
    }
  }

  async function cancel(j: CareJob) {
    if (!window.confirm(`Cancel ${j.title} for ${j.elder_name}? The family will be told.`)) return;
    try {
      await updateJob(j.id, { status: "cancelled" });
      say(`${j.title} for ${j.elder_name} cancelled — the family has been told.`);
      await load();
    } catch (e) {
      fail(e, "Could not cancel");
    }
  }

  /** Started more than 4 hours ago and never finished — easy to forget once it drops off Today. */
  const unfinished = useMemo(
    () =>
      (jobs ?? []).filter((j) => {
        if (j.status !== "checked_in" && j.status !== "on_the_way") return false;
        const at = j.checked_in_at || j.started_at || j.scheduled_at;
        return at !== null && Date.now() - new Date(at).getTime() > UNFINISHED_AFTER;
      }),
    [jobs],
  );

  /** Visits per tab, before the type / caregiver / date filters. */
  const byTab = useMemo(() => {
    const start = todayStart();
    const out: Record<Exclude<Tab, "requests">, CareJob[]> = { today: [], upcoming: [], missed: [], past: [] };
    for (const j of jobs ?? []) {
      const t = tabOf(j, start);
      if (t === "missed" && j.scheduled_at && new Date(j.scheduled_at).getTime() < start - MISSED_DAYS * DAY) continue;
      out[t].push(j);
    }
    return out;
  }, [jobs]);

  const filterCount = (kind !== "all" ? 1 : 0) + (cg ? 1 : 0) + (tab === "past" && (from || to) ? 1 : 0);

  const groups = useMemo(() => {
    if (tab === "requests") return [];
    const rows = byTab[tab].filter((j) => {
      if (kind !== "all" && j.kind !== kind) return false;
      if (cg && String(j.caregiver_id ?? "") !== cg) return false;
      if (tab === "past") {
        const k = dayKey(j.scheduled_at);
        if (from && k < from) return false;
        if (to && k > to) return false;
      }
      return true;
    });
    const newestFirst = tab === "past" || tab === "missed";
    rows.sort((a, b) => {
      const d = new Date(a.scheduled_at ?? 0).getTime() - new Date(b.scheduled_at ?? 0).getTime();
      return newestFirst ? -d : d;
    });
    const map = new Map<string, CareJob[]>();
    for (const j of rows) {
      const k = dayKey(j.scheduled_at);
      map.set(k, [...(map.get(k) ?? []), j]);
    }
    return [...map.entries()];
  }, [byTab, tab, kind, cg, from, to]);

  const counts: Partial<Record<Tab, number>> = {
    today: byTab.today.filter((j) => !CLOSED.has(j.status)).length,
    requests: requests.length,
    missed: byTab.missed.length,
  };

  const set = (k: keyof typeof EMPTY_FORM) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });

  const mapJob = mapJobId != null ? (jobs ?? []).find((x) => x.id === mapJobId) ?? null : null;

  const EMPTY_TEXT: Record<Exclude<Tab, "requests">, string> = {
    today: "No visits today",
    upcoming: "Nothing booked ahead",
    missed: `No missed visits in the last ${MISSED_DAYS} days`,
    past: "Nothing in the past yet",
  };

  return (
    <div className="vs-page">
      {reporting ? (
        <VisitReportSheet
          job={reporting}
          onClose={() => setReporting(null)}
          onDone={(msg) => {
            setReporting(null);
            setMessage(msg);
            void load();
          }}
        />
      ) : null}
      <div className="ks-head-row">
        <PageHeader title="Visits" subtitle="Today, upcoming, requests and missed — one list" />
        <div className="ks-head-actions">
          {edit ? (
            <button
              type="button"
              onClick={() => (open ? setOpen(false) : openForm(EMPTY_FORM))}
              aria-label="Schedule a visit"
              title="Schedule a visit"
            >
              <span className="ks-ha-icon" aria-hidden="true">+</span>
              <span className="ks-ha-label">+ Schedule a visit</span>
            </button>
          ) : null}
          <div className="vs-more" ref={moreRef}>
            <button
              type="button"
              className="secondary"
              aria-haspopup="menu"
              aria-expanded={moreOpen}
              aria-label="More"
              title="More"
              onClick={() => setMoreOpen((v) => !v)}
            >
              <span className="ks-ha-icon" aria-hidden="true">⋯</span>
              <span className="ks-ha-label">
                More <span aria-hidden="true">▾</span>
              </span>
            </button>
            {moreOpen ? (
              <div className="vs-menu" role="menu">
                {MORE_LINKS.filter((l) => edit || l.href === "/kushalaya/assessments").map((l) => (
                  <Link key={l.href} href={l.href} role="menuitem" onClick={() => setMoreOpen(false)}>
                    {l.label}
                  </Link>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      </div>
      <Flash error={error} message={message} onClear={() => { setError(""); setMessage(""); }} />
      {sharing ? (
        <div className="vs-sharing" role="status">
          <span className="vs-sharing-dot" aria-hidden="true" />
          <span className="vs-sharing-text">
            <strong>Sharing your live location</strong> with {sharing.name}&apos;s family. Keep this page open on your phone.
          </span>
          <span className="vs-sharing-actions">
            {sharing.trackPath ? (
              <button type="button" className="secondary" onClick={() => void copyTrack(sharing.trackPath)}>
                Copy tracking link
              </button>
            ) : null}
            <button type="button" className="secondary" onClick={stopSharing}>
              Stop sharing
            </button>
          </span>
        </div>
      ) : null}

      <div className="vs-bar">
        {tab !== "requests" ? (
          <button type="button" className="secondary vs-filter-btn" aria-expanded={sheet} onClick={() => setSheet(true)}>
            Filter{filterCount ? ` · ${filterCount}` : ""}
          </button>
        ) : null}
      </div>

      <OpsModal open={mapJob != null} title={mapJob ? `Live tracking · ${mapJob.elder_name}` : "Live tracking"} onClose={() => setMapJobId(null)} wide>
        {mapJob ? (
          <div className="vs-livemap">
            <p className="vs-livemap-eta">
              <strong>{mapJob.live?.caregiver_first_name || "On the way"}</strong>
              {mapJob.live?.position
                ? ` · ${mapJob.live.eta_minutes === 0 ? "arriving now" : roadEta ? `arriving in about ${roadEta.minutes} min (${roadEta.km} km)` : mapJob.live.eta_label || "on the way"}${mapJob.live.stale ? " · last seen a few minutes ago" : ""}`
                : " · no location yet"}
            </p>
            {mapJob.live?.position ? (
              <LiveVisitMap caregiver={mapJob.live.position} home={mapJob.live.home} caregiverLabel={mapJob.live.caregiver_first_name} onRoute={setRoadEta} />
            ) : (
              <p className="muted">
                The map appears when the person on the way shares their location: the caregiver app, or this page open on
                the care manager&apos;s phone after tapping On the way.
              </p>
            )}
            {mapJob.live?.track_path ? (
              <div className="vs-livemap-actions">
                <button type="button" className="secondary" onClick={() => void copyTrack(mapJob.live?.track_path)}>
                  Copy tracking link
                </button>
                <a className="button secondary" href={trackUrl(mapJob.live.track_path)} target="_blank" rel="noopener noreferrer">
                  Open tracking page
                </a>
              </div>
            ) : null}
          </div>
        ) : null}
      </OpsModal>

      <OpsModal open={edit && open} title="Schedule a visit" onClose={() => setOpen(false)} wide>
        <form className="sc-form" onSubmit={save}>
          {error ? <p className="ks-modal-error sc-wide" role="alert">{error}</p> : null}
          {form.request_id ? (
            <p className="sc-from">From a family request{form.title ? `: ${form.title}` : ""}</p>
          ) : null}
          <label>
            Client
            <select value={form.elder_id} onChange={set("elder_id")} required>
              <option value="">Choose…</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.first_name} {c.last_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            What
            <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as JobKind })}>
              <option value="visit">Care visit</option>
              <option value="assessment">Home safety assessment</option>
              <option value="install">Product installation</option>
            </select>
          </label>
          <label>
            Date
            <input type="date" value={form.date} min={istInputValue().slice(0, 10)} onChange={set("date")} required />
          </label>
          <label>
            Time
            <input type="time" value={form.time} onChange={set("time")} />
          </label>
          <label>
            Caregiver
            <select value={form.caregiver_id} onChange={set("caregiver_id")}>
              <option value="">Assign later</option>
              {caregivers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.first_name} {c.last_name}
                </option>
              ))}
            </select>
          </label>
          <label className="sc-wide">
            Work to do
            <input value={form.tasks} onChange={set("tasks")} placeholder="e.g. Medicines check, short walk, physio exercises" />
          </label>
          {clash ? (
            <p className="sc-clash" role="alert">
              {clash}
              <button type="button" className="sc-step" disabled={saving} onClick={(e) => void save(e, true)}>
                Book anyway
              </button>
            </p>
          ) : null}
          <div className="sc-form-actions">
            <button type="button" className="secondary" disabled={saving} onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button type="submit" disabled={saving}>
              {saving ? "Booking…" : "Book and tell the family"}
            </button>
          </div>
        </form>
      </OpsModal>

      {unfinished.length ? (
        <section className="card sc-unfinished">
          <h2>Needs finishing</h2>
          <ul>
            {unfinished.map((j) => (
              <li key={j.id}>
                <span>
                  <strong>{j.elder_name}</strong> · {j.title}{" "}
                  <small>
                    {j.scheduled_at ? `booked ${whenIST(j.scheduled_at)}` : ""}
                    {arrivalAt(j) ? `${j.scheduled_at ? " · " : ""}${j.status === "checked_in" ? "arrived" : "set off"} ${whenIST(arrivalAt(j) as string)}` : ""}
                    {" · "}
                    {isStaleCheckIn(j) ? staleLabel(j) : "not finished yet"}
                  </small>
                </span>
                {!edit ? null : j.status === "checked_in" ? (
                  <button type="button" className="sc-step is-go" onClick={() => openWork(j)}>
                    {j.kind === "assessment" ? (j.assessment_id ? "Continue assessment" : "Start assessment") : "Write report"}
                  </button>
                ) : (
                  <button type="button" className="sc-step is-go" onClick={() => void progress(j, "checked_in")}>
                    I&apos;ve arrived
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="vs-head">
        <div className="sc-tabs vs-tabs" role="tablist" aria-label="Visits">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              className={tab === t.id ? "is-on" : ""}
              onClick={() => setTab(t.id)}
            >
              {t.label}
              {counts[t.id] ? <span className={`vs-badge${t.id === "missed" ? " is-red" : ""}`}>{counts[t.id]}</span> : null}
            </button>
          ))}
        </div>
      </div>

      {tab !== "requests" ? (
        <>
          {sheet ? <div className="vs-scrim" onClick={() => setSheet(false)} aria-hidden="true" /> : null}
          <div className={`vs-filters${sheet ? " is-sheet" : ""}`} role={sheet ? "dialog" : undefined} aria-label="Filters">
            <p className="vs-sheet-title">Filter visits</p>
            <label className="vs-sel">
              <span>Type</span>
              <select value={kind} onChange={(e) => setKind(e.target.value as JobKind | "all")}>
                <option value="all">All types</option>
                <option value="visit">Care visits</option>
                <option value="assessment">Assessments</option>
                <option value="install">Installations</option>
              </select>
            </label>
            <label className="vs-sel">
              <span>Caregiver</span>
              <select value={cg} onChange={(e) => setCg(e.target.value)}>
                <option value="">All caregivers</option>
                {caregivers.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.first_name} {c.last_name}
                  </option>
                ))}
              </select>
            </label>
            {tab === "past" ? (
              <>
                <label className="vs-date">
                  <span>From</span>
                  <input type="date" value={from} max={to || undefined} onChange={(e) => setFrom(e.target.value)} />
                </label>
                <label className="vs-date">
                  <span>To</span>
                  <input type="date" value={to} min={from || undefined} onChange={(e) => setTo(e.target.value)} />
                </label>
              </>
            ) : null}
            {filterCount ? (
              <button
                type="button"
                className="sc-text vs-clear"
                onClick={() => {
                  setKind("all");
                  setCg("");
                  setFrom("");
                  setTo("");
                }}
              >
                Clear filters
              </button>
            ) : null}
            <button type="button" className="vs-sheet-done" onClick={() => setSheet(false)}>
              Done
            </button>
          </div>
        </>
      ) : null}

      {jobs === null ? (
        <p className="muted">Loading…</p>
      ) : tab === "requests" ? (
        requests.length === 0 ? (
          <div className="card sc-empty vs-empty">
            <p>No requests waiting. New family requests and due reassessments show up here.</p>
          </div>
        ) : (
          <ul className="vs-req">
            {requests.map((r) => (
              <li key={`${r.elder_id}-${r.id || r.label}`} className="card">
                <div className="vs-req-main">
                  <Link href={`/kushalaya/customers/${r.elder_id}`}>{r.elder_name}</Link>
                  <strong>{r.label}</strong>
                  {r.notes ? <small>{r.id ? `“${r.notes}”` : r.notes}</small> : null}
                </div>
                <dl className="vs-req-meta">
                  {r.id ? (
                    <div>
                      <dt>Asked</dt>
                      <dd>
                        {r.requested_by || "Family"}
                        {r.created_at ? ` · ${since(r.created_at)}` : ""}
                      </dd>
                    </div>
                  ) : (
                    <div>
                      <dt>From</dt>
                      <dd>Reassessment due</dd>
                    </div>
                  )}
                  {r.preferred_at ? (
                    <div>
                      <dt>Prefers</dt>
                      <dd>{istWhen(r.preferred_at)} IST</dd>
                    </div>
                  ) : null}
                </dl>
                {edit ? (
                <div className="sc-actions vs-req-actions">
                  <button type="button" className="sc-step is-go" onClick={() => scheduleRequest(r)}>
                    Schedule
                  </button>
                  {r.id ? (
                    <button type="button" className="sc-text is-danger" onClick={() => void declineRequest(r)}>
                      Decline
                    </button>
                  ) : null}
                </div>
                ) : null}
              </li>
            ))}
          </ul>
        )
      ) : groups.length === 0 ? (
        <div className="card sc-empty vs-empty">
          <p>{filterCount ? "No visits match these filters." : EMPTY_TEXT[tab]}</p>
        </div>
      ) : (
        groups.map(([day, rows]) => (
          <section key={day} className="sc-day">
            <h3>{dayLabel(day)}</h3>
            <ul>
              {rows.map((j) => (
                <li key={j.id} id={`job-${j.id}`} className={`sc-job vs-card is-${j.status}${focusJob === j.id ? " is-focus" : ""}`}>
                  <span className="sc-time">{j.scheduled_at ? istTime(j.scheduled_at) : "—"}</span>
                  <span className="sc-what">
                    <Link href={`/kushalaya/customers/${j.elder_id}`}>{j.elder_name}</Link>
                    <span>
                      <span className={`sc-kind is-${j.kind}`}>{JOB_KIND_LABEL[j.kind]}</span>
                      {j.tasks ? <small>{j.tasks}</small> : null}
                    </span>
                  </span>
                  {CLOSED.has(j.status) || !edit ? (
                    <span className="sc-cg-name">{j.caregiver_name || (j.status === "completed" ? "Logged by staff" : "Not assigned")}</span>
                  ) : (
                    <select value={j.caregiver_id ?? ""} onChange={(e) => void reassign(j, e.target.value)} aria-label="Caregiver">
                      <option value="">Not assigned</option>
                      {caregivers.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.first_name} {c.last_name}
                        </option>
                      ))}
                    </select>
                  )}
                  <span className="vs-stat">
                    <span className={`sc-status is-${j.status}`}>{tab === "missed" && j.status === "scheduled" ? "Never started" : isStaleCheckIn(j) ? staleLabel(j) : j.status_label}</span>
                    {j.status === "on_the_way" ? <OpsLiveBadge live={j.live} withStatus /> : null}
                  </span>
                  <span className="sc-actions">
                    {!edit ? (
                      <Directions home={j.elder_home} address={j.elder_address} location={j.location} name={j.elder_name} className="is-end" />
                    ) : tab === "missed" ? (
                      <button type="button" className="sc-step is-go" onClick={() => rebook(j)}>
                        Rebook
                      </button>
                    ) : !CLOSED.has(j.status) ? (
                      <>
                        {j.status === "scheduled" ? (
                          <button type="button" className="sc-step" onClick={() => void progress(j, "on_the_way")}>
                            On the way
                          </button>
                        ) : null}
                        {j.status === "checked_in" ? (
                          <button type="button" className="sc-step is-go" onClick={() => openWork(j)}>
                            {j.kind === "assessment" ? (j.assessment_id ? "Continue assessment" : "Start assessment") : "Write report"}
                          </button>
                        ) : (
                          <button type="button" className="sc-step is-go" onClick={() => void progress(j, "checked_in")}>
                            I&apos;ve arrived
                          </button>
                        )}
                        {j.status === "on_the_way" ? (
                          <button type="button" className="sc-step vs-live-btn" onClick={() => setMapJobId(j.id)}>
                            <span className="vs-sharing-dot" aria-hidden="true" /> Live tracking
                          </button>
                        ) : null}
                        <Directions home={j.elder_home} address={j.elder_address} location={j.location} name={j.elder_name} className="is-end" />
                        {MOVABLE.has(j.status) ? (
                          <>
                            <button type="button" className="sc-text" onClick={() => startMove(j)}>
                              Reschedule
                            </button>
                            <button type="button" className="sc-text is-danger" onClick={() => void cancel(j)}>
                              Cancel
                            </button>
                          </>
                        ) : null}
                      </>
                    ) : j.caregiver_note ? (
                      <small title={j.caregiver_note}>“{j.caregiver_note}”</small>
                    ) : null}
                  </span>
                  {moving?.id === j.id ? (
                    <span className="sc-resched">
                      New time (IST)
                      <input
                        type="date"
                        value={moving.date}
                        min={istInputValue().slice(0, 10)}
                        onChange={(e) => setMoving({ ...moving, date: e.target.value })}
                        aria-label="New date"
                      />
                      <input
                        type="time"
                        value={moving.time}
                        onChange={(e) => setMoving({ ...moving, time: e.target.value })}
                        aria-label="New time"
                      />
                      <button type="button" className="sc-step is-go" onClick={() => void reschedule(j)}>
                        Save
                      </button>
                      <button type="button" className="sc-text" onClick={() => setMoving(null)}>
                        Cancel
                      </button>
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          </section>
        ))
      )}

    </div>
  );
}
