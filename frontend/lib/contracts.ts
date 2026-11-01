/** Contracts signed in the app (backend: app/api/v1/contracts.py, app/livewell/contracts.py). */
import { api, getApiUrl, getStoredAuth, postFormData } from "@/lib/api";
import { trackUrl } from "@/lib/live-location";

export type ContractKind = "vendor" | "client";
export type ContractStatus = "draft" | "awaiting_company" | "sent" | "viewed" | "signed" | "expired" | "cancelled";

export type Placeholder = { key: string; label: string; kinds: ContractKind[] };
export type Signatory = {
  name: string;
  designation: string;
  signature_kind: "drawn" | "typed";
  signature_png: string | null;
  signature_text: string | null;
  updated_at: string | null;
};
export type ContractsMeta = {
  kinds: { code: ContractKind; label: string }[];
  placeholders: Placeholder[];
  can_sign: boolean;
  signatory: Signatory | null;
  link_days: number;
  my_name: string;
};
export type ContractTemplate = {
  id: number;
  kind: ContractKind;
  kind_label: string;
  group_key: string;
  version: number;
  is_current: boolean;
  archived: boolean;
  title: string;
  body: string;
  is_placeholder: boolean;
  created_at: string | null;
  created_by: string;
};
export type Contract = {
  id: number;
  ref: string;
  kind: ContractKind;
  kind_label: string;
  elder_id: number | null;
  vendor_id: number | null;
  party_name: string;
  title: string;
  status: ContractStatus;
  template_version: number | null;
  signer_name: string;
  signer_email: string | null;
  signer_mobile: string | null;
  signer_relation: string | null;
  created_at: string | null;
  sent_at: string | null;
  viewed_at: string | null;
  signed_at: string | null;
  expires_at: string | null;
  company_signer_name: string | null;
  company_signer_designation: string | null;
  company_signed_at: string | null;
  locked: boolean;
  has_pdf: boolean;
  sign_path: string | null;
  created_by: string;
  body?: string;
};
export type Preview = {
  template_id: number;
  template_version: number;
  title: string;
  body: string;
  fields: Record<string, string>;
  missing: string[];
  suggested_signers: { name: string; email: string; mobile: string; relation: string }[];
};
export type SignatureBlock = {
  name: string | null;
  designation?: string | null;
  signed_at: string | null;
  signed_at_ist: string;
  signature_kind: "drawn" | "typed" | null;
  signature_png: string | null;
  signature_text: string | null;
};
export type PublicContract = {
  ref: string;
  kind: ContractKind;
  party_label: string;
  title: string;
  body: string;
  status: "sent" | "viewed" | "signed";
  signer_name: string;
  company_name: string;
  expires_at: string | null;
  company: SignatureBlock;
  signer: SignatureBlock | null;
  text_sha256: string | null;
};

export const STATUS_LABEL: Record<ContractStatus, string> = {
  draft: "Draft",
  awaiting_company: "Waiting for KushAlaya signature",
  sent: "Sent",
  viewed: "Viewed",
  signed: "Signed by both",
  expired: "Expired",
  cancelled: "Cancelled",
};

const J = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

export const contractsMeta = () => api<ContractsMeta>("/api/v1/contracts/meta");
export const listTemplates = (kind?: ContractKind, includeArchived = false) =>
  api<ContractTemplate[]>(`/api/v1/contracts/templates?${new URLSearchParams({
    ...(kind ? { kind } : {}),
    ...(includeArchived ? { include_archived: "true" } : {}),
  })}`);
export const templateVersions = (id: number) => api<ContractTemplate[]>(`/api/v1/contracts/templates/${id}/versions`);
export const createTemplate = (t: { kind: ContractKind; title: string; body: string }) =>
  api<ContractTemplate>("/api/v1/contracts/templates", J(t));
export const updateTemplate = (id: number, t: { title: string; body: string }) =>
  api<ContractTemplate>(`/api/v1/contracts/templates/${id}`, { method: "PUT", body: JSON.stringify(t) });
export const archiveTemplate = (id: number, archived: boolean) =>
  api<ContractTemplate>(`/api/v1/contracts/templates/${id}/archive?archived=${archived}`, { method: "POST" });
