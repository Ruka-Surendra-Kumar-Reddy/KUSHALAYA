import { describe, expect, it } from "vitest";
import { assessmentPayloadForServer } from "./assessmentApi";
import { isOrphanPhoto, stripPhotoForStorage } from "./photoPersist";
import type { HomeSafetyAssessment } from "./assessment";

describe("photoPersist", () => {
  it("flags hasLocalPreview when stripping data URL", () => {
    const stripped = stripPhotoForStorage({
      id: "p1",
      caption: "",
      roomType: null,
      localPreview: "data:image/jpeg;base64,abc",
      documentId: null,
      uploadedAt: null,
    });
    expect(stripped.localPreview).toBeNull();
    expect(stripped.hasLocalPreview).toBe(true);
  });

  it("detects orphan photos", () => {
    expect(
      isOrphanPhoto({
        id: "x",
        caption: "",
        roomType: null,
        localPreview: null,
        documentId: null,
        uploadedAt: null,
      }),
    ).toBe(true);
  });
});

describe("assessmentPayloadForServer", () => {
  it("only sends synced photos to the server", () => {
    const assessment = {
      id: "hs-1",
      photos: [
        {
          id: "local",
          caption: "",
          roomType: null,
          localPreview: null,
          hasLocalPreview: true,
          documentId: null,
          uploadedAt: null,
        },
        {
          id: "synced",
          caption: "",
          roomType: null,
          localPreview: null,
          documentId: 42,
          uploadedAt: "2026-01-01T00:00:00Z",
        },
      ],
    } as HomeSafetyAssessment;

    const payload = assessmentPayloadForServer(assessment);
    expect(payload.photos).toHaveLength(1);
    expect(payload.photos[0].documentId).toBe(42);
  });
});
