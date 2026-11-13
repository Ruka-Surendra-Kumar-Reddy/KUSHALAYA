"use client";

/**
 * Operations: the sales pipeline as a board, one column per stage (scrolls sideways).
 * Date range (lead created) and search filter the cards; column counts follow them.
 * Dragging a card to a column opens the same move form as the popup. A lead opens in OpsModal: details, Call / WhatsApp / Start assessment, Move stage
 * (Lost needs a comment; Won needs plan + billing and lands in Pending approval →
 * Authorize), Add comment, and the history newest first.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { PageHeader } from "@/components/PageHeader";
import { api } from "@/lib/api";
import { can, isAdmin } from "@/lib/roles";
import { formatIST, istInputToISO, istInputValue } from "@/lib/ist";
import { matchLeadToClient } from "@/lib/lead-labels";
import { inr } from "@/lib/care-plan-catalog";
import {
  CYCLE_LABEL,
  DATE_RANGES,
  DEFAULT_RANGE,
  FUNNEL_LABEL,
  FUNNEL_STEPS,
  LEAD_SOURCES,
  PLAN_STATUS_LABEL,
  SALES_STAGES,
  STAGE_LABEL,
  addLeadComment,
  boardColumns,
  createLead,
  updateLead,
  downloadCsv,
  dropTarget,
  filterLeads,
  funnelStep,
  isRangeKey,
  isoDay,
  leadHistory,
  leadsCsv,
  listLeads,
  moveLead,
  moveProblem,
  rangeQuery,
  sourceLabel,
  type DateRangeKey,
  type FunnelStep,
  type Lead,
  type LeadEvent,
  type SalesStage,
  couponNote,
} from "@/lib/sales-pipeline";
import { PaymentDialog, PlanFields, emptyPick, pickCoupon, type PlanPick } from "@/components/ops/CustomerPlanParts";
import { NewAssessment } from "@/components/ops/NewAssessment";
import { bookAssessment, isClash, startAssessment } from "@/lib/jobs";
import { OpsModal } from "@/components/ops/OpsModal";
import { ChoiceWithOther } from "@/components/ChoiceWithOther";
import "@/components/ops/sales.css";
import "@/components/ops/sales-board.css";

type ClientRow = {
  id: number;
  first_name: string;
  last_name: string;
  phone?: string | null;
  emergency_contact_phone?: string | null;
  family_email?: string | null;
};

const errText = (e: unknown, fallback: string) => (e instanceof Error ? e.message : fallback);
const day = (iso: string | null | undefined) => (iso ? formatIST(iso, { dateOnly: true }) : "—");
const areaOf = (l: Lead) => [l.address, l.pincode].filter(Boolean).join(" · ");
const telHref = (p: string) => `tel:${p.replace(/[^+\d]/g, "")}`;
const OPEN_ORDER: SalesStage[] = ["NEW", "ASSESSMENT_SCHEDULED", "ASSESSMENT_DONE", "FOLLOW_UP_1", "FOLLOW_UP_2", "WON"];
function nextStage(s: SalesStage): SalesStage | null {
  const i = OPEN_ORDER.indexOf(s);
  return i >= 0 && i < OPEN_ORDER.length - 1 ? OPEN_ORDER[i + 1] : null;
}
function assessmentText(l: Lead): string {
  if (l.assessment?.status === "completed") return "Done";
  if (l.assessment) return "Draft open";
  if (l.stage === "ASSESSMENT_DONE") return "Done";
  if (l.stage === "ASSESSMENT_SCHEDULED") return "Booked";
  return "Not started";
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt>{label}:</dt>
      <dd>{children}</dd>
    </div>
  );
}

/** Move form shown inside the lead popup (no second dialog). */
function MoveForm({
  lead,
  to,
  clients,
  onCancel,
  onDone,
}: {
  lead: Lead;
  to: SalesStage;
  clients: ClientRow[];
  onCancel: () => void;
  onDone: (msg: string) => void;
}) {
  const [comment, setComment] = useState("");
  const [pick, setPick] = useState<PlanPick>(emptyPick);
  const existing = to === "WON" && !lead.converted_elder_id ? matchLeadToClient(lead, clients) : null;
  const [linkExisting, setLinkExisting] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    const problem = moveProblem(to, comment, pick);
    if (problem) return setError(problem);
    setBusy(true);
    setError("");
    try {
      const won = to === "WON";
      const out = await moveLead(lead.id, {
        to,
        comment: comment.trim() || null,
        ...(won && pick.billing_cycle
          ? {
              plan_id: pick.plan_id,
              billing_cycle: pick.billing_cycle,
              start_date: pick.start_date,
              coupon_code: pickCoupon(pick),
              elder_id: existing && linkExisting ? existing.id : null,
            }
          : {}),
      });
      onDone(
        out.customer_plan
          ? `${lead.name} won: ${out.customer_plan.plan_name} (${inr(out.customer_plan.amount_paise)}) is waiting for approval.`
          : `${lead.name} moved to ${STAGE_LABEL[to]}.`,
      );
    } catch (err) {
      setError(errText(err, "Could not move the lead"));
      setBusy(false);
    }
  }

  return (
    <form className="sb-move-form sp-dialog" onSubmit={submit}>
      <p className="sb-move-title">
        {STAGE_LABEL[lead.stage]} → <strong>{STAGE_LABEL[to]}</strong>
      </p>
      {to === "WON" ? (
        <>
          <PlanFields value={pick} onChange={setPick} />
          {existing ? (
            <label className="sp-check">
              <input type="checkbox" checked={linkExisting} onChange={(e) => setLinkExisting(e.target.checked)} />
              Same person as client {`${existing.first_name} ${existing.last_name}`.trim()}: add the plan there
            </label>
          ) : null}
          <p className="muted sp-dialog-lead">The plan waits in Pending approval until an admin authorizes it.</p>
        </>
      ) : null}
      <label>
        {to === "LOST" ? "Why was it lost? (required)" : "Comment (optional)"}
        <textarea rows={3} value={comment} maxLength={2000} required={to === "LOST"} onChange={(e) => setComment(e.target.value)} />
      </label>
      {error ? (
        <p className="error-text" role="alert">
          {error}
        </p>
      ) : null}
      <div className="sb-btns">
        <button type="button" className="secondary" disabled={busy} onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="primary" disabled={busy}>
          {busy ? "Saving…" : to === "WON" ? "Mark won" : to === "LOST" ? "Mark lost" : "Move"}
        </button>
      </div>
    </form>
  );
}