export function importDocx(file: File) {
  const fd = new FormData();
  fd.append("file", file);
  return postFormData<{ text: string; file_name: string }>("/api/v1/contracts/templates/import-docx", fd);
}
export const saveSignatory = (s: { name: string; designation: string; signature_png: string | null; signature_text: string | null }) =>
  api<Signatory>("/api/v1/contracts/signatory", { method: "PUT", body: JSON.stringify(s) });

export type PartyRef = { elder_id?: number; vendor_id?: number };
export const previewContract = (b: PartyRef & { template_id: number; signer_name?: string; fields?: Record<string, string> }) =>
  api<Preview>("/api/v1/contracts/preview", J(b));
export const listContracts = (q: PartyRef & { status?: string } = {}) =>
  api<Contract[]>(`/api/v1/contracts?${new URLSearchParams(
    Object.entries(q).filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => [k, String(v)]),
  )}`);
export const createContract = (
  b: PartyRef & {
    template_id: number;
    signer_name: string;
    signer_email: string | null;
    signer_mobile: string | null;
    signer_relation: string | null;
    fields: Record<string, string>;
    title?: string;
    body?: string;
    action: "draft" | "submit" | "sign_and_send";
  },
) => api<Contract>("/api/v1/contracts", J(b));
export const getContract = (id: number) => api<Contract>(`/api/v1/contracts/${id}`);
export const contractAction = (id: number, action: "submit" | "sign-and-send" | "resend" | "cancel") =>
  api<Contract>(`/api/v1/contracts/${id}/${action}`, { method: "POST" });

/** Full signing-link URL on the family host (same rule as live tracking links). */
export const signUrl = (path: string | null | undefined) => trackUrl(path);

export function whatsappHref(c: Contract): string {
  const url = signUrl(c.sign_path);
  const text = `Dear ${c.signer_name}, please read and sign “${c.title}” from KushAlaya: ${url}`;
  const phone = (c.signer_mobile || "").replace(/\D/g, "");
  const to = phone.length === 10 ? `91${phone}` : phone;
  return `https://wa.me/${to}?text=${encodeURIComponent(text)}`;
}

async function downloadPdf(path: string, name: string, auth = true) {
  const headers: Record<string, string> = {};
  const token = getStoredAuth()?.access_token;
  if (auth && token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${getApiUrl()}${path}`, { headers });
  if (!res.ok) throw new Error("Could not download the signed PDF");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

export const downloadContractPdf = (c: { id: number; ref: string }) =>
  downloadPdf(`/api/v1/contracts/${c.id}/pdf`, `${c.ref}-signed.pdf`);
export const downloadFamilyContractPdf = (c: { id: number; ref: string }) =>
  downloadPdf(`/api/v1/home-safety/family/contracts/${c.id}/pdf`, `${c.ref}-signed.pdf`);
export const downloadPublicContractPdf = (token: string, ref: string) =>
  downloadPdf(`/api/v1/home-safety/sign/${encodeURIComponent(token)}/pdf`, `${ref}-signed.pdf`, false);

export type FamilyContract = { id: number; ref: string; title: string; signed_at: string | null; signed_name: string | null; company_signer_name: string | null };
export const listFamilyContracts = () => api<FamilyContract[]>("/api/v1/home-safety/family/contracts");

/** Split contract text into blocks for display: "# Heading" lines and paragraphs. */
export function contractBlocks(body: string): { heading: boolean; text: string }[] {
  return body
    .replace(/\r\n/g, "\n")
    .split(/\n\s*\n/)
    .map((b) => b.trim())
    .filter(Boolean)
    .flatMap((b) => {
      if (!b.startsWith("#")) return [{ heading: false, text: b }];
      // "# Heading" is its first line; anything under it is a paragraph.
      const [first, ...rest] = b.split("\n");
      const under = rest.join("\n").trim();
      const out = [{ heading: true, text: first.replace(/^#+\s*/, "") }];
      if (under) out.push({ heading: false, text: under });
      return out;
    });
}

/** Fill {placeholders} for the editor's live preview (unknown keys stay as they are). */
export function fillPlaceholders(text: string, values: Record<string, string>, known: Set<string>): string {
  return text.replace(/\{([a-z_]+)\}/g, (m, k: string) => (known.has(k) ? values[k]?.trim() || "__________" : m));
}
