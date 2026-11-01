import { api } from "./api";

export type OpsDashboardSummary = {
  clients: number;
  assessments_open: number;
  assessments_total: number;
  visits_today: number;
  visits_total: number;
  catalog_items: number;
};

export type Client = {
  id: number;
  first_name: string;
  last_name: string;
  status: string;
  phone: string | null;
  address?: string | null;
  date_of_birth?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  family_published?: boolean;
  independence_score?: number | null;
  latest_assessment_id?: string | null;
  latest_assessment_status?: string | null;
  next_step?: string | null;
};

export type AssessmentSummary = {
  assessment_id: string;
  status: string;
  client_first_name: string;
  client_last_name: string;
  client_address: string;
  updated_at: string;
  completed_at: string | null;
  prospect_id: number | null;
  elder_id: number | null;
};

export type AssessmentDetail = {
  assessment_id: string;
  status: string;
  updated_at: string;
  completed_at: string | null;
  payload: {
    id: string;
    status: string;
    clientFirstName: string;
    clientLastName: string;
    clientAddress: string;
    clientPhone: string;
    clientEmail: string;
    familyContactName: string;
    familyContactPhone: string;
    assessorName: string;
    notes: string;
    elderId: number | null;
    ratings?: Record<string, string | null>;
  };
};

export type Visit = {
  id: string;
  visit_type: string;
  visited_at: string;
  staff_name: string | null;
  summary: string;
  wellness_notes: string;
  concerns: string[];
  recommendations: string;
  duration_minutes: number | null;
  status: string;
};

export type VisitWithClient = Visit & {
  elder_id: number;
  client_name: string;
};

export const VISIT_TYPES = [
  "Baseline profile",
  "Home safety assessment",
  "Wellness visit",
  "Wellness check-in",
  "Modification follow-up",
  "Product installation",
  "Other",
] as const;

export function clientName(c: Pick<Client, "first_name" | "last_name">) {
  return `${c.first_name} ${c.last_name}`.trim();
}

export async function fetchDashboard(): Promise<OpsDashboardSummary> {
  return api<OpsDashboardSummary>("/api/v1/home-safety/dashboard");
}

export async function fetchClients(): Promise<Client[]> {
  return api<Client[]>("/api/v1/elders");
}

export async function fetchClient(id: number): Promise<Client> {
  return api<Client>(`/api/v1/elders/${id}`);
}

export async function createClient(payload: {
  first_name: string;
  last_name: string;
  phone?: string;
  address?: string;
}): Promise<Client> {
  return api<Client>("/api/v1/elders", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchAssessments(): Promise<AssessmentSummary[]> {
  return api<AssessmentSummary[]>("/api/v1/home-safety/assessments");
}

export async function fetchAssessment(id: string): Promise<AssessmentDetail> {
  return api<AssessmentDetail>(`/api/v1/home-safety/assessments/${encodeURIComponent(id)}`, {
    headers: { "X-Activity-Intent": "view" },
  });
}

export async function createDraftAssessment(client: Client): Promise<AssessmentDetail> {
  const now = new Date().toISOString();
  const id = `hsa-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
  return api<AssessmentDetail>(`/api/v1/home-safety/assessments/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify({
      id,
      createdAt: now,
      updatedAt: now,
      completedAt: null,
      status: "draft",
      clientFirstName: client.first_name,
      clientLastName: client.last_name,
      clientAddress: client.address || "",
      clientPhone: client.phone || "",
      clientEmail: "",
      familyContactName: "",
      familyContactPhone: "",
      painPoints: "",
      assessorName: "",
      notes: "",
      residentProfile: {},
      ratings: {},
      itemNotes: {},
      prospectId: null,
      prospectSyncedAt: null,
      elderId: client.id,
      photos: [],
    }),
  });
}

export async function fetchVisits(elderId: number, days = 90): Promise<Visit[]> {
  return api<Visit[]>(`/api/v1/home-safety/visits?elder_id=${elderId}&days=${days}`);
}

export async function fetchAllVisits(clients: Client[], days = 90): Promise<VisitWithClient[]> {
  const batches = await Promise.all(
    clients.map(async (client) => {
      try {
        const visits = await fetchVisits(client.id, days);
        return visits.map((visit) => ({
          ...visit,
          elder_id: client.id,
          client_name: clientName(client),
        }));
      } catch {
        return [] as VisitWithClient[];
      }
    }),
  );
  return batches
    .flat()
    .sort((a, b) => new Date(b.visited_at).getTime() - new Date(a.visited_at).getTime());
}

export async function createVisit(payload: {
  elder_id: number;
  visit_type: string;
  summary?: string;
  wellness_notes?: string;
  staff_name?: string;
  status?: string;
  duration_minutes?: number | null;
  baseline?: { notes?: string };
}): Promise<Visit> {
  return api<Visit>("/api/v1/home-safety/visits", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
