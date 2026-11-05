"use client";

import { CaregiverClients } from "@/components/ops/CaregiverClients";
import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, getStoredAuth } from "@/lib/api";
import { canManageUsers, canViewTeam } from "@/lib/auth";
import { Flash } from "@/components/Flash";
import { PageHeader } from "@/components/PageHeader";
import { OpsModal } from "@/components/ops/OpsModal";
import { StaffDocuments } from "@/components/ops/StaffDocuments";
import type { User } from "@/lib/types";
import "@/components/ops/team.css";
import { plural } from "@/lib/run-sheet";

type Staff = User & { status?: string; phone?: string | null };
type Manager = {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  clients?: number;
  caregivers?: number;
};
type TeamCaregiver = {
  id: number;
  first_name: string;
  last_name: string;
  phone: string | null;
  email?: string | null;
  status: string;
  manager_user_id: number | null;
  login_email: string | null;
  login_user_id?: number | null;
  login_status?: string | null;
};

const ROLE_LABEL: Record<string, string> = {
  SYSTEM_ADMIN: "Owner", // the platform super-admin is the owner
  TENANT_ADMIN: "Owner", // the business owner's account (admin rights)
  CARE_MANAGER: "Care manager",
  VIEWER: "View-only",
};

const EMPTY_FORM = {
  role: "CAREGIVER",
  first_name: "",
  last_name: "",
  phone: "",
  email: "",
  password: "",
  manager_user_id: "",
};

type Mode = "edit" | "role" | "password" | "deactivate" | "left";
type Panel = { kind: "staff" | "cg"; id: number; mode: Mode } | null;
const EMPTY_PANEL_FORM = { first_name: "", last_name: "", email: "", phone: "", role: "", password: "", reassign: "" };

function generatePassword(): string {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789";
  const bytes = new Uint32Array(12);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => chars[b % chars.length]).join("");
}

const fullName = (p: { first_name: string; last_name: string }) => `${p.first_name} ${p.last_name}`.trim();

