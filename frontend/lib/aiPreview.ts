/**
 * AI room preview ("See it in their home") — API client and shared helpers.
 * Backend: backend/app/api/v1/home_safety_ai_preview.py. Money is integer paise.
 *
 * Other features open the preview with products preselected:
 *   aiPreviewHref({ assessment, photo, products: ["BTH-002", "BTH-009"] })
 *   → /kushalaya/ai-preview?assessment=<id>&photo=<docId>&products=BTH-002,BTH-009
 */
import { api, downloadFileBlob, triggerBlobDownload } from "./api";

export type PreviewStage =
  | "queued"
  | "preparing"
  | "generating"
  | "checking"
  | "retrying"
  | "saving"
  | "done"
  | "failed";

export type PreviewMarker = { n: number; product: string; x: number; y: number; w: number; h: number };

export type PreviewItem = {
  n: number;
  product_id: number | null;
  product_code: string;
  name: string;
  price_paise?: number;
  gst_paise?: number;
  price_with_gst_paise: number;
  priced: boolean;
  /** QA: true shown, false not shown, null not checked. */
  shown?: boolean | null;
};

export type PreviewJob = {
  ai_job_id: string;
  assessment_id: string;
  elder_id: number | null;
  room_type: string;
  package_level: string;
  source_document_id: number;
  generated_document_id: number | null;
  before_url: string;
  after_url: string | null;
  status: string;
  review_status: string;
  provider: string | null;
  is_stub: boolean;
  error_message: string | null;
  progress: {
    stage: PreviewStage;
    label: string;
    percent: number;
    started_at: string | null;
    finished_at: string | null;
    elapsed_seconds: number | null;
    estimate_seconds: number;
    running: boolean;
  };
  similarity_score: number | null;
  similarity_min: number | null;
  room_changed: boolean;
  qa_status: string | null;
  missing: string[];
  /** Anything else the AI added, removed or moved (e.g. "a second toilet"); blocks approval. */
  changes?: string[];
  markers: PreviewMarker[];
  render_attempts: number;
  regenerated_from: string | null;
  regenerations_left: number | null;
  created_at: string;
  reviewed_at: string | null;
  items: PreviewItem[];
  subtotal_paise: number;
  gst_paise: number;
  total_paise: number;
  all_priced: boolean;
  cache_hit?: boolean;
};

export type PreviewPhoto = { document_id: number; room_type: string; caption: string; image_url: string };
export type CatalogPick = {
  product_id: number;
  product_code: string;
  name: string;
  category: string;
  price_with_gst_paise: number;
  priced: boolean;
};

export type PreviewContext = {
  assessments: {
    assessment_id: string;
    status: string;
    updated_at: string;
    completed_at?: string | null;
    created_at?: string | null;
    assessor?: string | null;
  }[];
  assessment_id: string | null;
  assessment_status?: string;
  client: { elder_id: number | null; prospect_id: number | null; first_name: string } | null;
  photos: PreviewPhoto[];
  recommended: Record<string, string[]>;
  catalog: CatalogPick[];
  tiers: { id: string; name: string }[];
  caps: { max_photos: number; max_regenerations_per_tier: number; daily_cap: number; today: number };
  provider: string;
};

export type FamilyPreview = {
  id: string;
  label: string;
  room_type: string;
  package_level: string;
  before_url: string;
  after_url: string;
  markers: PreviewMarker[];
  reviewed_at: string | null;
  items: PreviewItem[];
  total_paise: number;
  gst_paise: number;
  all_priced: boolean;
  disclaimer: string;
};

export type AiUsage = {
  features: {
    feature: string;
    label: string;
    calls: number;
    cache_hits: number;
    failed: number;
    estimated_cost_paise: number;
  }[];
  total_calls: number;
  estimated_cost_paise: number;
  previews_today: number;
  daily_cap: number;
};

const BASE = "/api/v1/home-safety/ai/preview";
const FAMILY = "/api/v1/home-safety/family/ai-previews";

