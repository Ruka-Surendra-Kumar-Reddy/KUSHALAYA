"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BackLink } from "@/components/ops/PageActions";
import { api, } from "@/lib/api";
import { isAdmin as isAdminUser } from "@/lib/roles";

type Area = { name: string; pincodes: string[]; manager_user_id: number | null };
type Testimonial = { quote: string; name: string; place: string };
type Company = {
  legal_name: string;
  address: string;
  gstin: string;
  grievance_name: string;
  grievance_email: string;
  grievance_phone: string;
};
type Site = {
  city: string;
  areas: Area[];
  assessment_price_paise: number | null;
  assessment_price_label: string;
  trial: { enabled: boolean; text: string };
  testimonials: Testimonial[];
  company: Company;
};
type Manager = { id: number; first_name: string; last_name: string };

/** Area rows are edited with pincodes as one comma-separated string. */
type AreaForm = { name: string; pincodes: string; manager_user_id: number | null };

/**
 * Settings → Website (FIX 107/108): service areas, the assessment price, the
 * first-month trial banner, real testimonials and the company details in the
 * site footer. The WhatsApp button uses Settings → Notifications → Care team contact.
 */
export default function WebsiteSettingsPage() {
  const isAdmin = isAdminUser();
  const [site, setSite] = useState<Site | null>(null);
  const [areas, setAreas] = useState<AreaForm[]>([]);
  const [price, setPrice] = useState("");
  const [managers, setManagers] = useState<Manager[]>([]);
  const [status, setStatus] = useState("");

  function load(s: Site) {
    setSite(s);
    setAreas(s.areas.map((a) => ({ ...a, pincodes: a.pincodes.join(", ") })));
    setPrice(s.assessment_price_paise ? String(s.assessment_price_paise / 100) : "");
  }

  useEffect(() => {
    api<Site>("/api/v1/site-settings").then(load).catch((e) => setStatus(e instanceof Error ? e.message : "Could not load"));
    api<Manager[]>("/api/v1/team/managers").then(setManagers).catch(() => setManagers([]));
  }, []);

  async function save(body: Record<string, unknown>, note: string) {
    setStatus("Saving…");
    try {
      load(await api<Site>("/api/v1/site-settings", { method: "PUT", body: JSON.stringify(body) }));
      setStatus(note);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Could not save");
    }
  }

  if (!site) {
    return (
      <div className="ks-frame">
        <header className="ks-head">
          <BackLink href="/settings" label="Settings" />
          <h1>Website</h1>
        </header>
        <p className="muted">{status || "Loading…"}</p>
      </div>
    );
  }

  const ro = !isAdmin;
  const setCompany = (k: keyof Company, v: string) => setSite({ ...site, company: { ...site.company, [k]: v } });
  const setT = (i: number, k: keyof Testimonial, v: string) =>
    setSite({ ...site, testimonials: site.testimonials.map((t, j) => (j === i ? { ...t, [k]: v } : t)) });

  return (
    <div className="ks-frame">
      <header className="ks-head">
        <BackLink href="/settings" label="Settings" />
        <h1>Website</h1>
        <p className="muted">
          What the public site shows. The WhatsApp and call buttons use the care team numbers in{" "}
          <Link href="/settings/notifications" className="ks-link">Notifications &amp; SOS</Link>.
        </p>
      </header>
      {status ? <p className="muted" role="status">{status}</p> : null}

      <section className="card">
        <h2>Service areas</h2>
        <p className="muted">
          The enquiry form checks the PIN code: listed ones see &ldquo;We serve your area&rdquo;, others &ldquo;We&rsquo;ll call to
          check&rdquo;. A manager set on an area becomes the owner of enquiries from it.{" "}
          <Link href="/kushalaya/enquiries" className="ks-link">See enquiries and where they came from</Link>.
        </p>
        {areas.map((a, i) => (
          <div key={i} className="ko-area-row">
            <label>
              Area
              <input value={a.name} disabled={ro} onChange={(e) => setAreas(areas.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} />
            </label>
            <label>
              PIN codes (comma separated)
              <input value={a.pincodes} disabled={ro} onChange={(e) => setAreas(areas.map((x, j) => (j === i ? { ...x, pincodes: e.target.value } : x)))} />
            </label>
            <label>
              Manager
              <select
                value={a.manager_user_id ?? ""}
                disabled={ro}
                onChange={(e) =>
                  setAreas(areas.map((x, j) => (j === i ? { ...x, manager_user_id: e.target.value ? Number(e.target.value) : null } : x)))
                }
              >
                <option value="">Nobody</option>
                {managers.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.first_name} {m.last_name}
                  </option>
                ))}
              </select>
            </label>
            {ro ? <span /> : (
              <button type="button" className="secondary ko-btn-danger" onClick={() => setAreas(areas.filter((_, j) => j !== i))}>
                Remove
              </button>
            )}
          </div>
        ))}
        {areas.length === 0 ? <p className="muted">No areas yet — every enquiry hears &ldquo;We&rsquo;ll call to check&rdquo;.</p> : null}
        {ro ? null : (
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button
              type="button"
              className="ks-btn-secondary"
              onClick={() => setAreas([...areas, { name: "", pincodes: "", manager_user_id: null }])}
            >
              + Add area
            </button>
            <button
              type="button"
              onClick={() =>
                void save(
                  { areas: areas.map((a) => ({ ...a, pincodes: a.pincodes.split(/[\s,;]+/).filter(Boolean) })) },
                  "Service areas saved.",
                )
              }
            >
              Save areas
            </button>
          </div>
        )}
      </section>

      <section className="card">
        <h2>Home assessment price</h2>
        <p className="muted">
          Shown on the site and the KushCare Discovery form. Leave empty (or 0) for the default: Free, with no payment step. With a
          price, a family who picks a visit slot can pay online (Razorpay). Now showing:{" "}
          <strong>{site.assessment_price_label}</strong>
        </p>
        <label>
          Price in ₹
          <input type="number" min={0} step={1} value={price} disabled={ro} onChange={(e) => setPrice(e.target.value)} />
        </label>
        {ro ? null : (
          <button
            type="button"
            onClick={() =>
              void save(
                { assessment_price_paise: price.trim() ? Math.round(Number(price) * 100) : null },
                "Price saved.",
              )
            }
          >
            Save price
          </button>
        )}
      </section>

      <section className="card">
        <h2>First month trial banner</h2>
        <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <input
            type="checkbox"
            checked={site.trial.enabled}
            disabled={ro}
            onChange={(e) => setSite({ ...site, trial: { ...site.trial, enabled: e.target.checked } })}
          />
          Show the banner on every page of the website
        </label>
        <label>
          Banner text
          <input value={site.trial.text} disabled={ro} onChange={(e) => setSite({ ...site, trial: { ...site.trial, text: e.target.value } })} />
        </label>
        {ro ? null : (
          <button type="button" onClick={() => void save({ trial: site.trial }, "Trial banner saved.")}>
            Save banner
          </button>
        )}
      </section>

      <section className="card">
        <h2>Testimonials</h2>
        <p className="muted">
          Only real words from real families, with their permission. The section is hidden on the site until you add one.
        </p>
        {site.testimonials.map((t, i) => (
          <div key={i} style={{ display: "grid", gap: "0.4rem", marginBottom: "0.75rem" }}>
            <label>
              What they said
              <textarea rows={3} value={t.quote} disabled={ro} onChange={(e) => setT(i, "quote", e.target.value)} />
            </label>
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
              <label>
                Name as shown (e.g. &ldquo;Ravi K.&rdquo;)
                <input value={t.name} disabled={ro} onChange={(e) => setT(i, "name", e.target.value)} />
              </label>
              <label>
                Place or relation
                <input value={t.place} disabled={ro} onChange={(e) => setT(i, "place", e.target.value)} />
              </label>
              {ro ? null : (
                <button type="button" onClick={() => setSite({ ...site, testimonials: site.testimonials.filter((_, j) => j !== i) })}>
                  Remove
                </button>
              )}
            </div>
          </div>
        ))}
        {ro ? null : (
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button type="button" onClick={() => setSite({ ...site, testimonials: [...site.testimonials, { quote: "", name: "", place: "" }] })}>
              Add testimonial
            </button>
            <button type="button" onClick={() => void save({ testimonials: site.testimonials }, "Testimonials saved.")}>
              Save testimonials
            </button>
          </div>
        )}
      </section>

      <section className="card">
        <h2>Company details in the site footer</h2>
        <p className="muted">
          {ro ? null : (
            <>
              Empty fields fall back to <Link href="/settings/business" className="ks-link">Business details</Link>.{" "}
            </>
          )}
          Each line appears only once it has a value.
        </p>
        <div style={{ display: "grid", gap: "0.5rem", gridTemplateColumns: "1fr 1fr" }}>
          <label>
            Legal name
            <input value={site.company.legal_name} disabled={ro} onChange={(e) => setCompany("legal_name", e.target.value)} />
          </label>
          <label>
            GSTIN
            <input value={site.company.gstin} disabled={ro} onChange={(e) => setCompany("gstin", e.target.value)} />
          </label>
          <label style={{ gridColumn: "1 / -1" }}>
            Registered address
            <input value={site.company.address} disabled={ro} onChange={(e) => setCompany("address", e.target.value)} />
          </label>
          <label>
            Grievance officer
            <input value={site.company.grievance_name} disabled={ro} onChange={(e) => setCompany("grievance_name", e.target.value)} />
          </label>
          <label>
            Grievance email
            <input value={site.company.grievance_email} disabled={ro} onChange={(e) => setCompany("grievance_email", e.target.value)} />
          </label>
          <label>
            Grievance phone
            <input value={site.company.grievance_phone} disabled={ro} onChange={(e) => setCompany("grievance_phone", e.target.value)} />
          </label>
        </div>
        {ro ? null : (
          <button type="button" style={{ marginTop: "0.5rem" }} onClick={() => void save({ company: site.company }, "Company details saved.")}>
            Save company details
          </button>
        )}
      </section>
    </div>
  );
}
