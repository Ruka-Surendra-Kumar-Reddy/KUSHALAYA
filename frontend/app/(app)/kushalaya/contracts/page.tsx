"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { ContractsPanel } from "@/components/contracts/ContractsPanel";
import { SignatorySetup } from "@/components/contracts/SignatorySetup";
import { TemplateEditor } from "@/components/contracts/TemplateEditor";
import "@/components/contracts/contracts.css";
import { getStoredAuth } from "@/lib/api";
import { STATUS_LABEL, contractsMeta, type ContractsMeta } from "@/lib/contracts";
import { can } from "@/lib/roles";

const TABS = [
  { key: "contracts", label: "Contracts" },
  { key: "templates", label: "Templates" },
  { key: "signature", label: "My signature" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

/**
 * Contracts: every vendor agreement and client contract, the editable templates, and
 * the admin's saved signature. Send a contract from a vendor (Vendors) or a client
 * (client page → Documents).
 */
export default function ContractsPage() {
  const [tab, setTabState] = useState<TabKey>("contracts");
  const [meta, setMeta] = useState<ContractsMeta | null>(null);
  const [status, setStatus] = useState("");
  const auth = getStoredAuth();
  const canEdit = can("edit", auth?.role || "");

  useEffect(() => {
    const key = new URLSearchParams(window.location.search).get("tab");
    if (key && TABS.some((t) => t.key === key)) setTabState(key as TabKey);
    contractsMeta().then(setMeta).catch(() => undefined);
  }, []);

  function setTab(t: TabKey) {
    setTabState(t);
    const url = new URL(window.location.href);
    if (t === "contracts") url.searchParams.delete("tab");
    else url.searchParams.set("tab", t);
    window.history.replaceState(null, "", url);
  }

  const tabs = TABS.filter((t) => t.key !== "signature" || meta?.can_sign);

  return (
    <>
      <div className="ks-head-row">
        <PageHeader title="Contracts" subtitle="Vendor agreements and client contracts, signed in the app" />
      </div>
      <div className="ct-tabs" role="tablist">
        {tabs.map((t) => (
          <button key={t.key} type="button" role="tab" aria-selected={tab === t.key} className={tab === t.key ? "is-active" : ""} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "contracts" ? (
        <section className="card">
          <div className="ct-bar">
            <select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All statuses</option>
              {Object.entries(STATUS_LABEL).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
            <span className="muted ct-note">Send a new one from a vendor (Vendors) or a client&apos;s Documents tab.</span>
          </div>
          <ContractsPanel canEdit={canEdit} showParty heading={null} statusFilter={status || undefined} />
        </section>
      ) : null}

      {tab === "templates" && meta ? <TemplateEditor meta={meta} /> : null}

      {tab === "signature" && meta?.can_sign ? (
        <section className="card ct-sigcard">
          <h2>My signature</h2>
          <SignatorySetup
            current={meta.signatory}
            defaultName={meta.my_name}
            onSaved={(s) => setMeta({ ...meta, signatory: s })}
          />
        </section>
      ) : null}
    </>
  );
}
