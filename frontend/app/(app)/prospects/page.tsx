"use client";

import { LeadDetails, LeadFunnel } from "@/components/ops/LeadFunnel";
import { dateTimeIST } from "@/lib/ist";
import Link from "next/link";
import { FormEvent, Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, getStoredAuth } from "@/lib/api";
import { canManageUsers, canWrite } from "@/lib/auth";
import { useBranding } from "@/components/BrandingProvider";
import { verticalHasFeature } from "@/lib/features";
import { Flash } from "@/components/Flash";
import { PageHeader } from "@/components/PageHeader";
import { useTranslation } from "@/lib/i18n/context";
import {
  demandEntityLabel,
  demandEntityPluralLabel,
  supplyEntityLabel,
  supplyEntityPluralLabel,
} from "@/lib/terminology";
import { prospectsPageSubtitle } from "@/lib/verticalUx";
import {
  addCaregiverActivity,
  addElderActivity,
  convertCaregiverProspect,
  convertElderProspect,
  createCaregiverProspect,
  createElderProspect,
  fetchAssignableOwners,
  fetchPipelineStages,
  formatFollowUp,
  listCaregiverActivities,
  listCaregiverProspects,
  listElderActivities,
  listElderProspects,
  permanentlyDeleteElder,
  permanentlyDeleteElderProspect,
  unlinkElderProspect,
  stageLabel,
  updateCaregiverProspect,
  updateElderProspect,
  type AssignableOwner,
  type CaregiverProspect,
  type ElderProspect,
  type PipelineActivity,
  type PipelineStages,
  type ProspectFilters,
} from "@/lib/prospects";
import {
  attachResumeToProspect,
  fetchPlacementSuggestions,
  parseResumeAndCreateProspect,
  parseResumeFile,
  type PlacementSuggestionsResponse,
  type ResumeParseResult,
} from "@/lib/recruitment";
import { ClientsAdminPanel } from "@/components/livewell/ClientsAdminPanel";

type Tab = "clients" | "elders" | "caregivers";

type ClientOption = {
  id: number;
  first_name: string;
  last_name: string;
};

const ACTIVITY_TYPES = ["NOTE", "CALL", "EMAIL", "VISIT"] as const;
const SOURCES = ["referral", "website", "hospital", "walk-in", "other"];

