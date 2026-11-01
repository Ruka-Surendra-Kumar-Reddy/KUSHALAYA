"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  STATUS_LABEL,
  contractAction,
  contractsMeta,
  downloadContractPdf,
  getContract,
  listContracts,
  signUrl,
  whatsappHref,
  type Contract,
  type ContractKind,
  type ContractsMeta,
} from "@/lib/contracts";
import { formatIst } from "./format";
import { ContractText } from "./ContractText";
import { SendContract } from "./SendContract";
import { SignatorySetup } from "./SignatorySetup";
import "./contracts.css";

/** Copy link + WhatsApp for a sent contract. */
export function ContractLinkActions({ c }: { c: Contract }) {
  const [copied, setCopied] = useState(false);
  if (!c.sign_path) return null;
  const url = signUrl(c.sign_path);
  async function copy() {
    const { copyText } = await import("@/lib/share");
    if (await copyText(url)) {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2500);
    }
  }
  return (
    <span className="ct-linkacts">
      <button type="button" className="secondary ct-small" onClick={() => void copy()}>
        {copied ? "Link copied" : "Copy link"}
      </button>
      <a className="secondary ct-small ct-wa" href={whatsappHref(c)} target="_blank" rel="noopener noreferrer">
        WhatsApp
      </a>
    </span>
  );
}

/**
 * Contracts for one client or vendor (or all, on the Contracts page): status, the
 * signing link, KushAlaya's signature for ones waiting, resend / cancel, signed PDF.
 */
