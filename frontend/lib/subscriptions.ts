import { api } from "./api";

export type SubscriptionPlan = {
  id: number;
  code: string;
  name: string;
  description: string | null;
  billing_model: string;
  base_price_inr: number;
  price_per_worker_inr: number;
  included_workers: number;
  max_workers: number | null;
  trial_days: number;
  is_active: boolean;
};

export type TenantSubscription = {
  id: number;
  tenant_id: number;
  tenant_name: string | null;
  plan: SubscriptionPlan;
  status: string;
  trial_ends_at: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  active_workers: number;
  notes: string | null;
};

export type SubscriptionInvoice = {
  id: number;
  tenant_id: number;
  tenant_name: string | null;
  subscription_id: number;
  plan_code: string | null;
  invoice_number: string | null;
  period_start: string;
  period_end: string;
  worker_count: number;
  status: string;
  subtotal: number;
  tax_rate: number;
  tax_amount: number;
  total_amount: number;
  amount_paid: number;
  due_date: string | null;
  issued_at: string | null;
  paid_at: string | null;
  line_description: string | null;
};

export async function fetchSubscriptionPlans(): Promise<SubscriptionPlan[]> {
  return api<SubscriptionPlan[]>("/api/v1/subscriptions/plans");
}

export async function fetchMySubscription(): Promise<TenantSubscription> {
  return api<TenantSubscription>("/api/v1/subscriptions/me");
}

export async function fetchTenantSubscription(
  tenantId: number,
): Promise<TenantSubscription> {
  return api<TenantSubscription>(
    `/api/v1/subscriptions/admin/tenants/${tenantId}`,
  );
}

export async function assignTenantSubscription(
  tenantId: number,
  payload: { plan_code: string; status?: string; notes?: string },
): Promise<TenantSubscription> {
  return api<TenantSubscription>(
    `/api/v1/subscriptions/admin/tenants/${tenantId}`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
  );
}

export async function fetchSubscriptionInvoices(
  tenantId?: number,
): Promise<SubscriptionInvoice[]> {
  const q = tenantId ? `?tenant_id=${tenantId}` : "";
  return api<SubscriptionInvoice[]>(`/api/v1/subscriptions/invoices${q}`);
}

export async function generateSubscriptionInvoice(payload: {
  tenant_id: number;
  period_start: string;
  period_end: string;
}): Promise<SubscriptionInvoice> {
  return api<SubscriptionInvoice>("/api/v1/subscriptions/invoices/generate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function issueSubscriptionInvoice(
  invoiceId: number,
): Promise<SubscriptionInvoice> {
  return api<SubscriptionInvoice>(
    `/api/v1/subscriptions/invoices/${invoiceId}/issue`,
    { method: "POST" },
  );
}

export async function recordSubscriptionPayment(
  invoiceId: number,
  amount: number,
  reference?: string,
): Promise<SubscriptionInvoice> {
  return api<SubscriptionInvoice>(
    `/api/v1/subscriptions/invoices/${invoiceId}/payments`,
    {
      method: "POST",
      body: JSON.stringify({ amount, reference }),
    },
  );
}
