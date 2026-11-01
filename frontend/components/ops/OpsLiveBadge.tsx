import { caregiverLocationLinks, liveShort, type LiveOnTheWay } from "@/lib/live-location";
import "@/components/live-visit.css";

/** "12 min away", "arriving", "no location yet" — without "on the way" (the status badge says that). */
function etaOnly(live: LiveOnTheWay | null | undefined): string {
  if (!live) return "";
  if (!live.position) return "no location yet";
  const eta = live.eta_minutes === 0 ? "arriving" : live.eta_minutes != null ? `${live.eta_minutes} min away` : "";
  return [eta, live.stale ? "last seen a while ago" : ""].filter(Boolean).join(" · ");
}

/**
 * Ops Schedule / Dashboard: how far the caregiver is and a map link to where they are.
 * `withStatus`: an "On the way" badge is already next to it, so don't say it twice ("12 min away · Map").
 */
export function OpsLiveBadge({ live, withStatus = false }: { live: LiveOnTheWay | null | undefined; withStatus?: boolean }) {
  const map = live ? caregiverLocationLinks(live)[0] : undefined;
  const text = withStatus ? etaOnly(live) : liveShort(live);
  if (!text && !map) return null;
  return (
    <span className="lv-ops">
      {text ? <span>{text}</span> : null}
      {map ? (
        <a
          className="lv-ops-map"
          href={map.href}
          target="_blank"
          rel="noreferrer"
          onClick={(e) => e.stopPropagation()}
          title="Caregiver's location in Google Maps"
        >
          Map
        </a>
      ) : null}
    </span>
  );
}