export function ContractsPanel({
  kind,
  elderId,
  vendorId,
  partyName = "",
  canEdit,
  showParty = false,
  heading = "Contracts",
  statusFilter,
  refreshKey = 0,
}: {
  kind?: ContractKind;
  elderId?: number;
  vendorId?: number;
  partyName?: string;
  canEdit: boolean;
  showParty?: boolean;
  heading?: string | null;
  statusFilter?: string;
  refreshKey?: number;
}) {
  const [rows, setRows] = useState<Contract[] | null>(null);
  const [meta, setMeta] = useState<ContractsMeta | null>(null);
  const [sending, setSending] = useState(false);
  const [busy, setBusy] = useState(0);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<Contract | null>(null);
  const [needSignature, setNeedSignature] = useState<number | null>(null);

  const load = useCallback(() => {
    listContracts({ elder_id: elderId, vendor_id: vendorId, status: statusFilter })
      .then((r) => {
        setRows(r);
        setError("");
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load contracts"));
  }, [elderId, vendorId, statusFilter]);

  useEffect(() => {
    load();
  }, [load, refreshKey]);
  useEffect(() => {
    contractsMeta().then(setMeta).catch(() => undefined);
  }, []);

  async function act(c: Contract, action: "submit" | "sign-and-send" | "resend" | "cancel") {
    if (action === "cancel" && !window.confirm(`Cancel “${c.title}” for ${c.party_name}? The link stops working.`)) return;
    if (action === "sign-and-send" && !meta?.signatory) return setNeedSignature(c.id);
    setBusy(c.id);
    setError("");
    try {
      await contractAction(c.id, action);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update the contract");
    } finally {
      setBusy(0);
    }
  }

  async function view(c: Contract) {
    if (open?.id === c.id) return setOpen(null);
    try {
      setOpen(await getContract(c.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not open the contract");
    }
  }

  const canSign = !!meta?.can_sign;

  return (
    <div className="ct-panel">
      {heading !== null || (canEdit && kind) ? (
        <div className="ct-panel-head">
          {heading ? <h3>{heading}</h3> : <span />}
          {canEdit && kind ? (
            <span className="ct-panel-acts">
              <Link href="/kushalaya/contracts?tab=templates" className="ct-textlink">
                Templates
              </Link>
              <button type="button" className="ct-small" onClick={() => setSending(true)}>
                {kind === "vendor" ? "Send agreement" : "Send contract"}
              </button>
            </span>
          ) : null}
        </div>
      ) : null}
      {error ? <p className="error-text">{error}</p> : null}
      {needSignature ? (
        <div className="ct-inline-setup card">
          <h4>Your signature for KushAlaya</h4>
          <SignatorySetup
            current={null}
            defaultName={meta?.my_name || ""}
            onCancel={() => setNeedSignature(null)}
            onSaved={(s) => {
              const id = needSignature;
              setMeta((m) => (m ? { ...m, signatory: s } : m));
              setNeedSignature(null);
              const c = rows?.find((r) => r.id === id);
              if (c) void (async () => {
                setBusy(c.id);
                try {
                  await contractAction(c.id, "sign-and-send");
                  load();
                } catch (e) {
                  setError(e instanceof Error ? e.message : "Could not sign");
                } finally {
                  setBusy(0);
                }
              })();
            }}
          />
        </div>
      ) : null}
      {rows === null ? (
        <p className="muted">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="muted ct-empty">No contracts yet.</p>
      ) : (
        <ul className="ct-list" aria-label="Contracts">
          {rows.map((c) => (
            <li key={c.id} className="ct-item">
              <div className="ct-item-main">
                <div className="ct-item-title">
                  <strong>{c.title}</strong>
                  <span className={`ct-pill is-${c.status}`}>{STATUS_LABEL[c.status]}</span>
                </div>
                <p className="muted ct-item-meta">
                  {showParty ? <>{c.party_name} · </> : null}
                  {c.ref} · signer {c.signer_name}
                  {c.signer_relation ? ` (${c.signer_relation})` : ""}
                </p>
                <p className="muted ct-item-meta">{timeline(c)}</p>
              </div>
              <div className="ct-item-acts">
                <button type="button" className="secondary ct-small" onClick={() => void view(c)}>
                  {open?.id === c.id ? "Hide" : "View"}
                </button>
                {c.status === "signed" ? (
                  <button type="button" className="ct-small" onClick={() => void downloadContractPdf(c).catch((e) => setError(String(e.message || e)))}>
                    Download signed PDF
                  </button>
                ) : null}
                {canEdit && (c.status === "sent" || c.status === "viewed") ? <ContractLinkActions c={c} /> : null}
                {canEdit && canSign && (c.status === "draft" || c.status === "awaiting_company") ? (
                  <button type="button" className="ct-small" disabled={busy === c.id} onClick={() => void act(c, "sign-and-send")}>
                    Sign &amp; send
                  </button>
                ) : null}
                {canEdit && !canSign && c.status === "draft" ? (
                  <button type="button" className="ct-small" disabled={busy === c.id} onClick={() => void act(c, "submit")}>
                    Send for KushAlaya signature
                  </button>
                ) : null}
                {canEdit && (c.status === "sent" || c.status === "viewed" || c.status === "expired") ? (
                  <button type="button" className="secondary ct-small" disabled={busy === c.id} onClick={() => void act(c, "resend")}>
                    Resend
                  </button>
                ) : null}
                {canEdit && c.status !== "signed" && c.status !== "cancelled" ? (
                  <button type="button" className="secondary ct-small ct-danger" disabled={busy === c.id} onClick={() => void act(c, "cancel")}>
                    Cancel
                  </button>
                ) : null}
              </div>
              {open?.id === c.id && open.body ? (
                <div className="ct-preview ct-item-text">
                  <ContractText title={open.title} body={open.body} />
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {sending && kind ? (
        <SendContract
          party={{ kind, elderId, vendorId, partyName }}
          onClose={() => setSending(false)}
          onDone={load}
        />
      ) : null}
    </div>
  );
}

function timeline(c: Contract): string {
  const bits: string[] = [];
  if (c.company_signed_at) bits.push(`KushAlaya signed ${formatIst(c.company_signed_at)} (${c.company_signer_name})`);
  else if (c.created_at) bits.push(`Created ${formatIst(c.created_at)}`);
  if (c.viewed_at) bits.push(`viewed ${formatIst(c.viewed_at)}`);
  if (c.signed_at) bits.push(`signed ${formatIst(c.signed_at)}`);
  else if ((c.status === "sent" || c.status === "viewed") && c.expires_at) bits.push(`link until ${formatIst(c.expires_at, false)}`);
  return bits.join(" · ");
}