type Manager = { id: number; first_name: string; last_name: string };

/** A new lead asks for a visit later: book the assessment (date, time, care manager) → "Assessment booked". */
function BookForm({ lead, onDone }: { lead: Lead; onDone: (msg: string) => void }) {
  const [date, setDate] = useState(() => istInputValue(86400000).slice(0, 10));
  const [time, setTime] = useState("10:00");
  const [managers, setManagers] = useState<Manager[]>([]);
  const [manager, setManager] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [clash, setClash] = useState(false);
  useEffect(() => {
    api<Manager[]>("/api/v1/team/managers").then(setManagers).catch(() => undefined);
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!date || !time) return setError("Pick a date and a time");
    setBusy(true);
    setError("");
    try {
      const at = istInputToISO(`${date}T${time}`);
      await bookAssessment({ lead_id: lead.id, scheduled_at: at, assignee_user_id: manager ? Number(manager) : null, force: clash });
      onDone(`Assessment booked for ${lead.name}: ${formatIST(at)}.`);
    } catch (err) {
      setClash(isClash(err));
      setError(errText(err, "Could not book the assessment"));
      setBusy(false);
    }
  }

  return (
    <form className="sb-book" onSubmit={submit}>
      <label>
        Date
        <input type="date" value={date} min={istInputValue().slice(0, 10)} required onChange={(e) => setDate(e.target.value)} />
      </label>
      <label>
        Time (IST)
        <input type="time" value={time} required onChange={(e) => setTime(e.target.value)} />
      </label>
      <label className="sb-book-wide">
        Care manager (optional)
        <select value={manager} onChange={(e) => setManager(e.target.value)}>
          <option value="">Decide later</option>
          {managers.map((m) => (
            <option key={m.id} value={m.id}>
              {`${m.first_name} ${m.last_name}`.trim()}
            </option>
          ))}
        </select>
      </label>
      {error ? (
        <p className="error-text sb-book-wide" role="alert">
          {error}
        </p>
      ) : null}
      <div className="sb-btns sb-book-wide">
        <button type="submit" className="primary" disabled={busy}>
          {busy ? "Booking…" : clash ? "Book anyway" : "Book assessment"}
        </button>
      </div>
    </form>
  );
}