export function aiPreviewHref(opts: {
  assessment?: string | null;
  elder?: number | null;
  photo?: number | null;
  products?: string[];
  job?: string | null;
}): string {
  const q = new URLSearchParams();
  if (opts.assessment) q.set("assessment", opts.assessment);
  if (opts.elder) q.set("elder", String(opts.elder));
  if (opts.photo) q.set("photo", String(opts.photo));
  if (opts.products?.length) q.set("products", opts.products.join(","));
  if (opts.job) q.set("job", opts.job);
  const s = q.toString();
  return `/kushalaya/ai-preview${s ? `?${s}` : ""}`;
}

/** "BTH-002, bth-009 ," → ["BTH-002", "BTH-009"] (deduped, max 12). */
export function parseProductCodes(raw: string | null | undefined): string[] {
  const out: string[] = [];
  for (const part of (raw || "").split(",")) {
    const code = part.trim().toUpperCase();
    if (/^[A-Z]{2,5}-\d{2,4}$/.test(code) && !out.includes(code)) out.push(code);
  }
  return out.slice(0, 12);
}

export function totalWithGst(items: Pick<PreviewItem, "price_with_gst_paise" | "priced">[]): number {
  return items.reduce((sum, i) => sum + (i.priced ? i.price_with_gst_paise : 0), 0);
}

export function fetchPreviewContext(opts: { assessment?: string | null; elder?: number | null }) {
  const q = new URLSearchParams();
  if (opts.assessment) q.set("assessment_id", opts.assessment);
  if (opts.elder) q.set("elder_id", String(opts.elder));
  return api<PreviewContext>(`${BASE}/context?${q}`);
}

export function createPreview(body: {
  assessment_id: string;
  source_document_id: number;
  room_type: string;
  package_level: string;
  product_codes: string[];
  force?: boolean;
}) {
  return api<PreviewJob>(`${BASE}/jobs`, { method: "POST", body: JSON.stringify(body) });
}

export function listPreviews(opts: { assessment?: string | null; elder?: number | null }) {
  const q = new URLSearchParams();
  if (opts.assessment) q.set("assessment_id", opts.assessment);
  if (opts.elder) q.set("elder_id", String(opts.elder));
  return api<PreviewJob[]>(`${BASE}/jobs?${q}`);
}

export function getPreview(id: string) {
  return api<PreviewJob>(`${BASE}/jobs/${encodeURIComponent(id)}`);
}

export function reviewPreview(id: string, action: "approve" | "reject" | "regenerate", notes?: string) {
  return api<PreviewJob>(`${BASE}/jobs/${encodeURIComponent(id)}/review`, {
    method: "POST",
    body: JSON.stringify({ action, notes }),
  });
}

export function fetchAiUsage() {
  return api<AiUsage>(`${BASE}/usage`);
}

export async function downloadPreview(id: string, kind: "pdf" | "image", family = false) {
  const base = family ? FAMILY : BASE + "/jobs";
  const path = `${base}/${encodeURIComponent(id)}/${kind === "pdf" ? "pdf" : "download"}`;
  const blob = await downloadFileBlob(path);
  const ext = kind === "pdf" ? "pdf" : blob.type.includes("png") ? "png" : "jpg";
  triggerBlobDownload(blob, `kushalaya-preview-${id}.${ext}`);
}

export function fetchFamilyPreviews() {
  return api<FamilyPreview[]>(FAMILY);
}

export function requestPreviewFixes(id: string, notes?: string) {
  return api<{ id: string; items: { product_code: string }[] }>(`${FAMILY}/${encodeURIComponent(id)}/request`, {
    method: "POST",
    body: JSON.stringify({ notes }),
  });
}

/** "Generating… 6 s of about 15 s" */
export function progressText(p: PreviewJob["progress"]): string {
  if (!p.running) return p.label;
  const el = p.elapsed_seconds ?? 0;
  return `${p.label} ${el} s · usually about ${p.estimate_seconds} s`;
}
