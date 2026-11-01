"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { PageActions } from "@/components/ops/PageActions";
import { AssessmentBoard } from "@/components/ops/AssessmentBoard";
import { ScheduleJobs } from "@/components/ops/ScheduleJobs";
import { NewAssessment, draftText } from "@/components/ops/NewAssessment";
import { useRouter } from "next/navigation";
import { OpsModal } from "@/components/ops/OpsModal";
import { SearchPick } from "@/components/ops/SearchPick";
import { assessmentTargets, startAssessment, type AssessmentTarget } from "@/lib/jobs";
import { can, isAdmin as isAdminUser } from "@/lib/roles";

export default function OpsAssessmentsPage() {
  const sysAdmin = isAdminUser();
  const edit = can("edit");
  const [assignToken, setAssignToken] = useState(0);
  const [reload, setReload] = useState(0);
  // "New assessment": pick a client or an open lead, then the same checklist screen
  // the caregiver uses. An unfinished draft is offered first (NewAssessment).
  const [picking, setPicking] = useState(false);
  const [targets, setTargets] = useState<AssessmentTarget[] | null>(null);
  const [key, setKey] = useState("");
  const [loadError, setLoadError] = useState("");
  useEffect(() => {
    if (!picking || targets) return;
    assessmentTargets()
      .then(setTargets)
      .catch((e) => setLoadError(e instanceof Error ? e.message : "Could not load clients and leads"));
  }, [picking, targets]);
  const chosen = targets?.find((t) => t.key === key) ?? null;
  const router = useRouter();
  const [opening, setOpening] = useState(false);
  // A draft is known from the list: ask straight away (continue / start new), one row of buttons.
  async function openDraft(fresh: boolean) {
    if (!chosen) return;
    setOpening(true);
    setLoadError("");
    try {
      const res = await startAssessment(chosen.elder_id ? { elder_id: chosen.elder_id } : { lead_id: Number(chosen.lead_id) }, fresh);
      router.push(`/caregiver/assess/${res.job_id}?from=assessments`);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Could not start the assessment");
      setOpening(false);
    }
  }
  const clients = (targets ?? []).filter((t) => t.kind === "client");
  const leads = (targets ?? []).filter((t) => t.kind === "lead");
  return (
    <>
      <div className="ks-head-row">
        <PageHeader title="Assessments" subtitle="Scheduled, in progress and completed — one list" />
        {edit ? (
          <div className="ks-head-actions">
            <button type="button" onClick={() => setPicking(true)} aria-label="New assessment" title="New assessment">
              <span className="ks-ha-icon" aria-hidden="true">+</span>
              <span className="ks-ha-label">+ New assessment</span>
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => setAssignToken((n) => n + 1)}
              aria-label="Schedule an assessment"
              title="Schedule an assessment"
            >
              <span className="ks-ha-icon" aria-hidden="true"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 11h18" /></svg></span>
              <span className="ks-ha-label">Schedule</span>
            </button>
          </div>
        ) : null}
      </div>
      {sysAdmin ? (
        <PageActions>
          <Link className="secondary" href="/kushalaya/rubric">
            Questions
          </Link>
        </PageActions>
      ) : null}
      <OpsModal open={picking} title="New assessment" onClose={() => setPicking(false)}>
        <div style={{ display: "grid", gap: "0.9rem" }}>
          <SearchPick
            label="Search"
            value={key}
            onChange={setKey}
            openOnType
            loading={!targets && !loadError}
            placeholder="Name, phone or ID (C12 / L7)"
            items={[...clients, ...leads].map((t) => ({
              value: t.key,
              label: t.name || "No name",
              group: t.kind === "lead" ? (t.draft ? "Lead · draft open" : "Lead") : t.draft ? "Draft open" : undefined,
              hint: [t.ref, t.phone].filter(Boolean).join(" · ") || undefined,
            }))}
          />
          <p className="ks-pick-or">or choose from a list</p>
          <div className="ks-pick-two">
            <label>
              Client
              <select value={key.startsWith("client:") ? key : ""} onChange={(e) => setKey(e.target.value)} disabled={!targets}>
                <option value="">{targets ? `Select client (${clients.length})` : "Loading…"}</option>
                {clients.map((t) => (
                  <option key={t.key} value={t.key}>
                    {t.name || "No name"}
                    {t.ref ? ` · ${t.ref}` : ""}
                    {t.draft ? " · draft open" : ""}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Lead
              <select value={key.startsWith("lead:") ? key : ""} onChange={(e) => setKey(e.target.value)} disabled={!targets}>
                <option value="">{targets ? `Select lead (${leads.length})` : "Loading…"}</option>
                {leads.map((t) => (
                  <option key={t.key} value={t.key}>
                    {t.name || "No name"}
                    {t.ref ? ` · ${t.ref}` : ""}
                    {t.draft ? " · draft open" : ""}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {chosen?.draft ? <p className="ks-draft-note">{draftText(chosen.name, chosen.draft)}</p> : null}
          <div className="ks-modal-actions">
            <button type="button" className="secondary" onClick={() => setPicking(false)}>
              Cancel
            </button>
            {chosen?.draft ? (
              <>
                <button type="button" className="secondary" disabled={opening} onClick={() => void openDraft(true)}>
                  Start a new one
                </button>
                <button type="button" disabled={opening} onClick={() => void openDraft(false)}>
                  {opening ? "Opening…" : "Continue the draft"}
                </button>
              </>
            ) : (
              <NewAssessment
                key={key}
                who={chosen ? (chosen.elder_id ? { elder_id: chosen.elder_id } : { lead_id: Number(chosen.lead_id) }) : null}
                name={chosen?.name ?? ""}
                draft={null}
                from="assessments"
                label="Start the checklist"
              />
            )}
          </div>
          {loadError ? <p className="error" style={{ margin: 0 }}>{loadError}</p> : null}
        </div>
      </OpsModal>
      <ScheduleJobs
        kind="assessment"
        title="Schedule an assessment"
        openToken={assignToken}
        hideAddButton
        formOnly
        onSaved={() => setReload((n) => n + 1)}
      />
      <AssessmentBoard reloadToken={reload} />
    </>
  );
}
