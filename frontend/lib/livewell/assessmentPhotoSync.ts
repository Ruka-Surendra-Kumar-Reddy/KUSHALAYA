import type { AssessmentCategory, AssessmentPhoto, HomeSafetyAssessment } from "./assessment";
import { normalizeAssessment } from "./assessment";
import { uploadHomeSafetyPhoto, deleteHomeSafetyPhoto, getPhotoBlobForUpload } from "./photos";
import { ensureAssessmentCustomerLink, isPipelineSyncAvailable } from "./syncProspect";
import { persistAssessmentWithSync, persistDraftWithSync } from "./assessmentSync";
import {
  isOrphanPhoto,
  persistPhotoPreviews,
  stripAssessmentForStorage,
} from "./photoPersist";
import { deletePhotoPreview } from "./photoPreviewStore";

/** Merge photo lists — keep local previews when server row has no document yet. */
export function mergeAssessmentPhotos(
  local: HomeSafetyAssessment | null,
  remote: HomeSafetyAssessment,
): AssessmentPhoto[] {
  const localById = new Map((local?.photos ?? []).map((p) => [p.id, p]));
  const merged: AssessmentPhoto[] = [];

  for (const remotePhoto of remote.photos ?? []) {
    const localPhoto = localById.get(remotePhoto.id);
    if (!localPhoto && isOrphanPhoto(remotePhoto)) {
      continue;
    }
    if (localPhoto?.hasLocalPreview && !remotePhoto.documentId) {
      merged.push({
        ...remotePhoto,
        hasLocalPreview: true,
        localPreview: localPhoto.localPreview,
      });
    } else if (localPhoto?.localPreview && !remotePhoto.documentId) {
      merged.push({ ...remotePhoto, localPreview: localPhoto.localPreview });
    } else {
      merged.push(remotePhoto);
    }
    localById.delete(remotePhoto.id);
  }

  for (const leftover of localById.values()) {
    if (isOrphanPhoto(leftover)) continue;
    merged.push(leftover);
  }

  return merged;
}

export function mergeAssessments(
  local: HomeSafetyAssessment | null,
  remote: HomeSafetyAssessment,
): HomeSafetyAssessment {
  const photos = mergeAssessmentPhotos(local, remote);
  const localNewer =
    local != null &&
    new Date(local.updatedAt).getTime() >= new Date(remote.updatedAt).getTime();
  const base = localNewer && local ? { ...local } : { ...remote };
  return normalizeAssessment({ ...base, photos });
}

async function ensureProspectForPhotos(
  assessment: HomeSafetyAssessment,
  _categories: AssessmentCategory[],
): Promise<HomeSafetyAssessment> {
  if (assessment.prospectId || assessment.elderId) {
    return assessment;
  }
  const linked = await ensureAssessmentCustomerLink(assessment);
  return persistDraftWithSync(linked);
}

/** Upload one pending photo; returns updated assessment or null if still local-only. */
export async function uploadPendingAssessmentPhoto(
  assessment: HomeSafetyAssessment,
  photo: AssessmentPhoto,
  categories: AssessmentCategory[],
): Promise<HomeSafetyAssessment | null> {
  if (photo.documentId) return null;
  if (!isPipelineSyncAvailable()) return null;

  let ctx = await ensureProspectForPhotos(assessment, categories);
  if (!ctx.prospectId && !ctx.elderId) return null;

  const blob = await getPhotoBlobForUpload(ctx.id, photo);
  if (!blob) return null;

  const documentId = await uploadHomeSafetyPhoto(blob, {
    fileName: `home-safety-${photo.id}.jpg`,
    assessmentId: ctx.id,
    prospectId: ctx.elderId ? null : ctx.prospectId,
    elderId: ctx.elderId ?? undefined,
    caption: photo.caption,
    roomType: photo.roomType ?? undefined,
  });

  await deletePhotoPreview(ctx.id, photo.id);

  const uploadedPhoto: AssessmentPhoto = {
    ...photo,
    documentId,
    uploadedAt: new Date().toISOString(),
    localPreview: null,
    hasLocalPreview: false,
  };
  const photos = (ctx.photos ?? []).map((p) => (p.id === photo.id ? uploadedPhoto : p));
  return { ...ctx, photos };
}

/** Persist photo changes for draft or completed assessments (keeps status). */
export async function persistAssessmentPhotos(
  assessment: HomeSafetyAssessment,
): Promise<HomeSafetyAssessment> {
  await persistPhotoPreviews(assessment);
  const stripped = stripAssessmentForStorage(assessment);
  if (assessment.status === "completed") {
    return persistAssessmentWithSync(stripped);
  }
  return persistDraftWithSync(stripped);
}

export async function persistDraftImmediately(
  assessment: HomeSafetyAssessment,
): Promise<HomeSafetyAssessment> {
  return persistAssessmentPhotos(assessment);
}

export function queuePhotoUpload(
  assessment: HomeSafetyAssessment,
  photo: AssessmentPhoto,
  categories: AssessmentCategory[],
  onUpdated: (next: HomeSafetyAssessment) => void,
): void {
  void uploadPendingAssessmentPhoto(assessment, photo, categories)
    .then(async (uploaded) => {
      if (!uploaded) return;
      const saved = await persistDraftImmediately(uploaded);
      onUpdated({ ...saved, photos: uploaded.photos });
    })
    .catch(() => {
      /* keep local preview — user can retry on save */
    });
}

export async function removeAssessmentPhoto(
  assessmentId: string,
  photo: AssessmentPhoto,
): Promise<void> {
  await deletePhotoPreview(assessmentId, photo.id);
  if (photo.documentId) {
    await deleteHomeSafetyPhoto(photo.documentId);
  }
}
