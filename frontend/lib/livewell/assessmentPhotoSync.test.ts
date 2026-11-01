import { describe, expect, it } from "vitest";
import { mergeAssessmentPhotos, mergeAssessments } from "./assessmentPhotoSync";
import type { HomeSafetyAssessment } from "./assessment";

const base = (overrides: Partial<HomeSafetyAssessment> = {}): HomeSafetyAssessment =>
  ({
    id: "hs-1",
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    completedAt: null,
    status: "draft",
    clientFirstName: "A",
    clientLastName: "",
    clientAddress: "",
    clientPhone: "",
    clientEmail: "",
    familyContactName: "",
    familyContactPhone: "",
    painPoints: "",
    assessorName: "",
    notes: "",
    residentProfile: {
      medicalConditions: [],
      smartHomeAssessment: true,
      smartHomeAdvanced: false,
      hasBalcony: true,
    },
    ratings: {},
    itemNotes: {},
    prospectId: null,
    prospectSyncedAt: null,
    elderId: null,
    photos: [],
    ...overrides,
  }) as HomeSafetyAssessment;

describe("mergeAssessmentPhotos", () => {
  it("keeps local preview when server stripped it", () => {
    const local = base({
      photos: [
        {
          id: "p1",
          caption: "",
          roomType: null,
          localPreview: "data:image/jpeg;base64,abc",
          hasLocalPreview: true,
          documentId: null,
          uploadedAt: null,
        },
      ],
    });
    const remote = base({
      photos: [
        {
          id: "p1",
          caption: "",
          roomType: null,
          localPreview: null,
          documentId: null,
          uploadedAt: null,
        },
      ],
    });
    const merged = mergeAssessmentPhotos(local, remote);
    expect(merged[0].localPreview).toBe("data:image/jpeg;base64,abc");
  });

  it("keeps local-only photos not yet on server", () => {
    const local = base({
      photos: [
        {
          id: "p2",
          caption: "bath",
          roomType: "bathroom",
          localPreview: "data:image/jpeg;base64,xyz",
          hasLocalPreview: true,
          documentId: null,
          uploadedAt: null,
        },
      ],
    });
    const remote = base({ photos: [] });
    const merged = mergeAssessments(local, remote);
    expect(merged.photos).toHaveLength(1);
    expect(merged.photos[0].id).toBe("p2");
  });

  it("drops server ghost photos with no image and no document", () => {
    const local = base({ photos: [] });
    const remote = base({
      photos: [
        {
          id: "ghost",
          caption: "",
          roomType: "bathroom",
          localPreview: null,
          documentId: null,
          uploadedAt: null,
        },
      ],
    });
    const merged = mergeAssessmentPhotos(local, remote);
    expect(merged).toHaveLength(0);
  });

  it("keeps IndexedDB-backed photos via hasLocalPreview", () => {
    const local = base({
      photos: [
        {
          id: "p3",
          caption: "",
          roomType: "bathroom",
          localPreview: null,
          hasLocalPreview: true,
          documentId: null,
          uploadedAt: null,
        },
      ],
    });
    const remote = base({ photos: [] });
    const merged = mergeAssessments(local, remote);
    expect(merged.photos).toHaveLength(1);
    expect(merged.photos[0].hasLocalPreview).toBe(true);
  });
});
