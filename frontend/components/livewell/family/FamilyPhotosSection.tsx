"use client";

import { photoCaption } from "@/lib/livewell/familyWords";
import { familyDate } from "@/lib/livewell/familyTime";

import { useEffect, useState } from "react";
import { FamilyError } from "./FamilyError";
import { FamilyPhotoImage } from "./FamilyPhotoImage";
import { FamilyAiPreviews } from "./FamilyAiPreviews";
import {
  fetchFamilyPhotos,
  type FamilyPhoto,
} from "@/lib/livewell/familyApi";

/** Approved before/after pairs + assessment photos (on Score & plan, #photos). */
export function FamilyPhotosSection() {
  const [photos, setPhotos] = useState<FamilyPhoto[]>([]);
  const [error, setError] = useState("");

  function load() {
    setError("");
    fetchFamilyPhotos()
      .then(setPhotos)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <section id="photos" className="fh-anchor" aria-labelledby="family-photos-heading">
      <h2 id="family-photos-heading">Photos</h2>
      <FamilyError message={error} onRetry={load} what="the photos" />

      <section className="home-safety-section" aria-labelledby="family-approved-visuals-heading">
        <h3 id="family-approved-visuals-heading">Before and after</h3>
        <FamilyAiPreviews />
      </section>

      <section
        className="home-safety-section"
        style={{ marginTop: "1.25rem" }}
        aria-labelledby="family-assessment-photos-heading"
      >
        <h3 id="family-assessment-photos-heading">Assessment photos</h3>
        {photos.length === 0 ? (
          <div className="card home-safety-empty">
            <p>No photos yet.</p>
            <p className="muted" style={{ fontSize: "0.9rem", marginTop: "0.5rem" }}>
              Photos from the home safety assessment appear here after the visit.
            </p>
          </div>
        ) : (
          <ul className="home-safety-family-photo-grid">
            {photos.map((p) => (
              <li key={`${p.source ?? "x"}-${p.id}`}>
                <figure className="home-safety-family-photo">
                  {p.url ? (
                    p.url.startsWith("http") ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={p.url}
                        alt={photoCaption(p.caption)}
                        loading="lazy"
                        decoding="async"
                      />
                    ) : (
                      <FamilyPhotoImage
                        url={p.url}
                        alt={photoCaption(p.caption)}
                      />
                    )
                  ) : (
                    <div
                      className="home-safety-family-photo-placeholder"
                      role="img"
                      aria-label="No image available"
                    >
                      No image
                    </div>
                  )}
                  <figcaption>
                    <strong>{photoCaption(p.caption)}</strong>
                    <span className="muted">
                      {p.taken_at
                        ? familyDate(p.taken_at)
                        : ""}
                    </span>
                  </figcaption>
                </figure>
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}
