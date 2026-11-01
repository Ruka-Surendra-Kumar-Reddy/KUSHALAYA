"use client";

import { useCallback, useEffect, useState } from "react";
import "@/components/ops/clients.css";
import { useRouter } from "next/navigation";
import { getStoredAuth } from "@/lib/api";
import { canAccessSettings, roleLabel } from "@/lib/auth";
import { formatIST } from "@/lib/ist";
import { isAdmin } from "@/lib/roles";
import { BackLink } from "@/components/ops/PageActions";
import {
  fetchActivitySession,
  fetchActivitySessions,
  type ActorType,
  type SessionDetail,
  type SessionEvent,
  type SessionSummary,
} from "@/lib/activity";
import { Flash } from "@/components/Flash";

/** One date format across ops: "Wed 7 Oct, 2:45 pm IST" (lib/ist.ts). */
function formatWhen(iso: string): string {
  return formatIST(iso) || iso;
}

/** Plain role words: "Admin", not "Tenant admin"; "Staff", not "STAFF". */
function plainRole(role: string): string {
  const r = (role || "").toUpperCase();
  if (r === "TENANT_ADMIN") return "Admin";
  if (r === "SYSTEM_ADMIN") return "Super admin";
  const label = roleLabel(role || "");
  if (label !== role) return label;
  const words = (role || "").toLowerCase().replace(/_/g, " ").trim();
  return words ? words[0]!.toUpperCase() + words.slice(1) : "";
}

