import type { HomeSafetyAssessment, LegacyHomeSafetyAssessment } from "./assessment";
import { normalizeAssessment } from "./assessment";
import { stripAssessmentForStorage } from "./photoPersist";
import { readLocalStorageWithLegacy, removeLocalStorageKeys } from "./legacyStorage";

const STORAGE_KEY = "safehome_home_safety_assessments_v1";
const LEGACY_STORAGE_KEYS = ["eldercare_home_safety_assessments_v1"];

function migrateAssessment(raw: LegacyHomeSafetyAssessment): HomeSafetyAssessment {
  return normalizeAssessment(raw);
}

function readAll(): HomeSafetyAssessment[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = readLocalStorageWithLegacy(STORAGE_KEY, LEGACY_STORAGE_KEYS);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as LegacyHomeSafetyAssessment[];
    return Array.isArray(parsed) ? parsed.map(migrateAssessment) : [];
  } catch {
    return [];
  }
}

function writeAll(list: HomeSafetyAssessment[]): void {
  if (typeof window === "undefined") return;
  const slim = list.map(stripAssessmentForStorage);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(slim));
    removeLocalStorageKeys(...LEGACY_STORAGE_KEYS);
  } catch {
    /* last resort — drop pending photo rows that have no server document */
    const metaOnly = slim.map((a) => ({
      ...a,
      photos: (a.photos ?? []).filter((p) => p.documentId != null),
    }));
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(metaOnly));
      removeLocalStorageKeys(...LEGACY_STORAGE_KEYS);
    } catch {
      /* give up — assessment text still lost if quota exceeded */
    }
  }
}

export function listAssessments(opts?: { includeDrafts?: boolean }): HomeSafetyAssessment[] {
  const includeDrafts = opts?.includeDrafts ?? true;
  return readAll()
    .filter((a) => includeDrafts || a.status === "completed")
    .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
}

export function listCompletedAssessments(): HomeSafetyAssessment[] {
  return listAssessments({ includeDrafts: false }).filter((a) => a.status === "completed");
}

export function listDraftAssessments(): HomeSafetyAssessment[] {
  return readAll().filter((a) => a.status === "draft");
}

export function getAssessment(id: string): HomeSafetyAssessment | null {
  return readAll().find((a) => a.id === id) ?? null;
}

/** Persist draft progress (auto-save while scoring). */
export function saveDraftAssessment(assessment: HomeSafetyAssessment): HomeSafetyAssessment {
  const updated: HomeSafetyAssessment = {
    ...assessment,
    status: "draft",
    completedAt: null,
    updatedAt: new Date().toISOString(),
  };
  const list = readAll();
  const idx = list.findIndex((a) => a.id === updated.id);
  if (idx >= 0) list[idx] = updated;
  else list.push(updated);
  writeAll(list);
  return updated;
}

/** Final save — marks assessment complete and appears in saved list. */
export function completeAssessment(assessment: HomeSafetyAssessment): HomeSafetyAssessment {
  const now = new Date().toISOString();
  const updated: HomeSafetyAssessment = {
    ...assessment,
    status: "completed",
    completedAt: now,
    updatedAt: now,
  };
  const list = readAll();
  const idx = list.findIndex((a) => a.id === updated.id);
  if (idx >= 0) list[idx] = updated;
  else list.push(updated);
  writeAll(list);
  return updated;
}

export function deleteAssessment(id: string): void {
  writeAll(readAll().filter((a) => a.id !== id));
}

export function linkAssessmentProspect(
  assessmentId: string,
  prospectId: number | null,
  elderId?: number | null,
): HomeSafetyAssessment | null {
  const list = readAll();
  const idx = list.findIndex((a) => a.id === assessmentId);
  if (idx < 0) return null;
  const updated: HomeSafetyAssessment = {
    ...list[idx],
    prospectId,
    elderId: elderId ?? list[idx].elderId,
    prospectSyncedAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
  list[idx] = updated;
  writeAll(list);
  return updated;
}

/** Persist assessment fields after save (including photo sync). */
/** Cache a copy fetched from the server as-is (keeps updatedAt, so opening is not an edit). */
export function cacheAssessmentState(assessment: HomeSafetyAssessment): HomeSafetyAssessment {
  const list = readAll();
  const idx = list.findIndex((a) => a.id === assessment.id);
  if (idx >= 0) list[idx] = assessment;
  else list.push(assessment);
  writeAll(list);
  return assessment;
}

export function saveAssessmentState(assessment: HomeSafetyAssessment): HomeSafetyAssessment {
  const list = readAll();
  const idx = list.findIndex((a) => a.id === assessment.id);
  const updated = { ...assessment, updatedAt: new Date().toISOString() };
  if (idx >= 0) list[idx] = updated;
  else list.push(updated);
  writeAll(list);
  return updated;
}
