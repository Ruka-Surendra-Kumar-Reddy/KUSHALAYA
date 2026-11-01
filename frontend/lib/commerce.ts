import { api, getApiUrl, postFormData } from "./api";

/** Products, coupons and orders — backend app/livewell/commerce.py. Money is paise. */
export type Product = {
  id: number;
  name: string;
  category: string;
  description: string;
  /** Admins only — the API leaves our cost and margin out for everyone else. */
  cost_paise?: number;
  margin_bp?: number;
  price_paise: number;
  active: boolean;
  fixes: string[];
  /** Uploaded photo (API path) or the marketing-site picture; null when neither exists. */
  image_url?: string | null;
  has_own_image?: boolean;
};

/** Full URL for a product photo: API paths go to the API host, site pictures stay relative. */
export const productImageSrc = (url?: string | null) =>
  !url ? "" : url.startsWith("/api/") ? `${getApiUrl()}${url}` : url;

export const uploadProductImage = (id: number, file: File) => {
  const fd = new FormData();
  fd.append("file", file);
  return postFormData<Product>(`/api/v1/products/${id}/image`, fd);
};

export const resetProductImage = (id: number) => api<Product>(`/api/v1/products/${id}/image`, { method: "DELETE" });

export type Coupon = {
  id: number;
  code: string;
  kind: "percent" | "amount";
  value: number;
  expires_at: string | null;
  max_uses: number | null;
  used_count: number;
  active: boolean;
  note: string;
};

export type OrderLine = { product_id: number; name: string; qty: number; unit_paise: number; cost_paise?: number };

export type Quote = {
  lines: OrderLine[];
  subtotal_paise: number;
  /** Admins only (with margin_paise). */
  cost_paise?: number;
  discount_paise: number;
  discount_bp: number;
  coupon_code: string | null;
  gst_paise: number;
  total_paise: number;
  margin_paise?: number;
};

export type Order = Quote & {
  id: number;
  elder_id: number;
  elder_name: string;
  status: "pending_approval" | "approved" | "quoted" | "family_accepted" | "scheduled" | "completed" | "cancelled";
  discount_reason: string;
  quoted_at?: string | null;
  family_note?: string;
  paid_paise?: number;
  paid_at?: string | null;
  request_id: string | null;
  job_id: number | null;
  note: string;
  created_at: string | null;
};

export const GST_RATE = 0.18;
export const MANAGER_DISCOUNT_LIMIT = 10;

export const rupees = (paise: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(
    Math.round(paise / 100),
  );

/** Selling price before GST, rounded to the rupee (matches the backend). */
export const priceFor = (costPaise: number, marginBp: number) =>
  Math.round((costPaise * (10000 + marginBp)) / 10000 / 100) * 100;

export const listProducts = (includeInactive = false) =>
  api<Product[]>(`/api/v1/products${includeInactive ? "?include_inactive=true" : ""}`);
export const saveProduct = (id: number | null, data: Partial<Product>) =>
  api<Product>(id ? `/api/v1/products/${id}` : "/api/v1/products", {
    method: id ? "PUT" : "POST",
    body: JSON.stringify(data),
  });

export const listCoupons = () => api<Coupon[]>("/api/v1/coupons");
export const saveCoupon = (id: number | null, data: Partial<Coupon>) =>
  api<Coupon>(id ? `/api/v1/coupons/${id}` : "/api/v1/coupons", {
    method: id ? "PUT" : "POST",
    body: JSON.stringify(data),
  });

type Basket = {
  lines: { product_id: number; qty: number }[];
  discount_bp?: number;
  discount_paise?: number;
  coupon_code?: string;
};
export const quoteOrder = (b: Basket) =>
  api<Quote>("/api/v1/orders/quote", { method: "POST", body: JSON.stringify(b) });
export const createOrder = (b: Basket & { elder_id: number; discount_reason?: string; request_id?: string; note?: string }) =>
  api<Order>("/api/v1/orders", { method: "POST", body: JSON.stringify(b) });
export const listOrders = (params: { elder_id?: number; status?: string } = {}) => {
  const q = new URLSearchParams();
  if (params.elder_id) q.set("elder_id", String(params.elder_id));
  if (params.status) q.set("status", params.status);
  const qs = q.toString();
  return api<Order[]>(`/api/v1/orders${qs ? `?${qs}` : ""}`);
};
export const setOrderStatus = (id: number, status: string, reason?: string) =>
  api<Order>(`/api/v1/orders/${id}/status`, { method: "POST", body: JSON.stringify({ status, reason: reason || undefined }) });

/** Book or move the installation visit (date, time, caregiver). 409 "Book anyway?" → resend with force. */
export const scheduleInstall = (
  id: number,
  body: { scheduled_at: string; caregiver_id?: number | null; note?: string; force?: boolean },
) =>
  api<{ order: Order; job: { id: number; scheduled_at: string | null; caregiver_name: string } }>(
    `/api/v1/orders/${id}/install`,
    { method: "POST", body: JSON.stringify(body) },
  );

/** A quote as the family sees it: names, quantities, GST and total — never our cost or margin. */
export type FamilyQuote = {
  id: number;
  status: Order["status"];
  status_label: string;
  needs_action: boolean;
  lines: { name: string; qty: number; unit_paise: number; line_paise: number; image_url: string | null }[];
  subtotal_paise: number;
  discount_paise: number;
  gst_bp: number;
  gst_paise: number;
  total_paise: number;
  paid_paise: number;
  paid_at: string | null;
  quoted_at: string | null;
  family_note: string;
  invoice_available: boolean;
};
export type FamilyQuoteAccept =
  | { paid: true; quote: FamilyQuote }
  | { paid: false; quote: FamilyQuote; balance_paise: number; shortfall_paise: number; topup_paise: number; message: string };
