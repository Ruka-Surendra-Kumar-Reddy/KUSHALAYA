"use client";

import { useEffect, useMemo, useState } from "react";
import { api, getStoredAuth } from "@/lib/api";
import type { HomeSafetyAssessment } from "@/lib/livewell/assessment";
import { EMPTY_RESIDENT_PROFILE, type ResidentProfile } from "@/lib/livewell/resident-profile";
import { listElderProspects, type ElderProspect } from "@/lib/prospects";
import { ageFromDob } from "@/lib/livewell/assessmentDisplay";

type ElderOption = {
  id: number;
  first_name: string;
  last_name: string;
  phone?: string | null;
  address?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  gender?: string | null;
  date_of_birth?: string | null;
};

export type ClientLinkPatch = Partial<
  Pick<
    HomeSafetyAssessment,
    | "clientFirstName"
    | "clientLastName"
    | "clientAddress"
    | "clientPhone"
    | "clientEmail"
    | "familyContactName"
    | "familyContactPhone"
    | "elderId"
    | "prospectId"
    | "residentProfile"
  >
>;

type Props = {
  draft: HomeSafetyAssessment;
  onApply: (patch: ClientLinkPatch) => void;
};

function labelElder(e: ElderOption) {
  return `${e.first_name} ${e.last_name}`.trim() || "Client without a name";
}

function labelProspect(p: ElderProspect) {
  const name = `${p.first_name} ${p.last_name}`.trim() || `Prospect #${p.id}`;
  return name;
}

export function AssessmentClientPicker({ draft, onApply }: Props) {
  const [signedIn, setSignedIn] = useState(false);
  useEffect(() => setSignedIn(Boolean(getStoredAuth()?.access_token)), []);
  const [elders, setElders] = useState<ElderOption[]>([]);
  const [prospects, setProspects] = useState<ElderProspect[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("");

  useEffect(() => {
    if (!signedIn) return;
    let cancelled = false;
    setLoading(true);
    setError("");
    Promise.all([
      api<ElderOption[]>("/api/v1/elders"),
      listElderProspects({ status: "OPEN" }),
    ])
      .then(([elderList, prospectList]) => {
        if (cancelled) return;
        setElders(elderList);
        setProspects(prospectList.filter((p) => p.status === "OPEN"));
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Could not load clients");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [signedIn]);

  // A draft already linked to a client: fill a blank age from the client's date of birth.
  useEffect(() => {
    if (!draft.elderId || draft.residentProfile?.residentAge) return;
    const e = elders.find((x) => x.id === draft.elderId);
    const age = ageFromDob(e?.date_of_birth);
    if (age) onApply({ residentProfile: { ...(draft.residentProfile ?? EMPTY_RESIDENT_PROFILE), residentAge: age } });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [elders, draft.elderId]);

  const q = filter.trim().toLowerCase();
  const filteredElders = useMemo(() => {
    if (!q) return elders;
    return elders.filter((e) => labelElder(e).toLowerCase().includes(q));
  }, [elders, q]);
  const filteredProspects = useMemo(() => {
    const list = !q
      ? prospects
      : prospects.filter((p) => labelProspect(p).toLowerCase().includes(q));
    return [...list].sort((a, b) => b.id - a.id);
  }, [prospects, q]);

  function pickElder(elderId: number) {
    const e = elders.find((x) => x.id === elderId);
    if (!e) return;
    const profile: ResidentProfile = {
      ...(draft.residentProfile ?? EMPTY_RESIDENT_PROFILE),
      gender: e.gender ?? draft.residentProfile?.gender ?? "",
      residentAge: draft.residentProfile?.residentAge || ageFromDob(e.date_of_birth),
    };
    onApply({
      elderId: e.id,
      prospectId: null,
      clientFirstName: e.first_name,
      clientLastName: e.last_name,
      clientPhone: e.phone?.trim() || draft.clientPhone,
      clientAddress: e.address?.trim() || draft.clientAddress,
      clientEmail: draft.clientEmail,
      familyContactName: e.emergency_contact_name?.trim() || draft.familyContactName,
      familyContactPhone: e.emergency_contact_phone?.trim() || draft.familyContactPhone,
      residentProfile: profile,
    });
  }

  function pickProspect(prospectId: number) {
    const p = prospects.find((x) => x.id === prospectId);
    if (!p) return;
    onApply({
      prospectId: p.id,
      elderId: null,
      clientFirstName: p.first_name,
      clientLastName: p.last_name,
      clientPhone: p.phone?.trim() || "",
      clientAddress: p.address?.trim() || "",
      clientEmail: p.email?.trim() || "",
    });
  }

  function clearLink() {
    onApply({ elderId: null, prospectId: null });
  }

  if (!signedIn) {
    return null;
  }

  // Names, never "Client #1": the loaded list first, else the name on the assessment.
  const draftName = `${draft.clientFirstName || ""} ${draft.clientLastName || ""}`.trim();
  const linkedElder = draft.elderId != null ? elders.find((e) => e.id === draft.elderId) : undefined;
  const linkedProspect = draft.prospectId != null ? prospects.find((p) => p.id === draft.prospectId) : undefined;
  const linked =
    draft.elderId != null
      ? linkedElder
        ? labelElder(linkedElder)
        : draftName || "Linked client"
      : draft.prospectId != null
        ? `Open lead: ${linkedProspect ? labelProspect(linkedProspect) : draftName || "unnamed"}`
        : null;

  return (
    <div className="home-safety-client-picker">
      <h3>Client</h3>

      {linked ? (
        <p className="home-safety-client-picker-linked">
          Linked: <strong>{linked}</strong>{" "}
          <button type="button" className="secondary" onClick={clearLink}>
            Clear
          </button>
        </p>
      ) : null}

      <label className="home-safety-field">
        Search
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Lakshmi, Reddy…"
          autoComplete="off"
        />
      </label>

      <div className="home-safety-field-row">
        <label className="home-safety-field">
          Existing client
          <select
            value={draft.elderId ?? ""}
            onChange={(e) => {
              const v = e.target.value;
              if (!v) return;
              pickElder(Number(v));
            }}
            disabled={loading}
          >
            <option value="">— Select client —</option>
            {filteredElders.map((e) => (
              <option key={e.id} value={e.id}>
                {labelElder(e)}
              </option>
            ))}
          </select>
        </label>
        <label className="home-safety-field">
          Lead
          <select
            value={
              draft.prospectId != null && prospects.some((p) => p.id === draft.prospectId)
                ? draft.prospectId
                : ""
            }
            onChange={(e) => {
              const v = e.target.value;
              if (!v) return;
              pickProspect(Number(v));
            }}
            disabled={loading}
          >
            <option value="">— Select lead —</option>
            {filteredProspects.map((p) => (
              <option key={p.id} value={p.id}>
                {labelProspect(p)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {loading ? <p className="muted">Loading clients…</p> : null}
      {error ? <p className="error">{error}</p> : null}
    </div>
  );
}
