import { api, getApiUrl, getStoredAuth, postFormData } from "@/lib/api";
import { getElderProspect } from "@/lib/prospects";
import type { AssessmentPhoto, HomeSafetyAssessment } from "./assessment";
import { deletePhotoPreview, getPhotoPreviewBlob } from "./photoPreviewStore";

export type UploadedPhoto = {
  photoId: string;
  documentId: number;
};

export async function uploadHomeSafetyPhoto(
  file: Blob,
  opts: {
    fileName: string;
    assessmentId: string;
    prospectId?: number | null;
    elderId?: number | null;
    caption?: string;
    roomType?: string | null;
  },
): Promise<number> {
  const form = new FormData();
  form.append("file", file, opts.fileName);
  form.append("assessment_id", opts.assessmentId);
  if (opts.prospectId) form.append("prospect_id", String(opts.prospectId));
  if (opts.elderId) form.append("elder_id", String(opts.elderId));
  if (opts.caption) form.append("caption", opts.caption);
  if (opts.roomType) form.append("room_type", opts.roomType);

  const doc = await postFormData<{ id: number }>("/api/v1/home-safety/photos", form);
  return doc.id;
}

export async function deleteHomeSafetyPhoto(documentId: number): Promise<void> {
  if (!getStoredAuth()?.access_token) return;
  await api(`/api/v1/documents/${documentId}`, { method: "DELETE" });
}

/** Blob for upload — data URL in memory, else IndexedDB. */
export async function getPhotoBlobForUpload(
  assessmentId: string,
  photo: AssessmentPhoto,
): Promise<Blob | null> {
  if (photo.localPreview) {
    const res = await fetch(photo.localPreview);
    return res.blob();
  }
  if (photo.hasLocalPreview) {
    return getPhotoPreviewBlob(assessmentId, photo.id);
  }
  return null;
}

export async function resolveElderIdForProspect(prospectId: number): Promise<number | null> {
  const prospect = await getElderProspect(prospectId);
  return prospect.converted_elder_id ?? null;
}

/** Upload pending local photos after assessment save (requires staff sign-in). */
export async function syncAssessmentPhotos(
  assessment: HomeSafetyAssessment,
): Promise<HomeSafetyAssessment> {
  if (!getStoredAuth()?.access_token) return assessment;

  let elderId = assessment.elderId;
  if (!elderId && assessment.prospectId) {
    elderId = await resolveElderIdForProspect(assessment.prospectId);
  }

  const pending = assessment.photos.filter(
    (p) => !p.documentId && (p.localPreview || p.hasLocalPreview),
  );
  if (pending.length === 0) {
    return elderId !== assessment.elderId ? { ...assessment, elderId } : assessment;
  }

  if (!assessment.prospectId && !elderId) {
    throw new Error("Save assessment to pipeline before uploading photos.");
  }

  const updatedPhotos: AssessmentPhoto[] = [...assessment.photos];
  for (const photo of pending) {
    const blob = await getPhotoBlobForUpload(assessment.id, photo);
    if (!blob) continue;
    const documentId = await uploadHomeSafetyPhoto(blob, {
      fileName: `home-safety-${photo.id}.jpg`,
      assessmentId: assessment.id,
      prospectId: elderId ? null : assessment.prospectId,
      elderId: elderId ?? undefined,
      caption: photo.caption,
      roomType: photo.roomType ?? undefined,
    });
    const idx = updatedPhotos.findIndex((p) => p.id === photo.id);
    if (idx >= 0) {
      await deletePhotoPreview(assessment.id, photo.id);
      updatedPhotos[idx] = {
        ...updatedPhotos[idx],
        documentId,
        uploadedAt: new Date().toISOString(),
        localPreview: null,
        hasLocalPreview: false,
      };
    }
  }

  return { ...assessment, elderId, photos: updatedPhotos };
}

export function familyPhotoImageUrl(documentId: number): string {
  return `${getApiUrl()}/api/v1/home-safety/family/photos/${documentId}/image`;
}

export async function fetchFamilyPhotoBlob(relativeOrAbsoluteUrl: string): Promise<string> {
  if (relativeOrAbsoluteUrl.startsWith("http")) {
    return relativeOrAbsoluteUrl;
  }
  const auth = getStoredAuth();
  const url = `${getApiUrl()}${relativeOrAbsoluteUrl}`;
  const res = await fetch(url, {
    headers: auth?.access_token ? { Authorization: `Bearer ${auth.access_token}` } : {},
  });
  if (!res.ok) throw new Error("Could not load photo");
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}