function toDatetimeLocal(iso: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromDatetimeLocal(value: string) {
  if (!value) return null;
  return new Date(value).toISOString();
}

export default function ProspectsPage() {
  return (
    <Suspense fallback={<p>Loading…</p>}>
      <ProspectsContent />
    </Suspense>
  );
}

function ProspectsContent() {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const deepElderId = Number(searchParams.get("elder") || "") || null;
  const deepCaregiverId = Number(searchParams.get("caregiver") || "") || null;
  const auth = getStoredAuth();
  const branding = useBranding();
  const showElderProspects = verticalHasFeature(branding.vertical, "elder_prospects");
  const showElderMatching = verticalHasFeature(branding.vertical, "elder_matching");
  const showElderProfiles = verticalHasFeature(branding.vertical, "elders");
  const demandLabel = demandEntityLabel(branding.vertical, branding.market);
  const demandPlural = demandEntityPluralLabel(branding.vertical, branding.market);
  const supplyLabel = supplyEntityLabel(branding.vertical, branding.market);
  const supplyPlural = supplyEntityPluralLabel(branding.vertical, branding.market);
  const writable = canWrite(auth?.role || "");
  const isAdmin = canManageUsers(auth?.role || "");
  const tabParam = searchParams.get("tab");
  const [tab, setTab] = useState<Tab>(() => {
    if (deepCaregiverId || tabParam === "caregivers") return "caregivers";
    if (deepElderId || tabParam === "elders") return "elders";
    if (tabParam === "clients" || (showElderProspects && showElderProfiles)) return "clients";
    if (showElderProspects) return "elders";
    return "caregivers";
  });
  const [stages, setStages] = useState<PipelineStages | null>(null);
  const [owners, setOwners] = useState<AssignableOwner[]>([]);
  const [elderRows, setElderRows] = useState<ElderProspect[]>([]);
  const [caregiverRows, setCaregiverRows] = useState<CaregiverProspect[]>([]);
  const [clientOptions, setClientOptions] = useState<ClientOption[]>([]);
  const [linkElderId, setLinkElderId] = useState<number | "">("");
  const [selectedElderId, setSelectedElderId] = useState<number | null>(deepElderId);
  const [selectedCaregiverId, setSelectedCaregiverId] = useState<number | null>(
    deepCaregiverId,
  );
  const [activities, setActivities] = useState<PipelineActivity[]>([]);
  // Client prospects: open leads only. Converted (WON) leads leave the pipeline → Clients.
  const [filters, setFilters] = useState<ProspectFilters>(() =>
    deepElderId || deepCaregiverId ? {} : { status: "OPEN" },
  );
  const [showNew, setShowNew] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [activityForm, setActivityForm] = useState({
    activity_type: "NOTE",
    body: "",
  });
  const [newForm, setNewForm] = useState({
    first_name: "",
    last_name: "",
    phone: "",
    email: "",
    source: "referral",
    notes: "",
  });
  const [resumePreview, setResumePreview] = useState<ResumeParseResult | null>(
    null,
  );
  const [resumeLoading, setResumeLoading] = useState(false);
  const [placements, setPlacements] =
    useState<PlacementSuggestionsResponse | null>(null);
  const [placementsLoading, setPlacementsLoading] = useState(false);

  const selectedElder = elderRows.find((r) => r.id === selectedElderId) ?? null;
  const selectedCaregiver =
    caregiverRows.find((r) => r.id === selectedCaregiverId) ?? null;
  const selected = tab === "elders" ? selectedElder : tab === "caregivers" ? selectedCaregiver : null;
  const stageOptions =
    tab === "elders"
      ? stages?.elder_stages ?? []
      : stages?.caregiver_stages ?? [];

  const loadList = useCallback(async () => {
    if (tab === "clients") return;
    if (tab === "elders") {
      if (!showElderProspects) return;
      const rows = await listElderProspects(filters);
      // Converted (WON) leads belong under Clients — hide unless filter = WON
      // or this row is the deep-linked / selected prospect.
      setElderRows(
        filters.status === "WON"
          ? rows.filter((r) => r.status === "WON")
          : filters.status
            ? rows
            : rows.filter(
                (r) =>
                  r.status !== "WON" ||
                  r.id === selectedElderId ||
                  r.id === deepElderId,
              ),
      );
    } else {
      setCaregiverRows(await listCaregiverProspects(filters));
    }
  }, [tab, filters, showElderProspects, selectedElderId, deepElderId]);

  const loadActivities = useCallback(async () => {
    if (tab === "elders" && selectedElderId) {
      setActivities(await listElderActivities(selectedElderId));
    } else if (tab === "caregivers" && selectedCaregiverId) {
      setActivities(await listCaregiverActivities(selectedCaregiverId));
    } else {
      setActivities([]);
    }
  }, [tab, selectedElderId, selectedCaregiverId]);

  useEffect(() => {
    if (!showElderProspects && (tab === "elders" || tab === "clients")) {
      setTab("caregivers");
      setSelectedElderId(null);
    }
  }, [showElderProspects, tab]);

  useEffect(() => {
    if (tab !== "elders" && tab !== "clients") return;
    api<ClientOption[]>("/api/v1/elders")
      .then(setClientOptions)
      .catch(() => setClientOptions([]));
  }, [tab, message]);

  useEffect(() => {
    setLinkElderId("");
  }, [selectedElderId]);

  useEffect(() => {
    if (deepElderId) {
      setTab("elders");
      setSelectedElderId(deepElderId);
      setSelectedCaregiverId(null);
      setFilters((f) => (f.status ? { ...f, status: undefined } : f));
    } else if (deepCaregiverId) {
      setTab("caregivers");
      setSelectedCaregiverId(deepCaregiverId);
      setSelectedElderId(null);
      setFilters((f) => (f.status ? { ...f, status: undefined } : f));
    }
  }, [deepElderId, deepCaregiverId]);

  useEffect(() => {
    fetchPipelineStages().then(setStages).catch(() => {});
    fetchAssignableOwners().then(setOwners).catch(() => {});
  }, []);

  useEffect(() => {
    loadList().catch((e) => setError(String(e)));
  }, [loadList]);

  useEffect(() => {
    loadActivities().catch(() => setActivities([]));
  }, [loadActivities]);

  async function onCreateNew(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      if (tab === "elders") {
        const row = await createElderProspect(newForm);
        setSelectedElderId(row.id);
        setSelectedCaregiverId(null);
      } else {
        const row = await createCaregiverProspect(newForm);
        setSelectedCaregiverId(row.id);
        setSelectedElderId(null);
      }
      setShowNew(false);
      setNewForm({
        first_name: "",
        last_name: "",
        phone: "",
        email: "",
        source: "referral",
        notes: "",
      });
      setMessage("Prospect created");
      await loadList();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    }
  }

  async function saveProspect(patch: Record<string, unknown>) {
    if (!selected || !writable) return;
    setError("");
    try {
      if (tab === "elders") {
        const updated = await updateElderProspect(selected.id, patch);
        setElderRows((rows) =>
          rows.map((r) => (r.id === updated.id ? updated : r)),
        );
      } else {
        const updated = await updateCaregiverProspect(selected.id, patch);
        setCaregiverRows((rows) =>
          rows.map((r) => (r.id === updated.id ? updated : r)),
        );
      }
      setMessage("Saved");
      await loadActivities();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  }

  async function onAddActivity(e: FormEvent) {
    e.preventDefault();
    if (!selected || !activityForm.body.trim()) return;
    setError("");
    try {
      if (tab === "elders") {
        await addElderActivity(selected.id, activityForm);
      } else {
        await addCaregiverActivity(selected.id, activityForm);
      }
      setActivityForm({ activity_type: "NOTE", body: "" });
      await loadActivities();
      setMessage("Activity logged");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  async function onResumeFile(
    file: File | undefined,
    mode: "preview" | "create" | "attach",
  ) {
    if (!file) return;
    setError("");
    setResumeLoading(true);
    try {
      if (mode === "preview") {
        setResumePreview(await parseResumeFile(file));
        setMessage("Resume parsed — review fields below");
      } else if (mode === "create") {
        const res = await parseResumeAndCreateProspect(file);
        setSelectedCaregiverId(res.prospect.id);
        setTab("caregivers");
        setResumePreview(res.parse);
        const stageNote =
          res.prospect.stage !== "APPLIED"
            ? ` — advanced to ${res.prospect.stage}`
            : "";
        setMessage(
          `Prospect created — score ${res.parse.candidate_score.toFixed(0)}${stageNote}`,
        );
        await loadList();
      } else if (mode === "attach" && selectedCaregiverId) {
        const res = await attachResumeToProspect(selectedCaregiverId, file);
        setResumePreview(res.parse);
        setCaregiverRows((rows) =>
          rows.map((r) => (r.id === res.prospect.id ? res.prospect : r)),
        );
        const stageNote =
          res.prospect.stage !== "APPLIED"
            ? ` — stage → ${res.prospect.stage}`
            : "";
        setMessage(
          `Resume attached — score ${res.parse.candidate_score.toFixed(0)}${stageNote}`,
        );
        await loadActivities();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Resume parse failed");
    } finally {
      setResumeLoading(false);
    }
  }

  async function onConvert() {
    if (!selected || !writable) return;
    const label = `${selected.first_name} ${selected.last_name}`;
    const linking =
      tab === "elders" && linkElderId !== "" ? Number(linkElderId) : null;
    if (
      !window.confirm(
        linking
          ? `Link ${label} to existing ${demandLabel.toLowerCase()} #${linking}?`
          : `Convert ${label} to a new active ${tab === "elders" ? demandLabel.toLowerCase() : supplyLabel.toLowerCase()} profile?`,
      )
    ) {
      return;
    }
    setError("");
    try {
      if (tab === "elders") {
        const res = await convertElderProspect(
          selected.id,
          linking != null ? { elder_id: linking } : undefined,
        );
        setMessage(
          linking
            ? `Linked to ${demandLabel.toLowerCase()} #${res.elder_id}. Prospect left the pipeline — open Clients.`
            : `Converted to ${demandLabel.toLowerCase()} #${res.elder_id}. Prospect left the pipeline — open Clients.`,
        );
        setLinkElderId("");
        setSelectedElderId(null);
        setTab("clients");
        setFilters({ status: "OPEN" });
      } else {
        const res = await convertCaregiverProspect(selected.id);
        setMessage(`Converted to ${supplyLabel.toLowerCase()} #${res.caregiver_id}`);
        await loadList();
        setSelectedCaregiverId(res.prospect.id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Convert failed");
    }
  }

  async function onUnlink() {
    if (!selected || !writable || tab !== "elders") return;
    if (!("converted_elder_id" in selected) || !selected.converted_elder_id) return;
    if (
      !window.confirm(
        `Unlink prospect #${selected.id} from client #${selected.converted_elder_id}? The prospect will reopen as OPEN.`,
      )
    ) {
      return;
    }
    setError("");
    try {
      const updated = await unlinkElderProspect(selected.id);
      setMessage(`Unlinked prospect #${updated.id}`);
      await loadList();
      setSelectedElderId(updated.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unlink failed");
    }
  }

  const rows = tab === "elders" ? elderRows : caregiverRows;

  return (
    <>
      <PageHeader
        title={t("pages.prospects.title")}
        subtitle={prospectsPageSubtitle(
          branding.vertical,
          branding.market,
          showElderProspects,
        )}
        action={
          writable && tab !== "clients" ? (
            <button type="button" onClick={() => setShowNew(!showNew)}>
              {showNew ? t("common.cancel") : t("pages.prospects.newProspect")}
            </button>
          ) : undefined
        }
      />
      <Flash
        error={error}
        message={message}
        onClear={() => {
          setError("");
          setMessage("");
        }}
      />

      {showElderProspects && showElderProfiles ? (
        <p
          className="card"
          style={{ padding: "0.65rem 0.85rem", marginBottom: "1rem", fontSize: "0.9rem" }}
        >
          <strong>Client leads &amp; assessments:</strong> use{" "}
          <Link href="/kushalaya/customers">Clients &amp; care flow</Link> (open leads + clients on
          one page). This screen is mainly for assessor / caregiver recruits.
        </p>
      ) : null}

      {writable && tab === "caregivers" && (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <h3>AI resume parsing</h3>
          <p className="muted">
            Upload a PDF or text resume to extract candidate details and score.
            Uses Azure Document Intelligence + OpenAI when configured; heuristic
            fallback in dev.
          </p>
          <input
            type="file"
            accept=".pdf,.txt,.doc,.docx"
            disabled={resumeLoading}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              onResumeFile(file, "create");
              e.target.value = "";
            }}
          />
        </div>
      )}

      {resumePreview && (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <h3>
            Parsed resume — score {resumePreview.candidate_score.toFixed(0)}
          </h3>
          <p className="muted">
            {resumePreview.provider} · {resumePreview.confidence} confidence
            {resumePreview.score_reasons.length > 0 &&
              ` · ${resumePreview.score_reasons.join("; ")}`}
          </p>
          <div className="grid-2" style={{ fontSize: "0.9rem" }}>
            <div>
              <strong>Name:</strong>{" "}
              {resumePreview.fields.first_name} {resumePreview.fields.last_name}
            </div>
            <div>
              <strong>Experience:</strong>{" "}
              {resumePreview.fields.years_experience ?? "—"} years
            </div>
            <div>
              <strong>Email:</strong> {resumePreview.fields.email ?? "—"}
            </div>
            <div>
              <strong>Phone:</strong> {resumePreview.fields.phone ?? "—"}
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <strong>Skills:</strong>{" "}
              {resumePreview.fields.skills.join(", ") || "—"}
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <strong>Languages:</strong>{" "}
              {resumePreview.fields.languages.join(", ") || "—"}
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <strong>Certifications:</strong>{" "}
              {resumePreview.fields.certifications.join(", ") || "—"}
            </div>
          </div>
        </div>
      )}

      <div className="pipeline-tabs" style={{ marginBottom: "1rem" }}>
        {showElderProspects && showElderProfiles && (
          <button
            type="button"
            className={tab === "clients" ? "" : "secondary"}
            onClick={() => {
              setTab("clients");
              setSelectedElderId(null);
              setSelectedCaregiverId(null);
            }}
          >
            {demandLabel}s
          </button>
        )}
        {showElderProspects && (
          <button
            type="button"
            className={tab === "elders" ? "" : "secondary"}
            onClick={() => {
              setTab("elders");
              setSelectedCaregiverId(null);
            }}
          >
            {demandLabel} prospects
          </button>
        )}
        <button
          type="button"
          className={tab === "caregivers" ? "" : "secondary"}
          onClick={() => {
            setTab("caregivers");
            setSelectedElderId(null);
          }}
        >
          {supplyLabel} recruits
        </button>
      </div>

      {tab === "clients" && showElderProfiles ? (
        <ClientsAdminPanel
          isAdmin={isAdmin}
          demandLabel={demandLabel}
          onMessage={setMessage}
          onError={setError}
        />
      ) : null}

      {tab !== "clients" && showNew && writable && (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <h3>
            New {tab === "elders" ? demandLabel.toLowerCase() : supplyLabel.toLowerCase()}{" "}
            prospect
          </h3>
          <form onSubmit={onCreateNew} className="grid-2">
            <div>
              <label>First name *</label>
              <input
                value={newForm.first_name}
                onChange={(e) =>
                  setNewForm((f) => ({ ...f, first_name: e.target.value }))
                }
                required
              />
            </div>
            <div>
              <label>Last name *</label>
              <input
                value={newForm.last_name}
                onChange={(e) =>
                  setNewForm((f) => ({ ...f, last_name: e.target.value }))
                }
                required
              />
            </div>
            <div>
              <label>Phone</label>
              <input
                value={newForm.phone}
                onChange={(e) =>
                  setNewForm((f) => ({ ...f, phone: e.target.value }))
                }
              />
            </div>
            <div>
              <label>Email</label>
              <input
                type="email"
                value={newForm.email}
                onChange={(e) =>
                  setNewForm((f) => ({ ...f, email: e.target.value }))
                }
              />
            </div>
            <div>
              <label>Source</label>
              <select
                value={newForm.source}
                onChange={(e) =>
                  setNewForm((f) => ({ ...f, source: e.target.value }))
                }
              >
                {SOURCES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <label>Initial notes</label>
              <textarea
                rows={2}
                value={newForm.notes}
                onChange={(e) =>
                  setNewForm((f) => ({ ...f, notes: e.target.value }))
                }
              />
            </div>
            <div>
              <button type="submit">Create prospect</button>
            </div>
          </form>
        </div>
      )}

      {tab !== "clients" ? (
      <>
      <div className="card" style={{ marginBottom: "1rem" }}>
        <div className="grid-2 pipeline-filters">
          <div>
            <label>Status</label>
            <select
              value={filters.status ?? ""}
              onChange={(e) =>
                setFilters((f) => ({
                  ...f,
                  status: e.target.value || undefined,
                }))
              }
            >
              <option value="OPEN">Open leads</option>
              <option value="LOST">Lost</option>
              <option value="">Open + lost</option>
              <option value="WON">Converted archive</option>
            </select>
          </div>
          <div>
            <label>Stage</label>
            <select
              value={filters.stage ?? ""}
              onChange={(e) =>
                setFilters((f) => ({
                  ...f,
                  stage: e.target.value || undefined,
                }))
              }
            >
              <option value="">All stages</option>
              {stageOptions.map((s) => (
                <option key={s} value={s}>
                  {stageLabel(s)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Owner</label>
            <select
              value={filters.owner_user_id ?? ""}
              onChange={(e) =>
                setFilters((f) => ({
                  ...f,
                  owner_user_id: e.target.value
                    ? Number(e.target.value)
                    : undefined,
                }))
              }
            >
              <option value="">Anyone</option>
              {owners.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.first_name} {o.last_name}
                </option>
              ))}
            </select>
          </div>
          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <label style={{ display: "flex", gap: "0.5rem", margin: 0 }}>
              <input
                type="checkbox"
                checked={!!filters.overdue_only}
                onChange={(e) =>
                  setFilters((f) => ({
                    ...f,
                    overdue_only: e.target.checked || undefined,
                  }))
                }
              />
              Overdue follow-ups only
            </label>
          </div>
        </div>
      </div>

      {tab === "elders" ? <LeadFunnel /> : null}

      <div className="pipeline-layout">
        <div className="card pipeline-list">
          <h3>
            {tab === "elders" ? demandPlural : supplyPlural} ({rows.length})
          </h3>
          {tab === "elders" ? (
            <p className="muted" style={{ fontSize: "0.85rem" }}>
              Open intake leads only. After convert/link, the prospect leaves this list — the senior
              lives under <strong>Clients</strong>.
            </p>
          ) : null}
          {rows.length === 0 ? (
            <p className="muted">
              {tab === "elders"
                ? "No open leads. Converted people are on the Clients tab."
                : "No prospects match filters"}
            </p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Name</th>
                  <th>Status</th>
                  <th>Stage</th>
                  {tab === "elders" && <th>Linked client</th>}
                  {tab === "elders" && <th>Source</th>}
                  <th>Owner</th>
                  <th>Follow-up</th>
                  {tab === "caregivers" && <th>Score</th>}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const sel =
                    tab === "elders"
                      ? row.id === selectedElderId
                      : row.id === selectedCaregiverId;
                  return (
                    <tr
                      key={row.id}
                      className={sel ? "pipeline-row-selected" : ""}
                      style={{ cursor: "pointer" }}
                      onClick={() => {
                        if (tab === "elders") setSelectedElderId(row.id);
                        else setSelectedCaregiverId(row.id);
                      }}
                    >
                      <td>#{row.id}</td>
                      <td>
                        {row.first_name} {row.last_name}
                      </td>
                      <td>{row.status}</td>
                      <td>{stageLabel(row.stage)}</td>
                      {tab === "elders" && (
                        <td>
                          {"converted_elder_id" in row && row.converted_elder_id
                            ? `#${row.converted_elder_id}`
                            : "—"}
                        </td>
                      )}
                      {tab === "elders" && (
                        <td title={"referred_by" in row && row.referred_by ? `Referred by ${row.referred_by}` : undefined}>
                          {("lead_source" in row && row.lead_source) || row.source || "—"}
                        </td>
                      )}
                      <td>{row.owner_name || "—"}</td>
                      <td>{formatFollowUp(row.next_follow_up_at)}</td>
                      {tab === "caregivers" && (
                        <td>
                          {"resume_score" in row && row.resume_score != null
                            ? row.resume_score.toFixed(0)
                            : "—"}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        <div className="card pipeline-detail">
          {!selected ? (
            <p className="muted">Select a prospect to view details and activity</p>
          ) : (
            <>
              <h3>
                {selected.first_name} {selected.last_name}
              </h3>
              <p className="muted" style={{ fontSize: "0.85rem" }}>
                Status: {selected.status} · Stage: {stageLabel(selected.stage)}
                {tab === "elders" ? ` · Prospect #${selected.id}` : ""}
              </p>

              {writable && selected.status === "OPEN" && (
                <div className="grid-2" style={{ marginTop: "1rem" }}>
                  <div>
                    <label>Stage</label>
                    <select
                      value={selected.stage}
                      onChange={(e) => {
                        const stage = e.target.value;
                        const patch: Record<string, unknown> = { stage };
                        if (stage === "LOST" || stage === "REJECTED") {
                          const reason = window.prompt("Lost / reject reason?");
                          if (reason) patch.lost_reason = reason;
                        }
                        saveProspect(patch);
                      }}
                    >
                      {stageOptions.map((s) => (
                        <option key={s} value={s}>
                          {stageLabel(s)}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label>Owner</label>
                    <select
                      value={selected.owner_user_id ?? ""}
                      onChange={(e) =>
                        saveProspect({
                          owner_user_id: e.target.value
                            ? Number(e.target.value)
                            : null,
                        })
                      }
                    >
                      <option value="">Unassigned</option>
                      {owners.map((o) => (
                        <option key={o.id} value={o.id}>
                          {o.first_name} {o.last_name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label>Next follow-up</label>
                    <input
                      type="datetime-local"
                      value={toDatetimeLocal(selected.next_follow_up_at)}
                      onChange={(e) =>
                        saveProspect({
                          next_follow_up_at: fromDatetimeLocal(e.target.value),
                        })
                      }
                    />
                  </div>
                  <div>
                    <label>Phone</label>
                    <input
                      defaultValue={selected.phone ?? ""}
                      onBlur={(e) =>
                        e.target.value !== (selected.phone ?? "") &&
                        saveProspect({ phone: e.target.value || null })
                      }
                    />
                  </div>
                  {selected.status === "OPEN" &&
                    (selected.stage === "LOST" ||
                      selected.stage === "REJECTED") && (
                      <div style={{ gridColumn: "1 / -1" }}>
                        <label>Lost reason</label>
                        <input
                          defaultValue={selected.lost_reason ?? ""}
                          onBlur={(e) =>
                            saveProspect({
                              lost_reason: e.target.value || null,
                            })
                          }
                        />
                      </div>
                    )}
                  <div style={{ gridColumn: "1 / -1" }}>
                    {tab === "elders" ? (
                      <>
                        <label>Link to existing {demandLabel.toLowerCase()} (optional)</label>
                        <select
                          value={linkElderId}
                          onChange={(e) =>
                            setLinkElderId(e.target.value ? Number(e.target.value) : "")
                          }
                          style={{ display: "block", marginBottom: "0.5rem", maxWidth: "24rem" }}
                        >
                          <option value="">Create new {demandLabel.toLowerCase()}</option>
                          {clientOptions.map((c) => (
                            <option key={c.id} value={c.id}>
                              #{c.id} · {c.first_name} {c.last_name}
                            </option>
                          ))}
                        </select>
                      </>
                    ) : null}
                    <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                      <button type="button" onClick={onConvert}>
                        {tab === "elders" && linkElderId !== ""
                          ? `Link to client #${linkElderId}`
                          : "Convert to active profile"}
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {"converted_elder_id" in selected &&
                selected.converted_elder_id &&
                showElderProfiles && (
                  <p className="muted" style={{ marginTop: "0.75rem" }}>
                    Converted to {demandLabel.toLowerCase()} #{selected.converted_elder_id}
                    {writable ? (
                      <>
                        {" · "}
                        <button type="button" className="secondary" onClick={() => void onUnlink()}>
                          Unlink
                        </button>
                      </>
                    ) : null}
                  </p>
                )}

              {tab === "elders" && selected ? <LeadDetails p={selected as ElderProspect} /> : null}

              {tab === "elders" && selected ? (
                isAdmin ? (
                  <div
                    className="admin-danger-zone"
                    role="region"
                    aria-label="Permanent delete"
                  >
                    <p className="admin-danger-zone__label">Admin · Permanent delete</p>
                    <p className="admin-danger-zone__hint">
                      Removes records permanently. Family users for a deleted client are unlinked.
                      This cannot be undone.
                    </p>
                    <div className="admin-danger-zone__actions">
                      <button
                        type="button"
                        className="danger admin-danger-btn"
                        onClick={() => {
                          if (
                            !window.confirm(
                              `Permanently delete prospect #${selected.id} (${selected.first_name} ${selected.last_name})?\n\nThis cannot be undone.`,
                            )
                          ) {
                            return;
                          }
                          permanentlyDeleteElderProspect(selected.id)
                            .then(() => {
                              setMessage(`Deleted prospect #${selected.id}`);
                              setSelectedElderId(null);
                              loadList().catch(() => {});
                            })
                            .catch((e) => setError(String(e)));
                        }}
                      >
                        Permanently delete this prospect
                      </button>
                      {"converted_elder_id" in selected &&
                      selected.converted_elder_id &&
                      showElderProfiles ? (
                        <button
                          type="button"
                          className="danger admin-danger-btn"
                          onClick={() => {
                            const eid = selected.converted_elder_id!;
                            if (
                              !window.confirm(
                                `Permanently delete client #${eid}?\n\nFamily users will be unlinked. Assessments stay but lose the elder link.`,
                              )
                            ) {
                              return;
                            }
                            permanentlyDeleteElder(eid)
                              .then(() => {
                                setMessage(`Deleted client #${eid}`);
                                loadList().catch(() => {});
                              })
                              .catch((e) => setError(String(e)));
                          }}
                        >
                          Permanently delete linked client #{selected.converted_elder_id}
                        </button>
                      ) : null}
                    </div>
                  </div>
                ) : (
                  <p className="muted admin-delete-hint" style={{ marginTop: "1rem" }}>
                    Need to remove this prospect or client? Ask a tenant admin to permanently
                    delete them.
                  </p>
                )
              ) : null}
              {"converted_caregiver_id" in selected &&
                selected.converted_caregiver_id && (
                  <p className="muted" style={{ marginTop: "0.75rem" }}>
                    Converted to {supplyLabel.toLowerCase()} #{selected.converted_caregiver_id}
                  </p>
                )}

              {tab === "caregivers" &&
                showElderMatching &&
                selected.status === "OPEN" &&
                ("has_resume" in selected && selected.has_resume) && (
                  <div style={{ marginTop: "1rem" }}>
                    <h4>Placement fit</h4>
                    {placementsLoading ? (
                      <p className="muted">Ranking {demandLabel.toLowerCase()} demand…</p>
                    ) : placements && placements.suggestions.length > 0 ? (
                      <>
                        <p className="muted" style={{ fontSize: "0.85rem" }}>
                          {placements.uncovered_clients} uncovered{" "}
                          {demandLabel.toLowerCase()}(s) on schedule
                        </p>
                        <table className="table">
                          <thead>
                            <tr>
                              <th>{demandLabel}</th>
                              <th>Match</th>
                              <th>Notes</th>
                            </tr>
                          </thead>
                          <tbody>
                            {placements.suggestions.map((s) => (
                              <tr key={s.elder_id}>
                                <td>
                                  <Link href={`/elders/${s.elder_id}`}>
                                    {s.elder_name}
                                  </Link>
                                  {s.uncovered && (
                                    <span
                                      className="muted"
                                      style={{ fontSize: "0.75rem" }}
                                    >
                                      {" "}
                                      · needs cover
                                    </span>
                                  )}
                                </td>
                                <td>{Math.round(s.match_score)}%</td>
                                <td
                                  className="muted"
                                  style={{ fontSize: "0.8rem" }}
                                >
                                  {s.reasons.join(" · ") || "—"}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        <p style={{ marginBottom: 0 }}>
                          <Link href="/matching">Open matching</Link>
                        </p>
                      </>
                    ) : (
                      <p className="muted">
                        No strong {demandLabel.toLowerCase()} matches yet — add schedule
                        demand or {demandLabel.toLowerCase()} requirements.
                      </p>
                    )}
                  </div>
                )}

              {writable &&
                tab === "caregivers" &&
                selected.status === "OPEN" && (
                  <div style={{ marginTop: "1rem" }}>
                    <h4>Resume</h4>
                    <p className="muted" style={{ fontSize: "0.85rem" }}>
                      {"has_resume" in selected && selected.has_resume
                        ? `Parsed — score ${selected.resume_score?.toFixed(0) ?? "—"}`
                        : "No resume on file"}
                    </p>
                    <input
                      type="file"
                      accept=".pdf,.txt,.doc,.docx"
                      disabled={resumeLoading}
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        onResumeFile(file, "attach");
                        e.target.value = "";
                      }}
                    />
                  </div>
                )}

              <div style={{ marginTop: "1.25rem" }}>
                <h4>Activity timeline</h4>
                {activities.length === 0 ? (
                  <p className="muted">No activity yet</p>
                ) : (
                  <ul className="pipeline-activity-list">
                    {activities.map((a) => (
                      <li key={a.id} className="pipeline-activity-item">
                        <div className="pipeline-activity-meta">
                          <strong>{a.activity_type}</strong>
                          {" · "}
                          {a.created_by_name || "System"}
                          {" · "}
                          {dateTimeIST(a.created_at)}
                        </div>
                        <p style={{ margin: "0.35rem 0 0" }}>{a.body}</p>
                      </li>
                    ))}
                  </ul>
                )}

                {writable && selected.status === "OPEN" && (
                  <form onSubmit={onAddActivity} style={{ marginTop: "1rem" }}>
                    <div className="grid-2">
                      <div>
                        <label>Type</label>
                        <select
                          value={activityForm.activity_type}
                          onChange={(e) =>
                            setActivityForm((f) => ({
                              ...f,
                              activity_type: e.target.value,
                            }))
                          }
                        >
                          {ACTIVITY_TYPES.map((t) => (
                            <option key={t} value={t}>
                              {t}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <label style={{ marginTop: "0.5rem" }}>Note</label>
                    <textarea
                      rows={2}
                      value={activityForm.body}
                      onChange={(e) =>
                        setActivityForm((f) => ({
                          ...f,
                          body: e.target.value,
                        }))
                      }
                      required
                    />
                    <button type="submit" style={{ marginTop: "0.5rem" }}>
                      Log activity
                    </button>
                  </form>
                )}
              </div>
            </>
          )}
        </div>
      </div>
      </>
      ) : null}
    </>
  );
}
