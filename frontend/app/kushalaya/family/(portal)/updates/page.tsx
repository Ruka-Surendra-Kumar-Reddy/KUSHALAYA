"use client";

import { FamilyLink as Link } from "@/components/livewell/family/FamilyLink";
import { Fragment, useEffect, useState } from "react";
import { FamilyShell } from "@/components/livewell/family/FamilyShell";
import { FamilyError } from "@/components/livewell/family/FamilyError";
import { FamilyVisitPhotos } from "@/components/livewell/family/FamilyVisitPhotos";
import { familyClock, familyDate, tidyDates } from "@/lib/livewell/familyTime";
import { collapseVisitChains, mergeVisitReports, splitFeedBody, tidyMissedVisits } from "@/lib/livewell/familyFeed";
import { plainWords } from "@/lib/livewell/familyWords";
import { useFamilyTimezone } from "@/lib/family-zone";
import { rewordFindingLines } from "@/lib/livewell/familyFindings";
import {
  familyApi,
  fetchFamilyCareFeed,
  type FamilyCareFeedItem,
  type FamilyStatus,
} from "@/lib/livewell/familyApi";
import { isStatusVisit, withNotedChanges } from "@/lib/livewell/familyStatus";
import { forSelf, useFamilySelf } from "@/lib/livewell/familySelf";

// One scrollable row; a chip shows only when it has something, all with counts.
const FILTERS = [
  { id: "all", label: "All" },
  { id: "visit", label: "Visits" },
  { id: "request", label: "Requests" },
  { id: "wellness", label: "KushLife" },
  { id: "update", label: "Updates" },
  { id: "alert", label: "Alerts" },
  { id: "message", label: "Messages" },
  { id: "photos", label: "Photos" },
];

function kindLabel(kind: string) {
  if (kind === "visit") return "Visit";
  if (kind === "wellness") return "KushLife";
  if (kind === "alert") return "Alert";
  if (kind === "message") return "Message";
  if (kind === "update") return "Update";
  return kind;
}

export default function FamilyUpdatesPage() {
  const [items, setItems] = useState<FamilyCareFeedItem[]>([]);
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState("");
  const tz = useFamilyTimezone();
  const self = useFamilySelf();
  // The same status as Home (GET /family/status): what the carer noted on the latest visit.
  const [status, setStatus] = useState<FamilyStatus | null>(null);

  function load() {
    familyApi<FamilyStatus>("/status").then(setStatus).catch(() => undefined);
    setError("");
    fetchFamilyCareFeed()
      // One card per visit with its latest state; backdated "scheduled" notices
      // (title or body date already past when posted) are dropped.
      // One card per visit (its report notice folds into it); a missed-visit
      // notice read on a later day no longer says "will call you today".
      .then((rows) => setItems(tidyMissedVisits(mergeVisitReports(collapseVisitChains(rows)))))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }

  useEffect(() => {
    load();
  }, []);

  const counts = items.reduce<Record<string, number>>((acc, i) => {
    acc[i.kind] = (acc[i.kind] ?? 0) + 1;
    if (i.photos?.length) acc.photos = (acc.photos ?? 0) + 1;
    return acc;
  }, {});
  const shown =
    filter === "all"
      ? items
      : filter === "photos"
        ? items.filter((i) => i.photos?.length)
        : items.filter((i) => i.kind === filter);

  return (
    <FamilyShell title="Updates" subtitle="Visit reports, KushLife checks, alerts and messages">
      <FamilyError message={error} onRetry={load} what="your updates" />

      <div className="ks-filterbar fh-filter-row" role="group" aria-label="Filter updates">
        {FILTERS.filter((f) => f.id === "all" || counts[f.id] || filter === f.id).map((f) => (
          <button
            key={f.id}
            type="button"
            className={`ks-filter${filter === f.id ? " is-on" : ""}`}
            aria-pressed={filter === f.id}
            onClick={() => setFilter(f.id)}
          >
            {f.label} ({f.id === "all" ? items.length : counts[f.id] ?? 0})
          </button>
        ))}
      </div>
      {shown.length === 0 ? (
        <div className="card home-safety-empty">
          <p>{items.length === 0 ? "No updates yet." : "Nothing in this filter."}</p>
          {items.length === 0 && (
            <p className="muted">After a visit or assessment, activity appears here.</p>
          )}
        </div>
      ) : (
        <ul className="home-safety-family-feed">
          {shown.map((item, idx) => {
            // Group by day (in the family's own time zone).
            const day = item.created_at ? familyDate(item.created_at, { tz }) : "";
            const prevDay = idx > 0 && shown[idx - 1].created_at ? familyDate(shown[idx - 1].created_at, { tz }) : "";
            const inner = (
              <>
                <div className="home-safety-family-feed-top">
                  <span className="home-safety-family-feed-kind">{kindLabel(item.kind)}</span>
                  {item.created_at ? (
                    <span className="muted">{familyClock(item.created_at, tz)}</span>
                  ) : null}
                </div>
                <strong>{forSelf(plainWords(tidyDates(item.title)), self.elderName, self.isSelf)}</strong>
                {item.body ? (
                  <FeedBody
                    text={forSelf(
                      plainWords(
                        tidyDates(
                          /urgent safety fixes/i.test(item.title)
                            ? rewordFindingLines(item.body)
                            : // The latest visit's card carries what the carer noted (same as Home).
                              item.kind === "visit" && isStatusVisit(item.created_at, status?.last_visit_at)
                              ? withNotedChanges(item.body, status?.changes)
                              : item.body,
                        ),
                      ),
                      self.elderName,
                      self.isSelf,
                    )}
                  />
                ) : null}
                {item.kind === "visit" && item.photos?.length ? (
                  <FamilyVisitPhotos
                    photos={item.photos}
                    visitedAt={item.created_at ?? ""}
                    total={item.photo_count}
                    compact
                  />
                ) : null}
              </>
            );
            return (
              <Fragment key={item.id}>
              {day && day !== prevDay ? (
                <li className="fh-feed-day">
                  <h2>{day}</h2>
                </li>
              ) : null}
              <li className="card home-safety-family-feed-item">
                {item.href ? (
                  <Link href={item.href} className="home-safety-family-feed-link">
                    {inner}
                  </Link>
                ) : (
                  inner
                )}
              </li>
              </Fragment>
            );
          })}
        </ul>
      )}
    </FamilyShell>
  );
}

function FeedBody({ text }: { text: string }) {
  const { intro, items, outro } = splitFeedBody(text);
  if (!items.length) return <p>{text}</p>;
  return (
    <>
      {intro ? <p>{intro}</p> : null}
      <ul className="fh-feed-list">
        {items.map((t, i) => (
          <li key={i}>{t}</li>
        ))}
      </ul>
      {outro ? <p>{outro}</p> : null}
    </>
  );
}
