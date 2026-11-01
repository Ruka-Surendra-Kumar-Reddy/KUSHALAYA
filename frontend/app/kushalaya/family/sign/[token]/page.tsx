"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { PublicBrandMark } from "@/components/BrandLogo";
import { ContractText } from "@/components/contracts/ContractText";
import { SignaturePad, SignatureView, type SignatureValue } from "@/components/contracts/SignaturePad";
import { formatIst } from "@/components/contracts/format";
import "@/components/contracts/contracts.css";
import { familyFont } from "@/components/livewell/family/family-font";
import { getApiUrl } from "@/lib/api";
import { downloadPublicContractPdf, type PublicContract, type SignatureBlock } from "@/lib/contracts";
import { PUBLIC_PHONE } from "@/lib/public-brand";
import "./sign.css";

/**
 * No-login signing link (/sign/<token> on the family site). KushAlaya has already
 * signed; the vendor / client reads the text, types their name, draws or types a
 * signature and ticks "I agree". The server records it once and makes the PDF.
 */
export default function SignContractPage() {
  const { token } = useParams<{ token: string }>();
  const [data, setData] = useState<PublicContract | null>(null);
  const [problem, setProblem] = useState("");
  const [name, setName] = useState("");
  const [sig, setSig] = useState<SignatureValue>({ png: null, text: null });
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let stop = false;
    (async () => {
      try {
        const res = await fetch(`${getApiUrl()}/api/v1/home-safety/sign/${encodeURIComponent(token)}`, { cache: "no-store" });
        const body = await res.json().catch(() => ({}));
        if (stop) return;
        if (!res.ok) return setProblem(typeof body.detail === "string" ? body.detail : "This link is not valid.");
        setData(body as PublicContract);
        setName((body as PublicContract).signer_name || "");
      } catch {
        if (!stop) setProblem("Couldn't load the contract. Check your connection and try again.");
      }
    })();
    return () => {
      stop = true;
    };
  }, [token]);

  async function sign() {
    setError("");
    if (name.trim().length < 2) return setError("Type your full name.");
    if (!sig.png && !sig.text) return setError("Draw your signature or type it.");
    if (!agree) return setError("Tick “I agree” to sign.");
    setBusy(true);
    try {
      const res = await fetch(`${getApiUrl()}/api/v1/home-safety/sign/${encodeURIComponent(token)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, signature_png: sig.png, signature_text: sig.text, agree }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Couldn't sign. Please try again.");
      setData(body as PublicContract);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't sign");
    } finally {
      setBusy(false);
    }
  }

  const signed = data?.status === "signed";

  return (
    <main className={`sg-page ${familyFont.className}`}>
      <header className="sg-head">
        <PublicBrandMark className="sg-logo" />
        <span className={`sg-tag${signed ? " is-signed" : ""}`}>{signed ? "Signed" : "To sign"}</span>
      </header>

      {problem ? (
        <section className="sg-card">
          <h1>This link can&apos;t be used</h1>
          <p className="sg-muted">{problem}</p>
          <p className="sg-muted">
            Call KushAlaya on <a href={PUBLIC_PHONE.tel}>{PUBLIC_PHONE.display}</a>.
          </p>
        </section>
      ) : !data ? (
        <section className="sg-card">
          <p className="sg-muted">Loading the contract…</p>
        </section>
      ) : (
        <>
          <section className="sg-card">
            <p className="sg-kicker">
              {data.ref} · for {data.signer_name}
            </p>
            {signed ? (
              <div className="sg-done" role="status">
                <h1>Signed by both sides</h1>
                <p>Thank you. A copy has been emailed to you and to {data.company_name}.</p>
                <button type="button" onClick={() => void downloadPublicContractPdf(token, data.ref).catch((e) => setError(String(e.message || e)))}>
                  Download signed PDF
                </button>
              </div>
            ) : (
              <p className="sg-muted">
                {data.company_name} has signed this. Please read it, then sign at the bottom.
                {data.expires_at ? ` The link works until ${formatIst(data.expires_at, false)}.` : ""}
              </p>
            )}
            <div className="sg-text">
              <ContractText title={data.title} body={data.body} />
            </div>
          </section>

          <section className="sg-card">
            <h2 className="sg-h2">Signatures</h2>
            <div className="sg-blocks">
              <Block heading={`For ${data.company_name}`} b={data.company} />
              {data.signer ? (
                <Block heading={data.party_label} b={data.signer} />
              ) : (
                <div className="sg-block is-empty">
                  <p className="sg-block-head">{data.party_label}</p>
                  <p className="sg-muted">Your signature goes here</p>
                </div>
              )}
            </div>
          </section>

          {!signed ? (
            <section className="sg-card sg-form">
              <h2 className="sg-h2">Sign</h2>
              {error ? <p className="sg-error" role="alert">{error}</p> : null}
              <label className="sg-field">
                Your full name
                <input value={name} maxLength={200} autoComplete="name" onChange={(e) => setName(e.target.value)} />
              </label>
              <SignaturePad onChange={setSig} defaultTyped={name} label="Your signature" />
              <label className="sg-agree">
                <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
                <span>I have read this contract and I agree to it. I am signing it electronically.</span>
              </label>
              <button type="button" className="sg-sign" disabled={busy} onClick={() => void sign()}>
                {busy ? "Signing…" : "Sign"}
              </button>
              <p className="sg-small">
                When you sign, we record your name, signature, the time, your IP address and device, and a fingerprint
                (SHA-256) of this exact text. You get the signed PDF by email.
              </p>
            </section>
          ) : error ? (
            <p className="sg-error">{error}</p>
          ) : null}
        </>
      )}
    </main>
  );
}

function Block({ heading, b }: { heading: string; b: SignatureBlock }) {
  return (
    <div className="sg-block">
      <p className="sg-block-head">{heading}</p>
      <div className="sg-block-sig">
        <SignatureView png={b.signature_png} text={b.signature_text} />
      </div>
      <p className="sg-block-who">
        <strong>{b.name}</strong>
        {b.designation ? <>, {b.designation}</> : null}
        <br />
        <span className="sg-muted">{b.signed_at_ist}</span>
      </p>
    </div>
  );
}