/** Team: admins, managers, view-only users and caregivers, and who each caregiver reports to. */
export default function UsersPage() {
  const router = useRouter();
  const auth = getStoredAuth();
  const isAdmin = canManageUsers(auth?.role || "");
  const canEditCaregivers = isAdmin || auth?.role === "CARE_MANAGER";
  const [staff, setStaff] = useState<Staff[]>([]);
  const [managers, setManagers] = useState<Manager[]>([]);
  const [caregivers, setCaregivers] = useState<TeamCaregiver[]>([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function sendSetupLink(userId: number, who: string) {
    try {
      const res = await api<{ sent: Record<string, string> }>(`/api/v1/users/${userId}/send-setup-link`, { method: "POST" });
      const via = Object.entries(res.sent || {}).map(([k, v]) => `${k}: ${v}`).join(", ") || "no channel configured";
      setMessage(`Setup link sent to ${who} (${via}).`);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not send the setup link");
    }
  }
  const [menu, setMenu] = useState<string | null>(null);
  const [docsFor, setDocsFor] = useState<{ type: "staff" | "caregiver"; id: number; name: string } | null>(null);
  const [panel, setPanel] = useState<Panel>(null);
  const [pf, setPf] = useState(EMPTY_PANEL_FORM);
  const [showPw, setShowPw] = useState(false);
  const [caseload, setCaseload] = useState<{ clients: number; caregivers: number } | null>(null);
  const [teamFilter, setTeamFilter] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");

  const load = useCallback(async () => {
    const [u, m, c] = await Promise.all([
      api<Staff[]>("/api/v1/users"),
      api<Manager[]>("/api/v1/team/managers"),
      api<TeamCaregiver[]>("/api/v1/team/caregivers"),
    ]);
    setStaff(u.filter((x) => x.role in ROLE_LABEL));
    setManagers(m);
    setCaregivers(c);
  }, []);

  useEffect(() => {
    if (!canViewTeam(auth?.role || "")) {
      router.replace("/unauthorized");
      return;
    }
    load().catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [auth?.role, router, load]);

  useEffect(() => {
    if (!menu) return;
    const close = () => setMenu(null);
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setMenu(null);
      document.querySelector<HTMLButtonElement>(`[data-menu-btn="${menu}"]`)?.focus();
    };
    // Focus the first item when a menu opens (keyboard users land inside it).
    document.querySelector<HTMLButtonElement>(".tm-menu [role=menuitem]")?.focus();
    document.addEventListener("click", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("click", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [menu]);

  const managerName = (id: number | null) => {
    const m = managers.find((x) => x.id === id);
    return m ? fullName(m) : "—";
  };
  const managerStats = (id: number) => managers.find((x) => x.id === id);

  function openPanel(kind: "staff" | "cg", id: number, mode: Mode) {
    setMenu(null);
    setShowPw(false);
    setCaseload(null);
    const person = kind === "staff" ? staff.find((s) => s.id === id) : caregivers.find((c) => c.id === id);
    setPf({
      ...EMPTY_PANEL_FORM,
      first_name: person?.first_name || "",
      last_name: person?.last_name || "",
      email: kind === "staff" ? (person as Staff)?.email || "" : (person as TeamCaregiver)?.email || "",
      phone: (kind === "cg" ? (person as TeamCaregiver)?.phone : (person as Staff)?.phone) || "",
      role: kind === "staff" ? ((person as Staff)?.role === "SYSTEM_ADMIN" ? "TENANT_ADMIN" : (person as Staff)?.role) : "",
    });
    setPanel({ kind, id, mode });
    const target = kind === "staff" ? (person as Staff) : null;
    if (target?.role === "CARE_MANAGER" && (mode === "deactivate" || mode === "role")) {
      api<{ clients: number; caregivers: number }>(`/api/v1/users/${id}/caseload`)
        .then(setCaseload)
        .catch(() => setCaseload(null));
    }
  }

  async function run(fn: () => Promise<unknown>, done: string) {
    setError("");
    setSaving(true);
    try {
      await fn();
      setMessage(done);
      setPanel(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save");
    } finally {
      setSaving(false);
    }
  }

  const needsReassign = caseload !== null && caseload.clients + caseload.caregivers > 0;
  const otherManagers = (id: number) => managers.filter((m) => m.id !== id);

  async function onPanelSubmit(e: FormEvent) {
    e.preventDefault();
    if (!panel) return;
    const reassign = pf.reassign ? Number(pf.reassign) : null;
    if (panel.kind === "staff") {
      const u = staff.find((s) => s.id === panel.id);
      const who = u ? fullName(u) : "User";
      if (panel.mode === "edit") {
        await run(
          () => api(`/api/v1/users/${panel.id}`, {
            method: "PATCH",
            body: JSON.stringify({ first_name: pf.first_name, last_name: pf.last_name, email: pf.email, phone: pf.phone.trim() || null }),
          }),
          `${who} updated.`,
        );
      } else if (panel.mode === "role") {
        await run(
          () => api(`/api/v1/users/${panel.id}`, {
            method: "PATCH",
            body: JSON.stringify({ role: pf.role, reassign_to_manager_id: reassign }),
          }),
          `${who} is now ${ROLE_LABEL[pf.role] || pf.role}.`,
        );
      } else if (panel.mode === "password") {
        await run(
          () => api(`/api/v1/users/${panel.id}/password`, { method: "POST", body: JSON.stringify({ password: pf.password }) }),
          `New password set for ${who}. Share it with them privately.`,
        );
      } else if (panel.mode === "deactivate") {
        await run(
          () => api(`/api/v1/users/${panel.id}/deactivate`, {
            method: "POST",
            body: JSON.stringify({ reassign_to_manager_id: reassign }),
          }),
          `${who} deactivated — they can no longer sign in.`,
        );
      }
      return;
    }
    const c = caregivers.find((x) => x.id === panel.id);
    const who = c ? fullName(c) : "Caregiver";
    if (panel.mode === "edit") {
      await run(
        () => api(`/api/v1/team/caregivers/${panel.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            first_name: pf.first_name,
            last_name: pf.last_name,
            phone: pf.phone || null,
            email: pf.email || null,
          }),
        }),
        `${who} updated.`,
      );
    } else if (panel.mode === "password" && c?.login_user_id) {
      await run(
        () => api(`/api/v1/users/${c.login_user_id}/password`, { method: "POST", body: JSON.stringify({ password: pf.password }) }),
        `New password set for ${who}. Share it with them privately.`,
      );
    } else if (panel.mode === "left") {
      await run(
        () => api(`/api/v1/team/caregivers/${panel.id}`, { method: "PATCH", body: JSON.stringify({ status: "INACTIVE" }) }),
        `${who} marked as left.`,
      );
    }
  }

  async function reactivate(u: Staff) {
    setMenu(null);
    await run(() => api(`/api/v1/users/${u.id}/reactivate`, { method: "POST" }), `${fullName(u)} can sign in again.`);
  }

  async function onAdd(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      if (form.role === "CAREGIVER") {
        await api("/api/v1/team/caregivers", {
          method: "POST",
          body: JSON.stringify({
            first_name: form.first_name,
            last_name: form.last_name,
            phone: form.phone || null,
            email: form.email || null,
            password: form.password || null,
            manager_user_id: form.manager_user_id ? Number(form.manager_user_id) : null,
          }),
        });
        setMessage(`${form.first_name} added. Book their visits on Schedule — the care manager runs each visit.`);
      } else {
        await api("/api/v1/users/invite", {
          method: "POST",
          body: JSON.stringify({
            email: form.email.trim().toLowerCase(),
            password: form.password,
            first_name: form.first_name,
            last_name: form.last_name,
            role: form.role,
            tenant_id: auth?.tenant_id,
            phone: form.phone.trim() || null,
          }),
        });
        setMessage(`${form.first_name} added as ${ROLE_LABEL[form.role]}.`);
      }
      setForm({ ...EMPTY_FORM, role: form.role });
      setAdding(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add");
    } finally {
      setSaving(false);
    }
  }

  async function setReportsTo(cg: TeamCaregiver, value: string) {
    try {
      await api(`/api/v1/team/caregivers/${cg.id}/manager`, {
        method: "PUT",
        body: JSON.stringify({ manager_user_id: value ? Number(value) : null }),
      });
      setMessage(`${cg.first_name} now reports to ${value ? managerName(Number(value)) : "no one"}.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update");
    }
  }

  const set = (k: keyof typeof EMPTY_FORM) => (e: { target: { value: string } }) =>
    setForm({ ...form, [k]: e.target.value });
  const setP = (k: keyof typeof EMPTY_PANEL_FORM) => (e: { target: { value: string } }) =>
    setPf({ ...pf, [k]: e.target.value });

  const myId = (auth as { user_id?: number; id?: number } | null)?.user_id;
  const needle = search.trim().toLowerCase();
  const hit = (...v: (string | null | undefined)[]) => !needle || v.some((x) => (x || "").toLowerCase().includes(needle));
  const roleGroup = (role: string) => (role === "SYSTEM_ADMIN" ? "TENANT_ADMIN" : role);
  const shownStaff =
    roleFilter === "CAREGIVER" ? [] : staff.filter((u) => (!roleFilter || roleGroup(u.role) === roleFilter) && hit(fullName(u), u.email));
  const shownCaregivers =
    roleFilter && roleFilter !== "CAREGIVER"
      ? []
      : caregivers.filter(
          (c) => (teamFilter == null || c.manager_user_id === teamFilter) && hit(fullName(c), c.login_email, c.phone),
        );

  function actionMenu(id: string, name: string, items: { label: string; onClick: () => void; danger?: boolean }[]) {
    if (items.length === 0) return null;
    return (
      <div className="tm-menu-wrap">
        <button
          type="button"
          className="tm-menu-btn"
          aria-label={`Actions for ${name}`}
          aria-haspopup="menu"
          aria-expanded={menu === id}
          data-menu-btn={id}
          onClick={(e) => {
            e.stopPropagation();
            setMenu(menu === id ? null : id);
          }}
        >
          ⋯
        </button>
        {menu === id && (
          <div className="tm-menu" role="menu" onClick={(e) => e.stopPropagation()}>
            {items.map((it) => (
              <button
                key={it.label}
                type="button"
                role="menuitem"
                className={it.danger ? "tm-menu-item tm-danger" : "tm-menu-item"}
                onClick={it.onClick}
              >
                {it.label}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  function passwordField() {
    return (
      <div className="tm-pw">
        <label>New password (8+ characters)</label>
        <div className="tm-pw-row">
          <input
            type={showPw ? "text" : "password"}
            value={pf.password}
            onChange={setP("password")}
            minLength={8}
            required
            autoComplete="new-password"
          />
          <button type="button" className="tm-link-btn" onClick={() => setShowPw(!showPw)}>
            {showPw ? "Hide" : "Show"}
          </button>
          <button
            type="button"
            className="tm-link-btn"
            onClick={() => {
              setPf({ ...pf, password: generatePassword() });
              setShowPw(true);
            }}
          >
            Generate
          </button>
        </div>
      </div>
    );
  }

  function reassignField(managerId: number) {
    if (!needsReassign || !caseload) return null;
    return (
      <div>
        <label>
          Reassign their {plural(caseload.clients, "client")} and {plural(caseload.caregivers, "caregiver")} to…
        </label>
        <select value={pf.reassign} onChange={setP("reassign")} required>
          <option value="">Choose a manager…</option>
          {otherManagers(managerId).map((m) => (
            <option key={m.id} value={m.id}>
              {fullName(m)}
            </option>
          ))}
        </select>
      </div>
    );
  }

  function panelRow(key: string, colSpan: number) {
    if (!panel) return null;
    const isStaff = panel.kind === "staff";
    const title = {
      edit: "Edit details",
      role: "Change role",
      password: "Reset password",
      deactivate: "Deactivate account",
      left: "Mark as left",
    }[panel.mode];
    void colSpan;
    return (
      <OpsModal key={key} open title={title} onClose={() => setPanel(null)} wide={panel.mode === "edit"}>
          <form className="tm-panel" onSubmit={onPanelSubmit}>
            {error ? <p className="ks-modal-error" role="alert">{error}</p> : null}
            {panel.mode === "edit" && (
              <div className="tm-panel-grid">
                <div>
                  <label>First name</label>
                  <input value={pf.first_name} onChange={setP("first_name")} required />
                </div>
                <div>
                  <label>Last name</label>
                  <input value={pf.last_name} onChange={setP("last_name")} />
                </div>
                <div>
                  <label>Email</label>
                  <input type="email" value={pf.email} onChange={setP("email")} required={isStaff} />
                </div>
                <div>
                  <label>Phone</label>
                  <input type="tel" inputMode="tel" placeholder="+91 98765 43210" value={pf.phone} onChange={setP("phone")} />
                </div>
              </div>
            )}
            {panel.mode === "edit" && !isStaff && <CaregiverClients caregiverId={panel.id} />}
            {panel.mode === "role" && (
              <div className="tm-panel-grid">
                <div>
                  <label>Role</label>
                  <select value={pf.role} onChange={setP("role")}>
                    <option value="TENANT_ADMIN">Owner (full access)</option>
                    <option value="CARE_MANAGER">Care manager</option>
                    <option value="VIEWER">View-only</option>
                  </select>
                </div>
                {pf.role !== "CARE_MANAGER" && reassignField(panel.id)}
              </div>
            )}
            {panel.mode === "password" && passwordField()}
            {panel.mode === "deactivate" && (
              <div className="tm-panel-grid">
                <p className="muted tm-panel-note">They will be signed out and can no longer sign in. You can reactivate them later.</p>
                {reassignField(panel.id)}
              </div>
            )}
            {panel.mode === "left" && (
              <p className="muted tm-panel-note">
                They leave the caregiver list and their app login (if any) is switched off.
              </p>
            )}
            <div className="tm-panel-actions">
              <button type="submit" className={panel.mode === "deactivate" || panel.mode === "left" ? "tm-primary tm-danger-btn" : "tm-primary"} disabled={saving}>
                {saving ? "Saving…" : panel.mode === "deactivate" ? "Deactivate" : panel.mode === "left" ? "Mark as left" : "Save"}
              </button>
              <button type="button" className="tm-link-btn" onClick={() => setPanel(null)}>
                Cancel
              </button>
            </div>
          </form>
      </OpsModal>
    );
  }

  function staffStatus(u: Staff) {
    return u.status === "INACTIVE" ? (
      <span className="tm-badge tm-badge-off">Deactivated</span>
    ) : (
      <span className="tm-badge tm-badge-on">Active</span>
    );
  }

  function caregiverStatus(c: TeamCaregiver) {
    if (!c.login_email) return <span className="tm-badge tm-badge-none">No login</span>;
    if (c.login_status === "INACTIVE") return <span className="tm-badge tm-badge-off">Login off</span>;
    return <span className="tm-badge tm-badge-on">Active</span>;
  }

  function staffItems(u: Staff) {
    const self = u.id === myId || u.email === auth?.email;
    const items: { label: string; onClick: () => void; danger?: boolean }[] = [];
    if (isAdmin) {
      items.push({ label: "Edit", onClick: () => openPanel("staff", u.id, "edit") });
      items.push({ label: "Documents", onClick: () => setDocsFor({ type: "staff", id: u.id, name: `${u.first_name} ${u.last_name}` }) });
      if (!self && u.role !== "SYSTEM_ADMIN") {
        items.push({ label: "Change role", onClick: () => openPanel("staff", u.id, "role") });
        items.push({ label: "Send setup link", onClick: () => void sendSetupLink(u.id, `${u.first_name} ${u.last_name}`) });
        items.push({ label: "Reset password", onClick: () => openPanel("staff", u.id, "password") });
        if (u.status === "INACTIVE") items.push({ label: "Reactivate", onClick: () => reactivate(u) });
        else items.push({ label: "Deactivate", onClick: () => openPanel("staff", u.id, "deactivate"), danger: true });
      }
    }
    return items;
  }

  function caregiverItems(c: TeamCaregiver) {
    if (!canEditCaregivers) return [];
    const items: { label: string; onClick: () => void; danger?: boolean }[] = [
      { label: "Edit", onClick: () => openPanel("cg", c.id, "edit") },
    ];
    if (isAdmin) items.push({ label: "Documents", onClick: () => setDocsFor({ type: "caregiver", id: c.id, name: `${c.first_name} ${c.last_name}` }) });
    if (c.login_user_id) items.push({ label: "Send setup link", onClick: () => void sendSetupLink(c.login_user_id as number, `${c.first_name} ${c.last_name}`) });
    if (c.login_user_id) items.push({ label: "Reset password", onClick: () => openPanel("cg", c.id, "password") });
    items.push({ label: "Mark as left", onClick: () => openPanel("cg", c.id, "left"), danger: true });
    return items;
  }

  return (
    <div className="tm-page">
      <div className="ks-head-row">
        <PageHeader title="Team" subtitle="Owners, managers and caregivers" />
        {canEditCaregivers ? (
          <div className="ks-head-actions">
            <button type="button" onClick={() => setAdding(true)} aria-label="Add team member" title="Add team member">
              <span className="ks-ha-icon" aria-hidden="true">+</span>
              <span className="ks-ha-label">+ Add team member</span>
            </button>
          </div>
        ) : null}
      </div>
      <Flash error={error} message={message} onClear={() => { setError(""); setMessage(""); }} />

      <div className="tm-find" role="search">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search the team"
          aria-label="Search the team"
        />
        <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} aria-label="Role">
          <option value="">Everyone</option>
          <option value="TENANT_ADMIN">Admins</option>
          <option value="CARE_MANAGER">Managers</option>
          <option value="VIEWER">View-only</option>
          <option value="CAREGIVER">Caregivers</option>
        </select>
      </div>

      <div className="card" style={{ marginBottom: "1rem" }}>
        <h2>{staff.some((u) => u.role === "VIEWER") ? "Owners, care managers & view-only" : "Owners & care managers"}</h2>
        <div className="tm-table-wrap">
          <table className="table tm-stack">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Phone</th>
                <th>Role</th>
                <th>Status</th>
                <th>Clients</th>
                <th>Caregivers</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {shownStaff.length === 0 ? (
                <tr>
                  <td colSpan={8} className="muted">
                    No one matches.
                  </td>
                </tr>
              ) : null}
              {shownStaff.map((u) => {
                const stats = u.role === "CARE_MANAGER" ? managerStats(u.id) : undefined;
                const filtered = teamFilter === u.id;
                return [
                  <tr key={u.id} className={u.status === "INACTIVE" ? "tm-row-off" : undefined}>
                    <td className="tm-name-cell">
                      {isAdmin ? (
                        <button type="button" className="tm-name-btn" title="Edit" onClick={() => openPanel("staff", u.id, "edit")}>
                          {fullName(u)}
                        </button>
                      ) : (
                        fullName(u)
                      )}
                    </td>
                    <td data-label="Email">{u.email}</td>
                    <td data-label="Phone">{u.phone ? <a className="tm-tel" href={`tel:${u.phone.replace(/[^\d+]/g, "")}`}>{u.phone}</a> : <span className="muted">—</span>}</td>
                    <td data-label="Role">{ROLE_LABEL[u.role]}</td>
                    <td data-label="Status">{staffStatus(u)}</td>
                    <td data-label="Clients">{stats ? stats.clients ?? "—" : "—"}</td>
                    <td data-label="Caregivers">
                      {stats ? (
                        <button
                          type="button"
                          className={filtered ? "secondary tm-team-btn tm-on" : "secondary tm-team-btn"}
                          title="Show this manager's caregivers"
                          aria-pressed={filtered}
                          onClick={() => setTeamFilter(filtered ? null : u.id)}
                        >
                          {stats.caregivers ?? caregivers.filter((c) => c.manager_user_id === u.id).length}
                        </button>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="tm-actions-cell">
                      {actionMenu(`s${u.id}`, fullName(u), staffItems(u))}
                    </td>
                  </tr>,
                  panel?.kind === "staff" && panel.id === u.id ? panelRow(`p${u.id}`, 8) : null,
                ];
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <div className="tm-cg-head">
          <h2>
            Caregivers
            {teamFilter != null && (
              <span className="tm-filter-chip">
                {managerName(teamFilter)}&rsquo;s team
                <button type="button" className="tm-link-btn" onClick={() => setTeamFilter(null)} aria-label="Show all caregivers">
                  ×
                </button>
              </span>
            )}
          </h2>
          <Link href="/kushalaya/hiring" className="tm-hire-link">Hiring: applicants &amp; interviews →</Link>
        </div>
        {shownCaregivers.length === 0 ? (
          <p className="muted">{caregivers.length ? "No caregivers match." : "No caregivers yet."}</p>
        ) : (
          <div className="tm-table-wrap">
            <table className="table tm-stack">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Sign-in email</th>
                  <th>Phone</th>
                  <th>Status</th>
                  <th>Reports to</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {shownCaregivers.map((c) => [
                  <tr key={c.id}>
                    <td className="tm-name-cell">
                      {canEditCaregivers ? (
                        <button type="button" className="tm-name-btn" title="Edit" onClick={() => openPanel("cg", c.id, "edit")}>
                          {fullName(c)}
                        </button>
                      ) : (
                        fullName(c)
                      )}
                    </td>
                    <td data-label="Sign-in email">{c.login_email ?? <span className="muted">—</span>}</td>
                    <td data-label="Phone">{c.phone ? <a className="tm-tel" href={`tel:${c.phone.replace(/[^\d+]/g, "")}`}>{c.phone}</a> : <span className="muted">—</span>}</td>
                    <td data-label="Status">{caregiverStatus(c)}</td>
                    <td data-label="Reports to">
                      {isAdmin ? (
                        <select
                          value={c.manager_user_id ?? ""}
                          onChange={(e) => setReportsTo(c, e.target.value)}
                          aria-label={`${c.first_name} reports to`}
                        >
                          <option value="">No manager</option>
                          {managers.map((m) => (
                            <option key={m.id} value={m.id}>
                              {fullName(m)}
                            </option>
                          ))}
                        </select>
                      ) : (
                        managerName(c.manager_user_id)
                      )}
                    </td>
                    <td className="tm-actions-cell">
                      {actionMenu(`c${c.id}`, fullName(c), caregiverItems(c))}
                    </td>
                  </tr>,
                  panel?.kind === "cg" && panel.id === c.id ? panelRow(`p${c.id}`, 6) : null,
                ])}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <OpsModal open={canEditCaregivers && adding} title="Add a team member" onClose={() => setAdding(false)}>
          <form onSubmit={onAdd} className="tm-add-form">
            {error ? <p className="ks-modal-error" role="alert">{error}</p> : null}
            <div>
              <label>Role</label>
              <select value={form.role} onChange={set("role")}>
                <option value="CAREGIVER">Caregiver</option>
                {isAdmin && <option value="CARE_MANAGER">Care manager</option>}
                {isAdmin && <option value="TENANT_ADMIN">Owner (full access)</option>}
                {isAdmin && <option value="VIEWER">View-only</option>}
              </select>
            </div>
            {form.role === "CAREGIVER" && isAdmin ? (
              <div>
                <label>Reports to</label>
                <select value={form.manager_user_id} onChange={set("manager_user_id")}>
                  <option value="">Choose a manager…</option>
                  {managers.map((m) => (
                    <option key={m.id} value={m.id}>
                      {fullName(m)}
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <div />
            )}
            <div>
              <label>First name</label>
              <input value={form.first_name} onChange={set("first_name")} required />
            </div>
            <div>
              <label>Last name</label>
              <input value={form.last_name} onChange={set("last_name")} required={form.role !== "CAREGIVER"} />
            </div>
            <div>
              <label>{form.role === "CAREGIVER" ? "Email (optional — only if they use the app)" : "Email (used to sign in)"}</label>
              <input type="email" value={form.email} onChange={set("email")} required={form.role !== "CAREGIVER"} />
            </div>
            <div>
              <label>Password (optional)</label>
              <input
                type="password"
                value={form.password}
                onChange={set("password")}
                minLength={8}
                placeholder="Leave blank to send a setup link"
              />
              <small className="muted">Blank = they get an email and WhatsApp link to set their own password.</small>
            </div>
            <div>
              <label>Phone</label>
              <input type="tel" inputMode="tel" placeholder="+91 98765 43210" value={form.phone} onChange={set("phone")} />
            </div>
            <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
              <button type="button" className="secondary" disabled={saving} onClick={() => setAdding(false)}>
                Cancel
              </button>
              <button type="submit" disabled={saving}>
                {saving ? "Adding…" : "Add"}
              </button>
            </div>
          </form>
      </OpsModal>
      {docsFor ? <StaffDocuments person={docsFor} onClose={() => setDocsFor(null)} /> : null}
    </div>
  );
}