function LeadDetail({
  lead,
  clients,
  onClose,
  onChanged,
  onAuthorize,
  initialMove = null,
}: {
  lead: Lead;
  clients: ClientRow[];
  onClose: () => void;
  onChanged: (msg: string) => void;
  onAuthorize: () => void;
  initialMove?: SalesStage | null;
}) {
  const edit = can("edit");
  const admin = isAdmin();
  const [events, setEvents] = useState<LeadEvent[] | null>(null);
  const [error, setError] = useState("");
  const [moveTo, setMoveTo] = useState<SalesStage | null>(initialMove);
  const [editing, setEditing] = useState(false);
  // Move stage: one drop-down (next stage pre-selected) + Move → the same confirm form.
  const [pick, setPick] = useState<SalesStage | "">(nextStage(lead.stage) ?? "");
  const router = useRouter();
  const [opening, setOpening] = useState(false);
  async function continueAssessment() {
    setOpening(true);
    try {
      const res = await startAssessment({ lead_id: lead.id }, false);
      router.push(`/caregiver/assess/${res.job_id}?from=leads`);
    } catch {
      setOpening(false);
    }
  }
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const loadHistory = useCallback(() => {
    leadHistory(lead.id)
      .then(setEvents)
      .catch((e) => setError(errText(e, "Could not load the history")));
  }, [lead.id]);
  useEffect(loadHistory, [loadHistory, lead.stage]);

  async function addNote(e: FormEvent) {
    e.preventDefault();
    if (!note.trim()) return;
    setSaving(true);
    setError("");
    try {
      await addLeadComment(lead.id, note.trim());
      setNote("");
      loadHistory();
      onChanged("");
    } catch (err) {
      setError(errText(err, "Could not save the comment"));
    } finally {
      setSaving(false);
    }
  }

  const open = lead.stage !== "WON" && lead.stage !== "LOST";
  const next = nextStage(lead.stage);
  const step = funnelStep(lead);
  return (
    <OpsModal open title={lead.name || "Lead"} onClose={onClose}>
      <div className="sb-detail">
        {editing ? (
          <EditLead
            lead={lead}
            onCancel={() => setEditing(false)}
            onSaved={() => {
              setEditing(false);
              onChanged("Details saved");
            }}
          />
        ) : edit && lead.stage !== "WON" ? (
          <button type="button" className="secondary sb-edit-btn" style={{ justifySelf: "start", minHeight: 40 }} onClick={() => setEditing(true)}>
            Edit details
          </button>
        ) : null}
        <dl className="sb-facts">
          <Fact label="Name">{lead.name || "—"}</Fact>
          <Fact label="Phone">{lead.phone ? <a href={telHref(lead.phone)}>{lead.phone}</a> : "—"}</Fact>
          <Fact label="Email">{lead.email ? <a href={`mailto:${lead.email}`}>{lead.email}</a> : "—"}</Fact>
          <Fact label="Area / address">{areaOf(lead) || "—"}</Fact>
          <Fact label="Source">{sourceLabel(lead.source)}</Fact>
          <Fact label="Stage">
            <b className={`sb-pill is-${step.toLowerCase()}`}>{FUNNEL_LABEL[step]}</b>
          </Fact>
          <Fact label="Created">{day(lead.created_at)}</Fact>
          <Fact label="Assessment">
            {assessmentText(lead)}
            {lead.assessment?.status === "completed" ? (
              <>
                {" · "}
                <Link className="ks-link" href={`/kushalaya/assessments/${encodeURIComponent(lead.assessment.assessment_id)}/report`}>
                  Report
                </Link>
              </>
            ) : null}
          </Fact>
          {lead.plan ? (
            <Fact label="Plan">
              {lead.plan.plan_name} · {CYCLE_LABEL[lead.plan.billing_cycle]} · {inr(lead.plan.amount_paise)}
              {couponNote(lead.plan)} ·{" "}
              {PLAN_STATUS_LABEL[lead.plan.status]}
            </Fact>
          ) : null}
          {lead.converted_elder_id ? (
            <Fact label="Client">
              <Link className="ks-link" href={`/kushalaya/customers/${lead.converted_elder_id}?tab=plan`}>
                {lead.customer_id}
              </Link>
            </Fact>
          ) : null}
        </dl>

        <div className="sb-btns sb-actions">
          {/* One assessment action, by state: report when done, continue a draft, else start. */}
          {lead.assessment?.status === "completed" ? (
            <Link
              className="primary sb-act-main"
              href={`/kushalaya/assessments/${encodeURIComponent(lead.assessment.assessment_id)}/report`}
            >
              View report
            </Link>
          ) : edit && open && lead.assessment ? (
            <button type="button" className="primary" disabled={opening} onClick={() => void continueAssessment()}>
              {opening ? "Opening…" : "Continue assessment"}
            </button>
          ) : edit && open ? (
            <NewAssessment
              who={{ lead_id: lead.id }}
              name={lead.name}
              from="leads"
              className={lead.stage === "NEW" ? "secondary" : "primary"}
              label={lead.stage === "NEW" ? "Start assessment now" : "Start assessment"}
              draft={null}
            />
          ) : null}
          {lead.plan?.status === "pending_approval" ? (
            admin ? (
              <button type="button" className="primary" onClick={onAuthorize}>
                Authorize plan
              </button>
            ) : (
              <span className="muted">Waiting for an admin to authorize</span>
            )
          ) : null}
        </div>

        {edit && lead.stage === "NEW" && !moveTo ? (
          <section className="sb-block" aria-label="Book assessment">
            <h3>Book assessment</h3>
            <BookForm lead={lead} onDone={onChanged} />
            <button type="button" className="secondary sb-lost" onClick={() => setMoveTo("LOST")}>
              Mark lost
            </button>
          </section>
        ) : edit && lead.stage !== "WON" ? (
          <section className="sb-block" aria-label="Move stage">
            <h3>Move stage</h3>
            {moveTo ? (
              <MoveForm
                key={moveTo}
                lead={lead}
                to={moveTo}
                clients={clients}
                onCancel={() => setMoveTo(null)}
                onDone={(msg) => {
                  setMoveTo(null);
                  onChanged(msg);
                }}
              />
            ) : (
              <div className="sb-move">
                <select value={pick} onChange={(e) => setPick(e.target.value as SalesStage)} aria-label="Move to stage">
                  <option value="">Choose a stage…</option>
                  {SALES_STAGES.filter((st) => st !== lead.stage).map((st) => (
                    <option key={st} value={st}>
                      {st === "LOST" ? "Lost" : STAGE_LABEL[st]}
                      {st === next ? " (next)" : ""}
                    </option>
                  ))}
                </select>
                <button type="button" className="primary" disabled={!pick} onClick={() => pick && setMoveTo(pick)}>
                  Move
                </button>
              </div>
            )}
          </section>
        ) : null}

        <section className="sb-block" aria-label="Comments and history">
          <h3>History</h3>
          {edit ? (
            <form className="sb-note" onSubmit={addNote}>
              <textarea
                rows={2}
                value={note}
                maxLength={2000}
                placeholder="Add a comment"
                aria-label="Add a comment"
                onChange={(e) => setNote(e.target.value)}
              />
              <button type="submit" className="secondary" disabled={saving || !note.trim()}>
                {saving ? "Saving…" : "Add comment"}
              </button>
            </form>
          ) : null}
          {error ? <p className="error-text">{error}</p> : null}
          {events === null ? (
            <p className="muted">Loading…</p>
          ) : events.length === 0 ? (
            <p className="muted">No history yet.</p>
          ) : (
            <ol className="sp-history">
              {events.map((ev) => (
                <li key={ev.id}>
                  <strong>{ev.to_label ? `${ev.from_label ?? "—"} → ${ev.to_label}` : ev.body}</strong>
                  {ev.comment ? <p>{ev.comment}</p> : null}
                  <span className="muted">
                    {ev.by || "System"} · {ev.at ? formatIST(ev.at) : ""}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </OpsModal>
  );
}

function EditLead({ lead, onCancel, onSaved }: { lead: Lead; onCancel: () => void; onSaved: () => void }) {
  const [name, setName] = useState(lead.name || "");
  const [phone, setPhone] = useState(lead.phone || "");
  const [email, setEmail] = useState(lead.email || "");
  const [address, setAddress] = useState(lead.address || "");
  const [pincode, setPincode] = useState(lead.pincode || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return setError("Add a name.");
    if (!phone.trim() && !email.trim()) return setError("Add a mobile number or an email.");
    setBusy(true);
    setError("");
    try {
      await updateLead(lead.id, {
        name: name.trim(),
        phone: phone.trim() || null,
        email: email.trim() || null,
        address: address.trim() || null,
        pincode: pincode.trim() || null,
      });
      onSaved();
    } catch (err) {
      setError(errText(err, "Could not save"));
      setBusy(false);
    }
  }

  return (
    <form className="sb-edit" style={{ display: "grid", gap: "0.75rem", marginBottom: "1rem" }} onSubmit={submit}>
      <label>
        Name
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label>
        Mobile
        <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+91" />
      </label>
      <label>
        Email
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      </label>
      <label>
        Address
        <textarea rows={2} value={address} maxLength={500} onChange={(e) => setAddress(e.target.value)} placeholder="Flat, street, area, city" />
      </label>
      <label>
        PIN code
        <input inputMode="numeric" value={pincode} maxLength={10} onChange={(e) => setPincode(e.target.value)} />
      </label>
      {error ? (
        <p className="error-text" role="alert">
          {error}
        </p>
      ) : null}
      <div className="sb-btns">
        <button type="button" className="secondary" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
        <button type="submit" className="primary" disabled={busy}>
          {busy ? "Saving…" : "Save details"}
        </button>
      </div>
    </form>
  );
}

function AddLead({ onClose, onSaved }: { onClose: () => void; onSaved: (name: string) => void }) {
  const [name, setName] = useState("");
  const [source, setSource] = useState<string>(LEAD_SOURCES[0]);
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [address, setAddress] = useState("");
  const [pincode, setPincode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    const full = name.trim().replace(/\s+/g, " ");
    if (!full) return setError("Add a name.");
    if (!phone.trim() && !email.trim()) return setError("Add a mobile number or an email.");
    setBusy(true);
    setError("");
    try {
      await createLead({
        name: full,
        source: source.trim() || "Other",
        phone: phone.trim() || null,
        email: email.trim() || null,
        address: address.trim() || null,
        pincode: pincode.trim() || null,
      });
      onSaved(full);
    } catch (err) {
      setError(errText(err, "Could not save"));
      setBusy(false);
    }
  }

  return (
    <OpsModal open title="Add lead" onClose={onClose}>
      <form style={{ display: "grid", gap: "0.75rem" }} onSubmit={submit}>
        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} autoFocus required />
        </label>
        <label>
          Source
          <ChoiceWithOther
            options={LEAD_SOURCES.map((x) => ({ value: x, label: x }))}
            value={source}
            onChange={setSource}
            otherValue="Other"
            placeholder={null}
            otherPlaceholder="Where did the lead come from?"
            ariaLabel="Source"
          />
        </label>
        <label>
          Mobile
          <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+91" />
        </label>
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          Address
          <textarea rows={2} value={address} maxLength={500} onChange={(e) => setAddress(e.target.value)} placeholder="Flat, street, area, city" />
        </label>
        <label>
          PIN code
          <input inputMode="numeric" value={pincode} maxLength={10} onChange={(e) => setPincode(e.target.value)} />
        </label>
        {error ? (
          <p className="error-text" role="alert">
            {error}
          </p>
        ) : null}
        <div className="sb-btns">
          <button type="button" className="secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="primary" disabled={busy}>
            {busy ? "Saving…" : "Save lead"}
          </button>
        </div>
      </form>
    </OpsModal>
  );
}

function LeadCard({ lead, draggable, onOpen }: { lead: Lead; draggable: boolean; onOpen: () => void }) {
  const area = areaOf(lead);
  const hint =
    lead.assessment?.status === "completed" ? "Assessment done" : lead.assessment ? "Draft" : lead.plan?.status === "pending_approval" ? "Awaiting approval" : "";
  return (
    <button
      type="button"
      className="sb-card"
      draggable={draggable}
      onDragStart={(e) => {
        e.dataTransfer.setData("text/plain", String(lead.id));
        e.dataTransfer.effectAllowed = "move";
      }}
      onClick={onOpen}
    >
      <strong>{lead.name || "No name"}</strong>
      <span>{lead.phone || lead.email || "No contact"}</span>
      {area ? <span className="sb-card-area">{area}</span> : null}
      <span className="sb-card-meta">
        <span>{sourceLabel(lead.source)}</span>
        <span>{day(lead.created_at)}</span>
      </span>
      {hint ? <b className={`sb-hint${hint === "Draft" ? " is-draft" : ""}`}>{hint}</b> : null}
    </button>
  );
}

/** Reads / writes ?range=&from=&to= so a refresh keeps the view; ?stage= scrolls to that column. */
function setUrl(params: Record<string, string>) {
  const url = new URL(window.location.href);
  for (const [k, v] of Object.entries(params)) {
    if (v) url.searchParams.set(k, v);
    else url.searchParams.delete(k);
  }
  window.history.replaceState(window.history.state, "", url.toString());
}

export function SalesBoard({ flash, onMessage }: { flash?: ReactNode; onMessage: (m: string) => void }) {
  const edit = can("edit");
  const [leads, setLeads] = useState<Lead[] | null>(null);
  const [clients, setClients] = useState<ClientRow[]>([]);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [stage, setStageState] = useState("");
  const [dropOn, setDropOn] = useState<string>("");
  const [initialMove, setInitialMove] = useState<SalesStage | null>(null);
  const [range, setRangeState] = useState<DateRangeKey | null>(null);
  const [custom, setCustom] = useState({ from: "", to: "" });
  const [openId, setOpenId] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);
  const [authorizing, setAuthorizing] = useState<Lead | null>(null);

  useEffect(() => {
    const sp = new URLSearchParams(window.location.search);
    const st = sp.get("stage") || "";
    if ((FUNNEL_STEPS as readonly string[]).includes(st)) setStageState(st);
    const r = sp.get("range");
    // A Dashboard tile (?stage=NEW) counts every open lead, so it opens on All time.
    setRangeState(isRangeKey(r) ? r : st ? "all" : DEFAULT_RANGE);
    setCustom({ from: sp.get("from") || "", to: sp.get("to") || "" });
  }, []);
  const setRange = (r: DateRangeKey) => {
    setRangeState(r);
    setUrl({ range: r, ...(r === "custom" ? {} : { from: "", to: "" }) });
  };
  const setCustomDay = (k: "from" | "to", v: string) => {
    setCustom((c) => ({ ...c, [k]: v }));
    setUrl({ [k]: v });
  };

  const load = useCallback(() => {
    if (!range) return;
    listLeads(rangeQuery(range, new Date(), custom))
      .then((rows) => {
        setLeads(rows);
        setError("");
      })
      .catch((e) => setError(errText(e, "Could not load leads")));
  }, [range, custom]);
  useEffect(load, [load]);
  useEffect(() => {
    api<ClientRow[]>("/api/v1/elders").then(setClients).catch(() => setClients([]));
  }, []);

  // Column counts follow the date range and the search, so a count always equals its cards.
  const shown = useMemo(() => filterLeads(leads ?? [], query), [leads, query]);
  const columns = useMemo(() => boardColumns(shown), [shown]);
  useEffect(() => {
    if (!stage || leads === null) return;
    document.getElementById(`sb-col-${stage}`)?.scrollIntoView({ inline: "start", block: "nearest" });
  }, [stage, leads]);
  const openCard = (id: number, move: SalesStage | null = null) => {
    setInitialMove(move);
    setOpenId(id);
  };
  const drop = (step: FunnelStep, id: number) => {
    setDropOn("");
    const l = shown.find((x) => x.id === id);
    const to = l && edit ? dropTarget(l, step) : null;
    if (l && to) openCard(l.id, to);
  };
  const openLead = (leads ?? []).find((l) => l.id === openId) || null;
  const changed = (msg: string) => {
    if (msg) onMessage(msg);
    load();
  };

  return (
    <>
      <div className="ks-head-row">
        <PageHeader title="Operations" subtitle="Every lead, first call to won" />
        <div className="ks-head-actions">
          {edit ? (
            <button type="button" onClick={() => setAdding(true)} aria-label="Add lead" title="Add lead">
              <span className="ks-ha-icon" aria-hidden="true">+</span>
              <span className="ks-ha-label">+ Add lead</span>
            </button>
          ) : null}
          <button
            type="button"
            className="secondary"
            disabled={!shown.length}
            onClick={() => downloadCsv(`kushalaya-leads-${isoDay(new Date())}.csv`, leadsCsv(shown))}
            aria-label="Export CSV"
            title="Export CSV"
          >
            <span className="ks-ha-icon" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 3v12M7 10l5 5 5-5M4 21h16" />
              </svg>
            </span>
            <span className="ks-ha-label">Export</span>
          </button>
        </div>
      </div>
      {flash}
      <section className="sb card" aria-label="Leads">
        <div className="sb-top">
          <input
            type="search"
            className="sb-search"
            aria-label="Search name, phone, area or source"
            placeholder="Search name, phone, area, source"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="sb-range">
            <select aria-label="Date range (lead created)" value={range ?? DEFAULT_RANGE} onChange={(e) => setRange(e.target.value as DateRangeKey)}>
              {DATE_RANGES.map(([k, label]) => (
                <option key={k} value={k}>
                  {label}
                </option>
              ))}
            </select>
            {range === "custom" ? (
              <>
                <input type="date" aria-label="From" value={custom.from} max={custom.to || undefined} onChange={(e) => setCustomDay("from", e.target.value)} />
                <span aria-hidden="true">–</span>
                <input type="date" aria-label="To" value={custom.to} min={custom.from || undefined} onChange={(e) => setCustomDay("to", e.target.value)} />
              </>
            ) : null}
          </div>
        </div>

        {error ? <p className="error-text">{error}</p> : null}
        {leads === null && !error ? <p className="muted">Loading…</p> : null}
        {leads !== null && shown.length === 0 ? <p className="sb-empty">{query ? "No match." : "No leads in this period."}</p> : null}
        {leads !== null ? (
          <div className="sb-board" aria-label="Pipeline board">
            {columns.map(({ step, leads: cards }) => (
              <section
                key={step}
                id={`sb-col-${step}`}
                className={`sb-col is-${step.toLowerCase()}${dropOn === step ? " is-drop" : ""}${stage === step ? " is-focus" : ""}`}
                aria-label={`${FUNNEL_LABEL[step]}: ${cards.length}`}
                onDragOver={(e) => {
                  if (!edit) return;
                  e.preventDefault();
                  if (dropOn !== step) setDropOn(step);
                }}
                onDragLeave={(e) => {
                  if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDropOn("");
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  drop(step, Number(e.dataTransfer.getData("text/plain")));
                }}
              >
                <h3 className="sb-col-head">
                  <span>{FUNNEL_LABEL[step]}</span>
                  <b>{cards.length}</b>
                </h3>
                <div className="sb-col-body">
                  {cards.map((l) => (
                    <LeadCard key={l.id} lead={l} draggable={edit && l.stage !== "WON"} onOpen={() => openCard(l.id)} />
                  ))}
                  {cards.length === 0 ? <p className="sb-col-empty">No leads</p> : null}
                </div>
              </section>
            ))}
          </div>
        ) : null}
      </section>

      {openLead ? (
        <LeadDetail
          key={`${openLead.id}-${initialMove ?? ""}`}
          lead={openLead}
          initialMove={initialMove}
          clients={clients}
          onClose={() => {
            setOpenId(null);
            setInitialMove(null);
          }}
          onChanged={changed}
          onAuthorize={() => {
            setOpenId(null);
            setAuthorizing(openLead);
          }}
        />
      ) : null}
      {authorizing?.plan ? (
        <PaymentDialog
          plan={authorizing.plan}
          name={authorizing.name}
          mode="authorize"
          onClose={() => setAuthorizing(null)}
          onDone={(p) => {
            setAuthorizing(null);
            changed(`${authorizing.name}: ${p.plan_name} is now active.`);
          }}
        />
      ) : null}
      {adding ? (
        <AddLead
          onClose={() => setAdding(false)}
          onSaved={(n) => {
            setAdding(false);
            changed(`${n} added to New.`);
          }}
        />
      ) : null}
    </>
  );
}
