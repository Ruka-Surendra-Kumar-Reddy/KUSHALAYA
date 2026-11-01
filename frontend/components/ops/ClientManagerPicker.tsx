"use client";
import "./client-history.css";

import { useEffect, useState } from "react";
import { api, } from "@/lib/api";
import { isAdmin as isAdminUser } from "@/lib/roles";

type Manager = { id: number; first_name: string; last_name: string };

/** "Care manager: Priya R." — admins can change it (managers see only their team). */
export function ClientManagerPicker({
  elderId,
  managerId,
  managerName = "",
}: {
  elderId: number;
  managerId: number | null | undefined;
  managerName?: string;
}) {
  const isAdmin = isAdminUser();
  const [managers, setManagers] = useState<Manager[]>([]);
  const [value, setValue] = useState(managerId ? String(managerId) : "");
  const [name, setName] = useState(managerName);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (isAdmin && open && !managers.length)
      api<Manager[]>("/api/v1/team/managers").then(setManagers).catch(() => undefined);
  }, [isAdmin, open, managers.length]);

  async function change(next: string) {
    setError("");
    try {
      await api(`/api/v1/team/clients/${elderId}/manager`, {
        method: "PUT",
        body: JSON.stringify({ manager_user_id: next ? Number(next) : null }),
      });
      const m = managers.find((x) => String(x.id) === next);
      setValue(next);
      setName(m ? `${m.first_name} ${m.last_name ? `${m.last_name[0]}.` : ""}`.trim() : "");
      setOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not change the manager");
    }
  }

  return (
    <span className="cp-manager">
      <span>Care manager: {name || "Not assigned"}</span>
      {isAdmin && !open ? (
        <button type="button" className="cp-linkbtn" onClick={() => setOpen(true)}>
          Change
        </button>
      ) : null}
      {isAdmin && open ? (
        <select value={value} onChange={(e) => void change(e.target.value)} aria-label="Care manager">
          <option value="">No manager</option>
          {managers.map((m) => (
            <option key={m.id} value={m.id}>
              {m.first_name} {m.last_name}
            </option>
          ))}
        </select>
      ) : null}
      {error ? <small className="error-text">{error}</small> : null}
    </span>
  );
}