function durationLabel(start: string, end: string | null, lastSeen: string): string {
  const a = new Date(start).getTime();
  const b = new Date(end || lastSeen).getTime();
  if (!Number.isFinite(a) || !Number.isFinite(b) || b < a) return "—";
  const mins = Math.round((b - a) / 60000);
  if (mins < 1) return "<1 min";
  if (mins < 60) return `${mins} min`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

function actorBadge(actor: string): string {
  if (actor === "family") return "Family";
  if (actor === "assessor") return "Caregiver app";
  if (actor === "system") return "System";
  return "Staff";
}

function EventMetaDetails({ meta }: { meta: Record<string, unknown> | null }) {
  if (!meta || Object.keys(meta).length === 0) return null;
  return (
    <details className="session-event-meta-details" style={{ marginTop: "0.35rem" }}>
      <summary className="muted" style={{ cursor: "pointer", fontSize: "0.85rem" }}>
        Technical details
      </summary>
      <pre
        style={{
          margin: "0.35rem 0 0",
          padding: "0.5rem",
          fontSize: "0.75rem",
          overflow: "auto",
          maxHeight: "14rem",
          background: "var(--surface-muted, #f6f6f6)",
        }}
      >
        {JSON.stringify(meta, null, 2)}
      </pre>
    </details>
  );
}

function SessionAccordion({
  summary,
}: {
  summary: SessionSummary;
}) {
  const [open, setOpen] = useState(false);
  // Only admins see IPs, browser strings and the technical request log.
  const admin = isAdmin();
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (!next || detail) return;
    setLoading(true);
    setError("");
    try {
      setDetail(await fetchActivitySession(summary.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const active = !summary.ended_at;

  return (
    <div className={`ai-ops-accordion session-activity-accordion is-${summary.actor_type}`}>
      <button
        type="button"
        className="ai-ops-accordion-toggle"
        aria-expanded={open}
        onClick={toggle}
      >
        <span className="ai-ops-accordion-title">
          <span className={`ks-tag is-${summary.actor_type}`}>{actorBadge(summary.actor_type)}</span>
          <strong>{summary.user_name || summary.user_email}</strong>
          <em className="ai-ops-accordion-hint">{summary.user_email}</em>
          <em className="ai-ops-accordion-hint">{plainRole(summary.user_role)}</em>
        </span>
        <span className="ai-ops-accordion-hint">
          {active ? "Active · " : ""}
          {summary.event_count} action{summary.event_count === 1 ? "" : "s"} ·{" "}
          {durationLabel(summary.started_at, summary.ended_at, summary.last_seen_at)} ·{" "}
          {formatWhen(summary.started_at)}
          <span aria-hidden> {open ? "▴" : "▾"}</span>
        </span>
        {summary.recent_actions?.length ? (
          <span className="session-recent">{summary.recent_actions.join(" · ")}</span>
        ) : null}
      </button>
      {open ? (
        <div className="ai-ops-accordion-body">
          {loading ? <p className="muted">Loading details…</p> : null}
          {error ? <p className="error">{error}</p> : null}
          {detail ? (
            <>
              <p className="muted session-meta">
                Started {formatWhen(detail.started_at)}
                {" · "}
                Last seen {formatWhen(detail.last_seen_at)}
                {detail.ended_at ? ` · Ended ${formatWhen(detail.ended_at)}` : " · Still open"}
                {admin && detail.ip_address ? ` · IP ${detail.ip_address}` : ""}
              </p>
              {detail.events.length === 0 ? (
                <p className="muted">Nothing recorded in this session yet.</p>
              ) : (
                <>
                  {(() => {
                    const actions = detail.events.filter((e) => e.event_kind === "action");
                    const aiResults = detail.events.filter((e) => e.event_kind === "ai_result");
                    const systemEvents = detail.events.filter((e) => e.event_kind === "system");
                    const apiCalls = detail.events.filter(
                      (e) => !["action", "ai_result", "system"].includes(e.event_kind),
                    );

                    function EventList({
                      title,
                      empty,
                      items,
                    }: {
                      title: string;
                      empty: string;
                      items: SessionEvent[];
                    }) {
                      return (
                        <>
                          <h3 className="session-section-title">{title}</h3>
                          {items.length === 0 ? (
                            <p className="muted">{empty}</p>
                          ) : (
                            <ul className="session-action-list">
                              {items.map((ev) => (
                                <li key={ev.id} className={`session-event-kind-${ev.event_kind}`}>
                                  <time>{formatWhen(ev.occurred_at)}</time>
                                  <div>
                                    <strong>{ev.action}</strong>
                                    {ev.summary ? (
                                      <div className="muted">{ev.summary}</div>
                                    ) : null}
                                    {ev.entity_type && ev.entity_id ? (
                                      <div className="muted">
                                        {ev.entity_type} {ev.entity_id}
                                      </div>
                                    ) : null}
                                    {admin ? <EventMetaDetails meta={ev.meta} /> : null}
                                  </div>
                                </li>
                              ))}
                            </ul>
                          )}
                        </>
                      );
                    }

                    return (
                      <>
                        <EventList
                          title="User actions"
                          empty="No user actions yet (upload, save, send to AI, etc.)."
                          items={actions}
                        />
                        <EventList
                          title="AI returns"
                          empty="No AI responses yet (vision / visualization results)."
                          items={aiResults}
                        />
                        <EventList
                          title="System"
                          empty="No system events in this session (IoT SOS, background jobs, …)."
                          items={systemEvents}
                        />
                        {admin && apiCalls.length > 0 ? (
                          <details className="session-api-details">
                            <summary>
                              Technical log ({apiCalls.length})
                            </summary>
                            <table className="table session-events-table">
                              <thead>
                                <tr>
                                  <th>When</th>
                                  <th>What</th>
                                  <th>Address</th>
                                  <th>Result</th>
                                  <th>Time taken (ms)</th>
                                </tr>
                              </thead>
                              <tbody>
                                {apiCalls.map((ev) => (
                                  <tr key={ev.id}>
                                    <td>{formatWhen(ev.occurred_at)}</td>
                                    <td>{ev.action}</td>
                                    <td>
                                      {ev.method && ev.path ? (
                                        <code>
                                          {ev.method} {ev.path}
                                        </code>
                                      ) : (
                                        "—"
                                      )}
                                    </td>
                                    <td>{ev.status_code ?? "—"}</td>
                                    <td>
                                      {ev.duration_ms != null
                                        ? Math.round(ev.duration_ms)
                                        : "—"}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </details>
                        ) : null}
                      </>
                    );
                  })()}
                </>
              )}
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export default function ActivityPage() {
  const router = useRouter();
  const auth = getStoredAuth();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [actorType, setActorType] = useState<ActorType | "">("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const rows = await fetchActivitySessions({
        actor_type: actorType,
        limit: 50,
      });
      setSessions(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [actorType]);

  useEffect(() => {
    if (!auth) {
      router.replace("/login");
      return;
    }
    if (!canAccessSettings(auth.role)) {
      router.replace("/unauthorized");
      return;
    }
    load();
  }, [auth?.email, auth?.role, auth?.tenant_id, load, router]);

  return (
    <div className="ks-frame">
      <header className="ks-head">
        <BackLink href="/settings" label="Settings" />
        <h1>Activity log</h1>
        <p className="muted">Who did what and when — staff, caregivers, families and wearables.</p>
      </header>
      <Flash error={error} onClear={() => setError("")} />

      <div className="card session-activity-filters">
        <label>
          Who
          <select
            value={actorType}
            onChange={(e) => setActorType(e.target.value as ActorType | "")}
          >
            <option value="">All</option>
            <option value="assessor">Caregiver app</option>
            <option value="family">Family</option>
            <option value="staff">Staff</option>
            <option value="system">System</option>
          </select>
        </label>
        <button type="button" className="ks-btn-secondary" onClick={load} disabled={loading}>
          Refresh
        </button>
      </div>

      <div className="card">
        {loading && sessions.length === 0 ? (
          <p className="muted">Loading sessions…</p>
        ) : sessions.length === 0 ? (
          <p className="muted">No activity yet. It appears here once people sign in and use the portal.</p>
        ) : (
          <div className="session-activity-list">
            {sessions.map((s) => (
              <SessionAccordion key={s.id} summary={s} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
