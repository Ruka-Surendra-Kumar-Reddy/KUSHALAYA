"use client";

import { useEffect, useState } from "react";
import {
  fetchStaffElderImprovementPlan,
  planStatusLabel,
  priorityLabel,
  updateStaffPlanItemStatus,
  type FamilyImprovementPlan,
  type PlanItemStatus,
} from "@/lib/livewell/familyApi";

const STATUSES: PlanItemStatus[] = ["open", "scheduled", "done"];

export function FamilyCarePlanAdmin({ elderId }: { elderId: number }) {
  const [plan, setPlan] = useState<FamilyImprovementPlan | null>(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  async function reload() {
    try {
      const row = await fetchStaffElderImprovementPlan(elderId);
      setPlan(row);
      setError("");
    } catch (e) {
      setPlan(null);
      setError(e instanceof Error ? e.message : "Could not load family plan");
    }
  }

  useEffect(() => {
    void reload();
  }, [elderId]);

  async function setStatus(itemId: string, status: PlanItemStatus) {
    setBusyId(itemId);
    setError("");
    try {
      await updateStaffPlanItemStatus(elderId, itemId, status);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    } finally {
      setBusyId(null);
    }
  }

  if (error && !plan) {
    return (
      <section className="card" style={{ marginTop: "1.5rem" }}>
        <h2>Living plan</h2>
        <p className="muted">{error}</p>
      </section>
    );
  }

  if (!plan?.has_plan) {
    return (
      <section className="card" style={{ marginTop: "1.5rem" }}>
        <h2>Living plan</h2>
        <p className="muted">No plan yet.</p>
      </section>
    );
  }

  return (
    <section className="card" style={{ marginTop: "1.5rem" }}>
      <h2>Living plan</h2>
      {error ? <p className="error-text">{error}</p> : null}
      <ul className="home-safety-family-plan-list" style={{ listStyle: "none", padding: 0 }}>
        {plan.items.map((item) => (
          <li key={item.id} style={{ marginBottom: "0.85rem" }}>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
              <span className={`home-safety-family-priority-badge priority-${item.priority}`}>
                {priorityLabel(item.priority)}
              </span>
              <span className={`home-safety-family-status-badge status-${item.status}`}>
                {planStatusLabel(item.status)}
              </span>
              <strong>{item.title}</strong>
            </div>
            <div style={{ display: "flex", gap: "0.35rem", marginTop: "0.45rem", flexWrap: "wrap" }}>
              {STATUSES.map((s) => (
                <button
                  key={s}
                  type="button"
                  className={item.status === s ? "primary" : "secondary"}
                  disabled={busyId === item.id || item.status === s}
                  onClick={() => void setStatus(item.id, s)}
                  style={{ fontSize: "0.8rem", padding: "0.25rem 0.55rem" }}
                >
                  {planStatusLabel(s)}
                </button>
              ))}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
