"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import {
  CUSTOMER_DOC_TEMPLATES,
  CUSTOMER_DOC_TEMPLATE_VERSION,
  PACKET_LABELS,
  emergencyInfoSheetChecklist,
  fillContextFromAssessment,
  type CustomerDocFillContext,
  type CustomerDocPacket,
  type CustomerDocTemplate,
} from "@/lib/livewell/customerDocumentTemplates";
import type { HomeSafetyAssessment } from "@/lib/livewell/assessment";
import { loadAssessmentMerged } from "@/lib/livewell/assessmentSync";
import { getAssessment } from "@/lib/livewell/storage";
import { hydratePendingAssessment } from "@/lib/livewell/startAssessment";
import { CustomerDocumentsPanel } from "@/components/livewell/CustomerDocumentsPanel";
import { publicBrandName, withPublicBrand } from "@/lib/public-brand";

const ALL_PACKETS: CustomerDocPacket[] = [
  "enrollment",
  "assessment",
  "installation",
  "completion",
];

function Field({
  label,
  value,
  wide,
}: {
  label: string;
  value?: string;
  wide?: boolean;
}) {
  return (
    <div className={`lw-doc-field${wide ? " lw-doc-field-wide" : ""}`}>
      <dt>{label}</dt>
      <dd>{value?.trim() ? value : "__________________________"}</dd>
    </div>
  );
}

