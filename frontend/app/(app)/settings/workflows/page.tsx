"use client";

import Link from "next/link";
import { dateTimeIST } from "@/lib/ist";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getStoredAuth } from "@/lib/api";
import { canAccessSettings } from "@/lib/auth";
import { Flash } from "@/components/Flash";
import { PageHeader } from "@/components/PageHeader";
import {
  completeWorkflowTask,
  fetchWorkflowConfig,
  fetchWorkflowEvents,
  fetchWorkflowTasks,
  scanWorkflowTriggers,
  updateWorkflowConfig,
  type WorkflowDefinition,
  type WorkflowEvent,
  type WorkflowTask,
} from "@/lib/workflows";

export default function WorkflowsSettingsPage() {
  const router = useRouter();
  const auth = getStoredAuth();
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([]);
  const [tasks, setTasks] = useState<WorkflowTask[]>([]);
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [config, openTasks, recentEvents] = await Promise.all([
        fetchWorkflowConfig(),
        fetchWorkflowTasks("OPEN"),
        fetchWorkflowEvents(20),
      ]);
      setWorkflows(config.workflows);
      setTasks(openTasks);
      setEvents(recentEvents);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!auth) {
      router.replace("/login");
      return;
    }
    if (!canAccessSettings(auth.role)) {
      router.replace("/unauthorized");
      return;
    }
    load();
  }, [auth?.email, auth?.role, auth?.tenant_id, load, router]);

  async function toggleWorkflow(wf: WorkflowDefinition) {
    setError("");
    const config = await fetchWorkflowConfig();
    const disabled = new Set(config.disabled_workflow_ids);
    if (wf.enabled) {
      disabled.add(wf.id);
    } else {
      disabled.delete(wf.id);
    }
    const updated = await updateWorkflowConfig({
      disabled_workflow_ids: Array.from(disabled),
    });
    setWorkflows(updated.workflows);
    setMessage(
      wf.enabled
        ? `Disabled workflow: ${wf.name}`
        : `Enabled workflow: ${wf.name}`,
    );
  }

  async function onScan() {
    setError("");
    const result = await scanWorkflowTriggers();
    setMessage(`Scan complete — ${result.events_emitted} event(s) emitted`);
    await load();
  }

  async function onCompleteTask(taskId: number) {
    setError("");
    await completeWorkflowTask(taskId);
    setMessage("Task marked completed");
    await load();
  }

  if (!canAccessSettings(auth?.role || "")) return null;

  if (loading) {
    return (
      <>
        <PageHeader
          title="Workflow automation"
          action={
            <Link href="/settings">
              <button type="button" className="secondary">
                Back to settings
              </button>
            </Link>
          }
        />
        <p className="muted">Loading…</p>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Workflow automation"
        subtitle="Configure triggers and review ops tasks from WorkforceOS workflows"
        action={
          <Link href="/settings">
            <button type="button" className="secondary">
              Back to settings
            </button>
          </Link>
        }
      />
      <Flash
        error={error}
        message={message}
        onClear={() => {
          setError("");
          setMessage("");
        }}
      />

      <div className="card" style={{ marginBottom: "1rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
          <div>
            <h2>Workflow templates</h2>
            <p className="muted" style={{ margin: 0 }}>
              Platform-defined automations for your industry vertical. Disable any you do not need.
            </p>
          </div>
          <button type="button" className="secondary" onClick={onScan}>
            Run compliance scan
          </button>
        </div>
        <table className="table" style={{ marginTop: "1rem" }}>
          <thead>
            <tr>
              <th>Workflow</th>
              <th>Trigger</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {workflows.map((wf) => (
              <tr key={wf.id}>
                <td>
                  <strong>{wf.name}</strong>
                  <br />
                  <span className="muted" style={{ fontSize: "0.8rem" }}>
                    {wf.description}
                  </span>
                </td>
                <td>
                  <code>{wf.trigger?.event}</code>
                </td>
                <td>{wf.enabled ? "Enabled" : "Disabled"}</td>
                <td>
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => toggleWorkflow(wf)}
                  >
                    {wf.enabled ? "Disable" : "Enable"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ marginBottom: "1rem" }}>
        <h2>Open tasks ({tasks.length})</h2>
        <p className="muted">Ops inbox created by workflow actions.</p>
        {tasks.length === 0 ? (
          <p className="muted">No open workflow tasks.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Task</th>
                <th>Workflow</th>
                <th>Priority</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => {
                const replacements =
                  task.metadata_json?.replacement_suggestions?.suggestions ?? [];
                return (
                <tr key={task.id}>
                  <td>
                    <strong>{task.title}</strong>
                    {task.description && (
                      <>
                        <br />
                        <span className="muted" style={{ fontSize: "0.8rem" }}>
                          {task.description.slice(0, 120)}
                        </span>
                      </>
                    )}
                    {task.workflow_id === "attendance-exception" &&
                      replacements.length > 0 && (
                        <ul
                          className="muted"
                          style={{
                            fontSize: "0.8rem",
                            margin: "0.35rem 0 0",
                            paddingLeft: "1.1rem",
                          }}
                        >
                          {replacements.slice(0, 3).map((s) => (
                            <li key={s.caregiver_id}>
                              <Link href={`/caregivers/${s.caregiver_id}`}>
                                {s.caregiver_name}
                              </Link>{" "}
                              — {Math.round(s.match_score)}% match
                            </li>
                          ))}
                        </ul>
                      )}
                  </td>
                  <td>{task.workflow_id}</td>
                  <td>{task.priority}</td>
                  <td>
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => onCompleteTask(task.id)}
                    >
                      Complete
                    </button>
                  </td>
                </tr>
              );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h2>Recent events</h2>
        <p className="muted">Domain events that triggered workflow evaluation.</p>
        {events.length === 0 ? (
          <p className="muted">No workflow events yet.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>When</th>
                <th>Event</th>
                <th>Entity</th>
                <th>Matched</th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev) => (
                <tr key={ev.id}>
                  <td>{dateTimeIST(ev.created_at)}</td>
                  <td>
                    <code>{ev.event_type}</code>
                  </td>
                  <td>
                    {ev.entity_type
                      ? `${ev.entity_type} #${ev.entity_id}`
                      : "—"}
                  </td>
                  <td>
                    {(ev.processing_result as { workflows_matched?: number })
                      ?.workflows_matched ?? 0}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
