"use client";

import Link from "next/link";
import { BackLink } from "@/components/ops/PageActions";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getStoredAuth } from "@/lib/api";
import { canManageTenants } from "@/lib/auth";
import { Flash } from "@/components/Flash";
import { PageHeader } from "@/components/PageHeader";
import {
  fetchMySubscription,
  fetchSubscriptionInvoices,
  type SubscriptionInvoice,
  type TenantSubscription,
} from "@/lib/subscriptions";

function inr(amount: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

function statusClass(status: string): string {
  if (status === "ACTIVE" || status === "PAID") return "success-text";
  if (status === "PAST_DUE" || status === "SUSPENDED") return "error-text";
  return "";
}

export default function SubscriptionSettingsPage() {
  const router = useRouter();
  const auth = getStoredAuth();
  const isSuperAdmin = canManageTenants(auth?.role || "");
  const [sub, setSub] = useState<TenantSubscription | null>(null);
  const [invoices, setInvoices] = useState<SubscriptionInvoice[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!auth) {
      router.replace("/login");
      return;
    }
    if (isSuperAdmin && !auth.tenant_id) {
      return;
    }
    Promise.all([fetchMySubscription(), fetchSubscriptionInvoices()])
      .then(([subscription, invs]) => {
        setSub(subscription);
        setInvoices(invs);
      })
      .catch((e) => setError(String(e)));
  }, [auth, isSuperAdmin, router]);

  if (isSuperAdmin && !auth?.tenant_id) {
    return (
      <>
        <PageHeader title="Platform subscription" />
        <div className="card">
          <p>
            Super admins manage tenant subscriptions from each{" "}
            <Link href="/tenants">tenant profile</Link>.
          </p>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="WorkforceOS subscription"
        subtitle="Your agency platform plan and billing"
      />
      <p style={{ marginBottom: "1rem" }}>
        <BackLink href="/settings" label="Back to settings" />
      </p>
      <Flash error={error} onClear={() => setError("")} />

      {sub && (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <h2>Current plan</h2>
          <p>
            <strong className={statusClass(sub.status)}>{sub.status}</strong>
            {" · "}
            {sub.plan.name} ({sub.plan.code})
          </p>
          <p className="muted" style={{ fontSize: "0.85rem" }}>
            {sub.plan.description}
          </p>
          <div className="kpi-grid" style={{ marginTop: "0.75rem" }}>
            <div className="kpi">
              <div className="muted">Active caregivers</div>
              <div className="kpi-value">{sub.active_workers}</div>
            </div>
            <div className="kpi">
              <div className="muted">Billing model</div>
              <div className="kpi-value" style={{ fontSize: "1rem" }}>
                {sub.plan.billing_model}
              </div>
            </div>
          </div>
          {sub.trial_ends_at && sub.status === "TRIAL" && (
            <p style={{ marginTop: "0.75rem" }}>
              Trial ends: {new Date(sub.trial_ends_at).toLocaleDateString()}
            </p>
          )}
          {sub.current_period_start && sub.current_period_end && (
            <p className="muted" style={{ fontSize: "0.85rem" }}>
              Billing period: {sub.current_period_start} – {sub.current_period_end}
            </p>
          )}
          <p className="muted" style={{ fontSize: "0.8rem", marginTop: "0.5rem" }}>
            Pricing: base {inr(sub.plan.base_price_inr)}
            {sub.plan.price_per_worker_inr > 0 && (
              <> · {inr(sub.plan.price_per_worker_inr)}/caregiver</>
            )}
            {sub.plan.included_workers > 0 && (
              <> · {sub.plan.included_workers} included</>
            )}
          </p>
        </div>
      )}

      <div className="card">
        <h2>Platform invoices</h2>
        {invoices.length === 0 ? (
          <p className="muted">No platform invoices yet.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Period</th>
                <th>Workers</th>
                <th>Amount</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr key={inv.id}>
                  <td>
                    {inv.invoice_number || `#${inv.id}`}
                    <br />
                    <span className="muted" style={{ fontSize: "0.8rem" }}>
                      {inv.period_start} – {inv.period_end}
                    </span>
                  </td>
                  <td>{inv.worker_count}</td>
                  <td>
                    {inr(inv.total_amount)}
                    {inv.amount_paid > 0 && inv.status !== "PAID" && (
                      <span className="muted" style={{ fontSize: "0.8rem" }}>
                        <br />
                        Paid {inr(inv.amount_paid)}
                      </span>
                    )}
                  </td>
                  <td className={statusClass(inv.status)}>{inv.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="muted" style={{ fontSize: "0.8rem", marginTop: "0.75rem" }}>
          Contact your WorkforceOS account manager for plan changes or payment
          questions.
        </p>
      </div>
    </>
  );
}
