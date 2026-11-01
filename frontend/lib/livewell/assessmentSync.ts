import { getStoredAuth } from "@/lib/api";
import type { HomeSafetyAssessment } from "./assessment";
import { normalizeAssessment } from "./assessment";
import {
  deleteServerAssessment,
  fetchServerAssessment,
  fetchServerAssessments,
  upsertServerAssessment,
} from "./assessmentApi";
import { mergeAssessments } from "./assessmentPhotoSync";
import {
  deleteAssessment,
  getAssessment,
  listAssessments,
  saveAssessmentState,
  cacheAssessmentState,
  saveDraftAssessment,
} from "./storage";

const SYNC_DEBOUNCE_MS = 1500;
const pendingTimers = new Map<string, ReturnType<typeof setTimeout>>();

export function isAssessmentServerSyncAvailable(): boolean {
  return Boolean(getStoredAuth()?.access_token);
}

/** Debounced PUT — keeps localStorage as source of truth; server mirrors for cross-device. */
export function queueAssessmentServerSync(assessment: HomeSafetyAssessment): void {
  if (!isAssessmentServerSyncAvailable()) return;

  const existing = pendingTimers.get(assessment.id);
  if (existing) clearTimeout(existing);

  pendingTimers.set(
    assessment.id,
    setTimeout(() => {
      pendingTimers.delete(assessment.id);
      void upsertServerAssessment(assessment).catch(() => {
        /* offline or session expired — local draft remains */
      });
    }, SYNC_DEBOUNCE_MS),
  );
}

export async function loadAssessmentMerged(id: string): Promise<HomeSafetyAssessment | null> {
  const local = getAssessment(id);

  if (!isAssessmentServerSyncAvailable()) {
    return local;
  }

  try {
    const server = await fetchServerAssessment(id, { activityIntent: "open" });
    if (!server) return local;
    if (!local) {
      cacheAssessmentState(server);
      return server;
    }

    const merged = mergeAssessments(local, server);
    cacheAssessmentState(merged);

    if (new Date(local.updatedAt).getTime() > new Date(server.updatedAt).getTime()) {
      queueAssessmentServerSync(merged);
    }

    return merged;
  } catch {
    return local;
  }
}

export async function listAssessmentsMerged(): Promise<HomeSafetyAssessment[]> {
  const local = listAssessments();

  if (!isAssessmentServerSyncAvailable()) {
    return local;
  }

  try {
    // One request with full payloads (was one extra request per assessment).
    const summaries = await fetchServerAssessments({ full: true });
    const serverIds = new Set(summaries.map((s) => s.assessment_id));
    const merged = [...local];
    const missing: string[] = [];

    for (const summary of summaries) {
      const existing = merged.find((a) => a.id === summary.assessment_id);
      const full = summary.payload ? normalizeAssessment(summary.payload) : null;
      if (!full) {
        if (!existing) missing.push(summary.assessment_id);
        continue;
      }
      if (existing) {
        const combined = mergeAssessments(existing, full);
        const idx = merged.findIndex((a) => a.id === summary.assessment_id);
        merged[idx] = combined;
        cacheAssessmentState(combined);
      } else {
        cacheAssessmentState(full);
        merged.push(full);
      }
    }
    // Older servers without full=true: fetch the missing ones in parallel.
    const fetched = await Promise.all(missing.map((id) => fetchServerAssessment(id)));
    for (const full of fetched) {
      if (!full) continue;
      cacheAssessmentState(full);
      merged.push(full);
    }

    for (const item of local) {
      if (!serverIds.has(item.id)) {
        queueAssessmentServerSync(item);
      }
    }

    return merged.sort(
      (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
    );
  } catch {
    return local;
  }
}

export function persistDraftWithSync(assessment: HomeSafetyAssessment): HomeSafetyAssessment {
  const saved = saveDraftAssessment(assessment);
  queueAssessmentServerSync(saved);
  return saved;
}

export function persistAssessmentWithSync(
  assessment: HomeSafetyAssessment,
): HomeSafetyAssessment {
  const saved = saveAssessmentState(assessment);
  queueAssessmentServerSync(saved);
  return saved;
}

export async function deleteAssessmentEverywhere(id: string): Promise<void> {
  deleteAssessment(id);
  if (isAssessmentServerSyncAvailable()) {
    try {
      await deleteServerAssessment(id);
    } catch {
      /* local already removed */
    }
  }
}