function PrintEmergencyInfoSheet({
  template,
  ctx,
}: {
  template: CustomerDocTemplate;
  ctx: CustomerDocFillContext;
}) {
  const check = emergencyInfoSheetChecklist(ctx);
  return (
    <article
      className="lw-doc-form lw-doc-eis"
      data-form={template.code}
      id="LW_EMERGENCY_INFO_SHEET"
    >
      <header className="lw-doc-form-head">
        <div className="lw-doc-form-head-row">
          <p className="lw-doc-brand">{publicBrandName()}</p>
          <p className="lw-doc-form-code">{template.code}</p>
        </div>
        <h2>Emergency Information Sheet</h2>
        <p className="lw-doc-packet">
          Post near phone / fridge / bedside · Assessment deliverable (EMG-001)
        </p>
      </header>

      {!check.ready ? (
        <section className="lw-doc-block lw-doc-screen-only lw-doc-eis-warn">
          <h3>Complete intake before posting</h3>
          <p className="muted">Still needed:</p>
          <ul>
            {check.missing.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
          <p className="muted">
            Return to assessment intake, fill these fields, then print again. Blank lines below can
            also be completed by hand.
          </p>
        </section>
      ) : null}

      <section className="lw-doc-block">
        <h3>Resident</h3>
        <dl className="lw-doc-fields">
          <Field label="Full name" value={ctx.elderName} wide />
          <Field label="Home address" value={ctx.address} wide />
          <Field label="Phone" value={ctx.phone} />
          <Field label="Age" value={ctx.age} />
          <Field label="Lives alone" value={ctx.livesAlone} />
          <Field label="Mobility aid" value={ctx.mobility} />
        </dl>
      </section>

      <section className="lw-doc-block">
        <h3>Emergency contacts</h3>
        <dl className="lw-doc-fields">
          <Field label="Primary contact" value={ctx.primaryContactName} />
          <Field label="Primary phone" value={ctx.primaryContactPhone} />
          <Field label="Secondary contact" value={ctx.secondaryContactName} />
          <Field label="Secondary phone" value={ctx.secondaryContactPhone} />
        </dl>
      </section>

      <section className="lw-doc-block">
        <h3>Medical notes</h3>
        <dl className="lw-doc-fields">
          <Field label="Conditions" value={ctx.medicalConditions} wide />
          <Field label="Allergies" value={ctx.allergies} wide />
          <Field label="Medications" value={ctx.medications} wide />
          <Field label="Preferred hospital" value={ctx.preferredHospital} wide />
          <Field label="Primary doctor" value={ctx.primaryDoctor} />
          <Field label="Doctor phone" value={ctx.doctorPhone} />
          <Field label="History of falls" value={ctx.historyOfFalls} />
          <Field label="Blood type" value={ctx.bloodType} />
          <Field label="Insurance / ID" value={ctx.insuranceNotes} wide />
        </dl>
      </section>

      <section className="lw-doc-block">
        <h3>Instructions (handwrite if needed)</h3>
        <p className="lw-doc-hand-line">Nearest exit / assembly: ________________________________</p>
        <p className="lw-doc-hand-line">Other notes: ____________________________________________</p>
        <p className="lw-doc-hand-line">________________________________________________________</p>
      </section>

      {template.terms.length ? (
        <section className="lw-doc-block">
          <h3>Notes</h3>
          <ol className="lw-doc-terms">
            {template.terms.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ol>
        </section>
      ) : null}

      <section className="lw-doc-block lw-doc-sign">
        <h3>Prepared by</h3>
        <dl className="lw-doc-fields">
          <Field label="Assessor" value={ctx.assessorName} />
          <Field label="Assessment ID" value={ctx.assessmentId} />
          <Field label="Date prepared" value="" />
        </dl>
        <p className="lw-doc-sign-hint">
          Customer may initial that the sheet was posted in the home.
        </p>
        <div className="lw-doc-sign-grid">
          <div className="lw-doc-sign-box">
            <p className="lw-doc-sign-role">Customer / family</p>
            <div className="lw-doc-sign-line" aria-hidden="true" />
            <p className="lw-doc-sign-caption">Posted / received</p>
          </div>
          <div className="lw-doc-sign-box">
            <p className="lw-doc-sign-role">Assessor</p>
            <div className="lw-doc-sign-line" aria-hidden="true" />
            <p className="lw-doc-sign-caption">Confirmed posted</p>
          </div>
        </div>
      </section>

      <footer className="lw-doc-foot">
        {withPublicBrand("LiveWell360 Hyderabad pilot · Emergency Information Sheet · template")}{" "}
        {CUSTOMER_DOC_TEMPLATE_VERSION} · catalog EMG-001
      </footer>
    </article>
  );
}

function PrintConsentForm({
  template,
  ctx,
}: {
  template: CustomerDocTemplate;
  ctx: CustomerDocFillContext;
}) {
  return (
    <article className="lw-doc-form" data-form={template.code}>
      <header className="lw-doc-form-head">
        <div className="lw-doc-form-head-row">
          <p className="lw-doc-brand">{publicBrandName()}</p>
          <p className="lw-doc-form-code">{template.code}</p>
        </div>
        <h2>{template.title}</h2>
        <p className="lw-doc-packet">{PACKET_LABELS[template.packet]}</p>
      </header>

      <section className="lw-doc-block">
        <h3>Customer information</h3>
        <dl className="lw-doc-fields">
          <Field label="Customer name" value={ctx.customerName} wide />
          <Field label="Elder / resident name" value={ctx.elderName} wide />
          <Field label="Address" value={ctx.address} wide />
          <Field label="Phone" value={ctx.phone} />
          <Field label="Assessment ID" value={ctx.assessmentId} />
          {template.code === "LW_HEALTH_EMERGENCY_AUTH" ? (
            <Field label="Emergency contact" value={ctx.emergencyContact} wide />
          ) : null}
        </dl>
      </section>

      <section className="lw-doc-block">
        <h3>Terms</h3>
        <ol className="lw-doc-terms">
          {template.terms.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ol>
      </section>

      <section className="lw-doc-block lw-doc-sign">
        <h3>Wet signatures</h3>
        <p className="lw-doc-sign-hint">
          Sign in ink. Leave blank lines empty for handwritten signature and date.
        </p>
        <div className="lw-doc-sign-grid">
          <div className="lw-doc-sign-box">
            <p className="lw-doc-sign-role">Customer</p>
            <div className="lw-doc-sign-line" aria-hidden="true" />
            <p className="lw-doc-sign-caption">Signature</p>
            <div className="lw-doc-sign-line lw-doc-sign-line-short" aria-hidden="true" />
            <p className="lw-doc-sign-caption">Date</p>
          </div>
          <div className="lw-doc-sign-box">
            <p className="lw-doc-sign-role">Assessor — {ctx.assessorName}</p>
            <div className="lw-doc-sign-line" aria-hidden="true" />
            <p className="lw-doc-sign-caption">Signature</p>
            <div className="lw-doc-sign-line lw-doc-sign-line-short" aria-hidden="true" />
            <p className="lw-doc-sign-caption">Date</p>
          </div>
        </div>
      </section>

      <footer className="lw-doc-foot">
        {withPublicBrand(
          `LiveWell360 Hyderabad pilot · template ${CUSTOMER_DOC_TEMPLATE_VERSION} · paper signature then scan into LiveWell360 · counsel review required before production`,
        )}
      </footer>
    </article>
  );
}

function PrintForm({
  template,
  ctx,
}: {
  template: CustomerDocTemplate;
  ctx: CustomerDocFillContext;
}) {
  if (template.kind === "emergency_info_sheet" || template.code === "LW_EMERGENCY_INFO_SHEET") {
    return <PrintEmergencyInfoSheet template={template} ctx={ctx} />;
  }
  return <PrintConsentForm template={template} ctx={ctx} />;
}

export default function AssessmentDocumentsPage() {
  return (
    <Suspense
      fallback={
        <div className="home-safety-app">
          <main className="home-safety-main">
            <p className="muted">Loading documents…</p>
          </main>
        </div>
      }
    >
      <AssessmentDocumentsPageContent />
    </Suspense>
  );
}

function AssessmentDocumentsPageContent() {
  const params = useParams();
  const searchParams = useSearchParams();
  const id = String(params.id);
  const formFocus = searchParams.get("form");

  const [draft, setDraft] = useState<HomeSafetyAssessment | null>(null);
  const [missing, setMissing] = useState(false);
  const [packetFilter, setPacketFilter] = useState<CustomerDocPacket | "all" | "eis">(
    formFocus === "LW_EMERGENCY_INFO_SHEET" ? "eis" : "all",
  );

  useEffect(() => {
    let cancelled = false;
    async function load() {
      let found = getAssessment(id);
      if (!found) found = hydratePendingAssessment(id);
      const merged = await loadAssessmentMerged(id);
      if (merged) found = merged;
      if (cancelled) return;
      if (!found) {
        setMissing(true);
        setDraft(null);
      } else {
        setMissing(false);
        setDraft(found);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    if (!draft) return;
    const prev = document.title;
    document.title = withPublicBrand(`LiveWell360 document pack — ${draft.id}`);
    return () => {
      document.title = prev;
    };
  }, [draft]);

  const ctx = useMemo(
    () => (draft ? fillContextFromAssessment(draft) : null),
    [draft],
  );

  const forms = useMemo(() => {
    if (packetFilter === "eis") {
      return CUSTOMER_DOC_TEMPLATES.filter((t) => t.code === "LW_EMERGENCY_INFO_SHEET");
    }
    if (packetFilter === "all") return CUSTOMER_DOC_TEMPLATES;
    return CUSTOMER_DOC_TEMPLATES.filter((t) => t.packet === packetFilter);
  }, [packetFilter]);

  if (missing) {
    return (
      <div className="home-safety-app">
        <main className="home-safety-main">
          <p className="error-text">Assessment not found.</p>
          <a href="/kushalaya">Back</a>
        </main>
      </div>
    );
  }

  if (!draft || !ctx) {
    return (
      <div className="home-safety-app">
        <main className="home-safety-main">
          <p className="muted">Loading documents…</p>
        </main>
      </div>
    );
  }

  const eisCheck = emergencyInfoSheetChecklist(ctx);

  return (
    <div className="home-safety-app lw-doc-page">
      <header className="home-safety-header lw-doc-screen-only">
        <div className="home-safety-header-top">
          <a
            href={`/kushalaya/assess/${encodeURIComponent(id)}`}
            className="home-safety-back"
          >
            ← Assessment
          </a>
          <button
            type="button"
            className="primary"
            onClick={() => window.print()}
          >
            Print
          </button>
        </div>
        <h1>Customer document pack</h1>
        <p className="home-safety-subtitle">
          {ctx.elderName} · {draft.id}
        </p>
      </header>

      <main className="home-safety-main lw-doc-main">
        <div className="lw-doc-screen-only card home-safety-section lw-doc-toolbar">
          <label htmlFor="packet-filter">Forms to print</label>
          <select
            id="packet-filter"
            value={packetFilter}
            onChange={(e) =>
              setPacketFilter(e.target.value as CustomerDocPacket | "all" | "eis")
            }
          >
            <option value="all">All packets</option>
            <option value="eis">Emergency Information Sheet only</option>
            {ALL_PACKETS.map((p) => (
              <option key={p} value={p}>
                {PACKET_LABELS[p]}
              </option>
            ))}
          </select>
          {!eisCheck.ready ? (
            <p className="error-text" style={{ marginTop: "0.75rem" }}>
              Emergency sheet incomplete — fill on intake: {eisCheck.missing.join("; ")}
            </p>
          ) : (
            <p className="success" style={{ marginTop: "0.75rem" }}>
              Emergency Information Sheet fields look complete — ready to print and post.
            </p>
          )}
          <p className="muted" style={{ marginTop: "0.75rem" }}>
            Use <strong>Print</strong> or Ctrl/Cmd+P. After posting the sheet, upload a photo under
            Customer documents (type: Emergency Information Sheet).
          </p>
          <button
            type="button"
            className="primary lw-doc-toolbar-print"
            onClick={() => window.print()}
          >
            Print
          </button>
        </div>

        <div className="lw-doc-print-root">
          {forms.map((template) => (
            <PrintForm key={template.code} template={template} ctx={ctx} />
          ))}
        </div>

        <div className="lw-doc-screen-only">
          <CustomerDocumentsPanel assessment={draft} />
        </div>
      </main>
    </div>
  );
}
