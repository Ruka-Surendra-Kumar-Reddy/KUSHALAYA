"use client";

import { useState } from "react";
import { ChoiceWithOther } from "@/components/ChoiceWithOther";
import { saveAssessmentClient, type AssessmentClient, type ClientDetails, type HomeLocation } from "@/lib/jobs";
import { requireLocation, withTimeout } from "@/lib/visit-location";

type Group = "beneficiary" | "home" | "contact";
const FIELDS: {
  key: keyof ClientDetails;
  label: string;
  group: Group;
  type?: string;
  required?: boolean;
  wide?: boolean;
  hint?: string;
}[] = [
  { key: "first_name", label: "First name", group: "beneficiary", required: true },
  { key: "last_name", label: "Last name", group: "beneficiary" },
  { key: "gender", label: "Gender", group: "beneficiary", required: true },
  { key: "date_of_birth", label: "Date of birth", group: "beneficiary", type: "date" },
  { key: "phone", label: "Phone", group: "beneficiary", type: "tel", hint: "If they use one", wide: true },
  { key: "address", label: "House / street", group: "home", required: true, wide: true },
  { key: "area", label: "Area / locality", group: "home", wide: true },
  { key: "city", label: "City", group: "home", required: true },
  { key: "pincode", label: "PIN code", group: "home", required: true },
  { key: "emergency_contact_name", label: "Name", group: "contact", required: true },
  { key: "emergency_contact_phone", label: "Phone", group: "contact", type: "tel", required: true },
  { key: "contact_relation", label: "Relation", group: "contact" },
  { key: "contact_email", label: "Email", group: "contact", type: "email" },
];
const GROUPS: { id: Group; title: string; sub: string }[] = [
  { id: "beneficiary", title: "Beneficiary details", sub: "The person receiving care" },
  { id: "home", title: "Home address", sub: "Where the assessment is done" },
  { id: "contact", title: "Contact person details", sub: "Family member we call for SOS and send reports to" },
];
const RELATIONS = ["Son", "Daughter", "Spouse", "Son-in-law", "Daughter-in-law", "Relative", "Friend", "Other"];
const BEN_RELATIONS = ["Spouse", "Sibling", "Parent", "Relative", "Other"];
type Beneficiary = { name: string; gender: string; date_of_birth: string; relation: string; phone: string };
const EMPTY_BEN: Beneficiary = { name: "", gender: "", date_of_birth: "", relation: "", phone: "" };
const GENDERS = [
  { value: "female", label: "Female" },
  { value: "male", label: "Male" },
  { value: "other", label: "Other" },
];

