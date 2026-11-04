"use client";

import { useRef, useState } from "react";
import type { Vendor } from "@/components/ops/VendorsList";
import { api, downloadFileBlob, postFormData } from "@/lib/api";
import { parseApiTime } from "@/lib/ist";

/** The paper agreement signed on a visit: upload the scan, open it, replace or remove it. */
export function VendorSignedCopy({
  vendor,
  canEdit,
  onChange,
}: {
  vendor: Vendor;
  canEdit: boolean;
  onChange: (v: Vendor) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const path = `/api/v1/vendors/${vendor.id}/signed-agreement`;
  const on = vendor.signed_agreement_at ? parseApiTime(vendor.signed_agreement_at) : null;

  async function run(work: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (e) {
      setError(e instanceof Error ? e.message : "That did not work. Try again.");
    } finally {
      setBusy(false);
    }
  }

  function upload(file: File | undefined) {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    void run(async () => onChange(await postFormData<Vendor>(path, form)));
    if (input.current) input.current.value = "";
  }

  function open() {
    void run(async () => {
      const url = URL.createObjectURL(await downloadFileBlob(path));
      const link = document.createElement("a");
      link.href = url;
      link.download = vendor.signed_agreement_name || "signed-agreement";
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    });
  }

  function remove() {
    if (!window.confirm("Remove the signed copy? The vendor will show as agreement pending.")) return;
    void run(async () => onChange(await api<Vendor>(path, { method: "DELETE" })));
  }

  return (
    <section className="vn-signed" aria-label="Signed agreement">
      <h3>Signed agreement</h3>
      {vendor.signed_agreement_name ? (
        <p className="muted">
          {vendor.signed_agreement_name}
          {on ? ` · uploaded ${on.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}` : ""}
          {vendor.signed_agreement_by ? ` by ${vendor.signed_agreement_by}` : ""}
        </p>
      ) : (
        <p className="muted">Signed on paper? Upload a PDF or a photo (10 MB at most).</p>
      )}
      <div className="vn-signed-acts">
        {vendor.signed_agreement_name ? (
          <button type="button" className="secondary" disabled={busy} onClick={open}>
            Download
          </button>
        ) : null}
        {canEdit ? (
          <button type="button" className="secondary" disabled={busy} onClick={() => input.current?.click()}>
            {vendor.signed_agreement_name ? "Replace" : "Upload signed copy"}
          </button>
        ) : null}
        {canEdit && vendor.signed_agreement_name ? (
          <button type="button" className="secondary" disabled={busy} onClick={remove}>
            Remove
          </button>
        ) : null}
      </div>
      <input
        ref={input}
        type="file"
        hidden
        accept="application/pdf,image/jpeg,image/png"
        onChange={(e) => upload(e.target.files?.[0])}
      />
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}
