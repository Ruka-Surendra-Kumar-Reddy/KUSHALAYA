import type { AssessmentPhoto, HomeSafetyAssessment } from "./assessment";
import { getPhotoPreviewBlob, savePhotoPreviewFromDataUrl } from "./photoPreviewStore";

export function isOrphanPhoto(photo: AssessmentPhoto): boolean {
  return !photo.documentId && !photo.localPreview && !photo.hasLocalPreview;
}

/** Strip heavy previews from data written to localStorage / sent to server metadata. */
export function stripPhotoForStorage(photo: AssessmentPhoto): AssessmentPhoto {
  const hasLocalPreview =
    photo.hasLocalPreview ?? Boolean(photo.localPreview && !photo.documentId);
  return {
    ...photo,
    localPreview: null,
    hasLocalPreview: photo.documentId ? false : hasLocalPreview,
  };
}

export function stripAssessmentForStorage(
  assessment: HomeSafetyAssessment,
): HomeSafetyAssessment {
  return {
    ...assessment,
    photos: (assessment.photos ?? []).map(stripPhotoForStorage),
  };
}

/** Restore object URLs from IndexedDB for pending photos. */
export async function hydratePhotoPreviews(
  assessment: HomeSafetyAssessment,
): Promise<HomeSafetyAssessment> {
  const photos = await Promise.all(
    (assessment.photos ?? []).map(async (photo) => {
      if (photo.documentId || photo.localPreview) return photo;
      if (!photo.hasLocalPreview) return photo;
      const blob = await getPhotoPreviewBlob(assessment.id, photo.id);
      if (!blob) {
        return { ...photo, hasLocalPreview: false };
      }
      return {
        ...photo,
        localPreview: URL.createObjectURL(blob),
      };
    }),
  );
  return { ...assessment, photos };
}

export async function persistPhotoPreviews(
  assessment: HomeSafetyAssessment,
): Promise<void> {
  await Promise.all(
    (assessment.photos ?? []).map(async (photo) => {
      if (!photo.localPreview || photo.documentId) return;
      await savePhotoPreviewFromDataUrl(assessment.id, photo.id, photo.localPreview);
    }),
  );
}