/** Address from map coordinates (OpenStreetMap). Optional: never blocks the step. */
async function reverseGeocode(lat: number, lng: number) {
  try {
    const res = await withTimeout(
      fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lng}&accept-language=en`),
      6000,
    );
    if (!res.ok) return null;
    const j = (await res.json()) as { display_name?: string; address?: Record<string, string> };
    const a = j.address || {};
    return {
      label: j.display_name || "",
      street: [a.house_number, a.road].filter(Boolean).join(", "),
      area: a.suburb || a.neighbourhood || a.village || "",
      city: a.city || a.town || a.county || a.state_district || "",
      pincode: (a.postcode || "").replace(/\s/g, ""),
    };
  } catch {
    return null;
  }
}

function age(dob: string) {
  const d = new Date(dob);
  if (Number.isNaN(d.getTime())) return "";
  const now = new Date();
  let y = now.getFullYear() - d.getFullYear();
  if (now < new Date(now.getFullYear(), d.getMonth(), d.getDate())) y -= 1;
  return `${y} yrs`;
}

/**
 * Step 1 of every assessment: the client's details (full form for a lead or when
 * anything is missing; a review card for a known client / reassessment) and the
 * home location — auto-detected on Next by default, or entered by hand.
 */
export function ClientStep({
  jobId,
  client,
  onSaved,
}: {
  jobId: number;
  client: AssessmentClient;
  onSaved: (c: AssessmentClient) => void;
}) {
  const [d, setD] = useState<ClientDetails>(client.details);
  // More people in the same home receiving care (spouse …), besides the main beneficiary.
  const [bens, setBens] = useState<Beneficiary[]>((client.beneficiaries as Beneficiary[]) ?? []);
  const setBen = (n: number, k: keyof Beneficiary, v: string) =>
    setBens((list) => list.map((b, i) => (i === n ? { ...b, [k]: v } : b)));
  const [editing, setEditing] = useState(client.is_lead || client.missing.length > 0);
  const [mode, setMode] = useState<"auto" | "manual">("auto");
  const [busy, setBusy] = useState<"" | "locating" | "saving">("");
  const [msg, setMsg] = useState("");
  // Next tapped with gaps: those boxes turn red with "Required" under them.
  const [tried, setTried] = useState(false);

  const set = (k: keyof ClientDetails) => (e: { target: { value: string } }) => setD((v) => ({ ...v, [k]: e.target.value }));
  const missing = FIELDS.filter((f) => f.required && !String(d[f.key] || "").trim());
  const benMissing = bens.some((b) => !b.name.trim() && Boolean(b.gender || b.relation || b.date_of_birth || b.phone));
  const pinBad = Boolean(d.pincode.trim()) && !/^\d{6}$/.test(d.pincode.trim());
  const errorOf = (k: keyof ClientDetails): string => {
    if (!tried) return "";
    if (missing.some((f) => f.key === k)) return "Required";
    if (k === "pincode" && pinBad) return "6 digits";
    return "";
  };
  const showFirstBad = () =>
    window.setTimeout(() => {
      const el = document.querySelector<HTMLElement>(".fa-client-form label.is-bad input, .fa-client-form label.is-bad select");
      el?.scrollIntoView({ block: "center" });
      el?.focus({ preventScroll: true });
    }, 30);

  async function next() {
    setMsg("");
    if (missing.length || pinBad || benMissing) {
      setEditing(true);
      setTried(true);
      setMsg(missing.length || benMissing ? "Fill in the boxes marked in red." : "PIN code must be 6 digits.");
      showFirstBad();
      return;
    }
    let location: HomeLocation = { mode: "manual" };
    if (mode === "auto") {
      setBusy("locating");
      try {
        const p = await requireLocation();
        const place = await reverseGeocode(p.latitude, p.longitude);
        location = { mode: "auto", latitude: p.latitude, longitude: p.longitude, accuracy: p.accuracy, label: place?.label || "" };
      } catch {
        setBusy("");
        setMsg("Couldn't detect the location. Allow location access and tap Next again, or choose “Enter manually”.");
        return;
      }
    }
    setBusy("saving");
    try {
      onSaved(
        await saveAssessmentClient(jobId, { details: d, location, beneficiaries: bens.filter((b) => b.name.trim()) }),
      );
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Could not save the details");
    } finally {
      setBusy("");
    }
  }

  async function fillFromMap() {
    setMsg("");
    setBusy("locating");
    try {
      const p = await requireLocation();
      const place = await reverseGeocode(p.latitude, p.longitude);
      if (!place) {
        setMsg("Location found, but no address for it. Type the address.");
        return;
      }
      setD((v) => ({
        ...v,
        address: v.address || place.street,
        area: v.area || place.area,
        city: v.city || place.city,
        pincode: v.pincode || place.pincode,
      }));
      setEditing(true);
    } catch {
      setMsg("Couldn't detect the location. Allow location access, or type the address.");
    } finally {
      setBusy("");
    }
  }

  const title = client.is_lead ? "New client — full details" : client.reassessment ? "Reassessment — check the details" : "Check the client’s details";

  return (
    <section className="fa-card fa-client">
      <p className="fa-cat">Step 1 of 3 · Client info</p>
      <h1 className="fa-q">{title}</h1>

      {editing ? (
        <div className="fa-client-groups">
          {GROUPS.map((g) => (
            <fieldset key={g.id} className="fa-group">
              <legend>
                {g.title}
                <small>{g.sub}</small>
              </legend>
              <div className="fa-client-form">
                {FIELDS.filter((f) => f.group === g.id).map((f) => (
                  <label
                    key={f.key}
                    className={[f.wide ? "is-wide" : "", errorOf(f.key) ? "is-bad" : ""].join(" ").trim() || undefined}
                  >
                    <span>
                      {f.label}
                      {f.required ? <em aria-hidden="true"> *</em> : null}
                      {f.hint ? <i className="fa-hint"> · {f.hint}</i> : null}
                    </span>
                    {f.key === "contact_relation" ? (
                      <ChoiceWithOther
                        options={RELATIONS.map((r) => ({ value: r.toLowerCase(), label: r }))}
                        value={d[f.key] || ""}
                        onChange={(v) => setD((x) => ({ ...x, contact_relation: v }))}
                        otherPlaceholder="Relation, e.g. Neighbour"
                        invalid={Boolean(errorOf(f.key))}
                      />
                    ) : f.key === "gender" ? (
                      <select value={d[f.key] || ""} onChange={set(f.key)} aria-invalid={Boolean(errorOf(f.key))}>
                        <option value="">Choose…</option>
                        {(f.key === "gender" ? GENDERS : RELATIONS.map((r) => ({ value: r.toLowerCase(), label: r }))).map((g) => (
                          <option key={g.value} value={g.value}>
                            {g.label}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type={f.type || "text"}
                        value={d[f.key] || ""}
                        onChange={set(f.key)}
                        required={f.required}
                        aria-invalid={Boolean(errorOf(f.key))}
                        inputMode={f.key === "pincode" ? "numeric" : undefined}
                        maxLength={f.key === "pincode" ? 6 : undefined}
                      />
                    )}
                    {errorOf(f.key) ? <small className="fa-field-err">{errorOf(f.key)}</small> : null}
                  </label>
                ))}
                {g.id === "home" ? (
                  <button type="button" className="fa-skipped-link fa-client-map" onClick={() => void fillFromMap()} disabled={!!busy}>
                    Fill the address from my location
                  </button>
                ) : null}
              </div>
              {g.id === "beneficiary" ? (
                <div className="fa-bens">
                  {bens.map((b, n) => (
                    <div key={n} className="fa-ben">
                      <div className="fa-ben-head">
                        <strong>Beneficiary {n + 2}</strong>
                        <button type="button" className="fa-ben-x" onClick={() => setBens((l) => l.filter((_, i) => i !== n))}>
                          Remove
                        </button>
                      </div>
                      <div className="fa-client-form">
                        <label className={tried && !b.name.trim() ? "is-wide is-bad" : "is-wide"}>
                          <span>
                            Full name<em aria-hidden="true"> *</em>
                          </span>
                          <input value={b.name} onChange={(e) => setBen(n, "name", e.target.value)} />
                          {tried && !b.name.trim() ? <small className="fa-field-err">Required</small> : null}
                        </label>
                        <label>
                          <span>Relation to beneficiary 1</span>
                          <ChoiceWithOther
                            options={BEN_RELATIONS.map((r) => ({ value: r.toLowerCase(), label: r }))}
                            value={b.relation}
                            onChange={(v) => setBen(n, "relation", v)}
                            otherPlaceholder="Relation, e.g. Cousin"
                          />
                        </label>
                        <label>
                          <span>Gender</span>
                          <select value={b.gender} onChange={(e) => setBen(n, "gender", e.target.value)}>
                            <option value="">Choose…</option>
                            {GENDERS.map((x) => (
                              <option key={x.value} value={x.value}>
                                {x.label}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          <span>Date of birth</span>
                          <input type="date" value={b.date_of_birth} onChange={(e) => setBen(n, "date_of_birth", e.target.value)} />
                        </label>
                        <label>
                          <span>
                            Phone<i className="fa-hint"> · If they use one</i>
                          </span>
                          <input type="tel" value={b.phone} onChange={(e) => setBen(n, "phone", e.target.value)} />
                        </label>
                      </div>
                    </div>
                  ))}
                  <button type="button" className="fa-add-ben" onClick={() => setBens((l) => [...l, { ...EMPTY_BEN }])}>
                    + Add beneficiary
                  </button>
                </div>
              ) : null}
            </fieldset>
          ))}
        </div>
      ) : (
        <div className="fa-client-review">
          <dl>
            <div>
              <dt>Beneficiary</dt>
              <dd>
                {[d.first_name, d.last_name].filter(Boolean).join(" ")}
                {d.date_of_birth ? ` · ${age(d.date_of_birth)}` : ""}
                {d.gender ? ` · ${GENDERS.find((g) => g.value === d.gender)?.label ?? d.gender}` : ""}
                {d.phone ? ` · ${d.phone}` : ""}
              </dd>
            </div>
            {bens.map((b, n) => (
              <div key={n}>
                <dt>Beneficiary {n + 2}</dt>
                <dd>
                  {b.name}
                  {b.relation ? ` · ${b.relation}` : ""}
                  {b.date_of_birth ? ` · ${age(b.date_of_birth)}` : ""}
                </dd>
              </div>
            ))}
            <div>
              <dt>Home address</dt>
              <dd>{[d.address, d.area, d.city, d.pincode].filter(Boolean).join(", ")}</dd>
            </div>
            <div>
              <dt>Contact person</dt>
              <dd>
                {d.emergency_contact_name}
                {d.contact_relation ? ` (${d.contact_relation})` : ""} · {d.emergency_contact_phone}
                {d.contact_email ? ` · ${d.contact_email}` : ""}
              </dd>
            </div>
          </dl>
          <button type="button" className="cg-btn is-ghost" onClick={() => setEditing(true)}>
            Edit details
          </button>
        </div>
      )}

      <h2 className="fa-q is-small">Home location on the map</h2>
      <div className="fa-loc" role="radiogroup" aria-label="Home location">
        {(
          [
            {
              v: "auto",
              l: "Auto-detect",
              s: "Uses this phone’s location when you tap Next",
              icon: <path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21Zm0-8.5a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" />,
            },
            {
              v: "manual",
              l: "Enter manually",
              s: "Use the address typed above",
              icon: <path d="M4 20h4l10.5-10.5a2.1 2.1 0 0 0-4-4L4 16v4Zm9.5-13.5 4 4" />,
            },
          ] as const
        ).map((o) => (
          <button
            key={o.v}
            type="button"
            role="radio"
            aria-checked={mode === o.v}
            className={mode === o.v ? "fa-loc-opt is-on" : "fa-loc-opt"}
            onClick={() => setMode(o.v)}
          >
            <svg className="fa-loc-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              {o.icon}
            </svg>
            <span className="fa-loc-text">
              <strong>{o.l}</strong>
              <small>{o.s}</small>
            </span>
            <span className="fa-loc-tick" aria-hidden="true">
              {mode === o.v ? "✓" : ""}
            </span>
          </button>
        ))}
      </div>
      {client.location?.label ? <p className="fa-client-last">Last saved: {client.location.label}</p> : null}

      {msg ? (
        <p className="cg-note is-warn" role="alert">
          {msg}
        </p>
      ) : null}
      <button type="button" className="cg-btn fa-next" onClick={() => void next()} disabled={!!busy}>
        {busy === "locating" ? "Detecting location…" : busy === "saving" ? "Saving…" : "Next: assessment"}
      </button>
    </section>
  );
}
