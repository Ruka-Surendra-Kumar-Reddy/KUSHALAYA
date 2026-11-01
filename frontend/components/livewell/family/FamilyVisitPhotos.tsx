"use client";

import { useAuthedImage } from "@/components/useAuthedImage";
import { familyDate } from "@/lib/livewell/familyTime";
import type { FamilyVisitPhoto } from "@/lib/livewell/familyApi";

/** Photos the caregiver took on a visit. Renders nothing when there are none.
 *  `compact`: up to 3 small thumbnails (+N more) with no links of their own — for
 *  a feed card that already links to the visit page. `total` = all photos on the visit. */
export function FamilyVisitPhotos({
  photos,
  visitedAt,
  compact = false,
  total,
}: {
  photos: FamilyVisitPhoto[];
  visitedAt: string;
  compact?: boolean;
  total?: number;
}) {
  if (!photos.length) return null;
  const fallbackAlt = `Photo from the visit on ${familyDate(visitedAt)}`;
  if (compact) {
    const few = photos.slice(0, 3);
    const more = Math.max((total ?? photos.length) - few.length, 0);
    return (
      <ul className="fh-visit-thumbs" aria-label="Visit photos">
        {few.map((p) => (
          <VisitPhoto key={p.id} photo={p} alt={p.caption || fallbackAlt} compact />
        ))}
        {more > 0 ? <li className="fh-visit-thumbs-more">+{more} more</li> : null}
      </ul>
    );
  }
  return (
    <section className="home-safety-visit-section" aria-labelledby="visit-photos-heading">
      <h3 id="visit-photos-heading">Photos</h3>
      <ul className="home-safety-family-visit-photos fh-visit-photos">
        {photos.map((p) => (
          <VisitPhoto key={p.id} photo={p} alt={p.caption || fallbackAlt} />
        ))}
      </ul>
    </section>
  );
}

function VisitPhoto({ photo, alt, compact = false }: { photo: FamilyVisitPhoto; alt: string; compact?: boolean }) {
  // Photo endpoints need the bearer token, so the image is loaded as a blob URL.
  const src = useAuthedImage(photo.url);
  if (compact) {
    return (
      <li>
        {src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={src} alt={alt} loading="lazy" />
        ) : (
          <span className="fh-visit-photo-loading" role="img" aria-label={alt} />
        )}
      </li>
    );
  }
  return (
    <li>
      {src ? (
        <a href={src} target="_blank" rel="noopener noreferrer" aria-label={`Open full photo: ${alt}`}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={src} alt={alt} loading="lazy" />
        </a>
      ) : (
        <span className="fh-visit-photo-loading" role="img" aria-label={alt} />
      )}
    </li>
  );
}
