"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  clientDisplayName,
  completionPercent,
  type HomeSafetyAssessment,
} from "@/lib/livewell/assessment";
import { EMPTY_RESIDENT_PROFILE } from "@/lib/livewell/resident-profile";
import { useSafetyRubric } from "@/lib/livewell/useSafetyRubric";
import { listAssessments } from "@/lib/livewell/storage";
import { deleteAssessmentEverywhere, listAssessmentsMerged } from "@/lib/livewell/assessmentSync";
import { getStoredAuth } from "@/lib/api";
import { canWrite } from "@/lib/auth";
import { MoreMenu } from "@/components/ops/MoreMenu";
import { isAdmin as isAdminUser } from "@/lib/roles";
import { categoriesForAssessment } from "@/lib/livewell/conditional";

function statusLabel(a: HomeSafetyAssessment): { label: string; className: string } {
  if (a.status === "draft") {
    return {
      label: "Draft",
      className: "customers-flow-badge customers-flow-badge--warn",
    };
  }
  return {
    label: "Saved",
    className: "customers-flow-badge customers-flow-badge--ok",
  };
}

export function AssessmentsListPanel({
  assessBase,
  showStartButton = true,
  showQuestionsLink = true,
}: {
  assessBase: string;
  showStartButton?: boolean;
  /** false when the page already links to the questions (ops Assessments page). */
  showQuestionsLink?: boolean;
}) {
  const router = useRouter();
  const categories = useSafetyRubric();
  // Read the stored sign-in after mount: the server render has no localStorage, so
  // reading it during render made the first client render differ (hydration error).
  const [writable, setWritable] = useState(false);
  const [sysAdmin, setSysAdmin] = useState(false);
  useEffect(() => {
    setWritable(canWrite(getStoredAuth()?.role || ""));
    setSysAdmin(isAdminUser());
  }, []);
  const [items, setItems] = useState<HomeSafetyAssessment[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [listTab, setListTab] = useState<"drafts" | "saved">("drafts");
  const [query, setQuery] = useState("");
  const [showEmpty, setShowEmpty] = useState(false);
  const [limit, setLimit] = useState(PAGE_SIZE);
  useEffect(() => setLimit(PAGE_SIZE), [listTab, query]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await listAssessmentsMerged();
      setItems(list);
      if (
        // Open on Saved when the only drafts are empty ones (hidden by default).
        !list.some((a) => a.status === "draft" && (clientDisplayName(a) || a.clientPhone || a.clientAddress)) &&
        list.some((a) => a.status === "completed")
      ) {
        setListTab("saved");
      }
    } catch {
      setItems(listAssessments());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const drafts = useMemo(
    () => items.filter((a) => a.status === "draft"),
    [items],
  );
  const saved = useMemo(
    () => items.filter((a) => a.status === "completed"),
    [items],
  );

  const pctOf = useCallback(
    (a: HomeSafetyAssessment) =>
      completionPercent(categoriesForAssessment(categories, a), a.ratings, a.residentProfile ?? EMPTY_RESIDENT_PROFILE),
    [categories],
  );
  // Drafts opened and left with nothing in them (no name, no contact, 0%) are hidden by default.
  const isEmptyDraft = useCallback(
    (a: HomeSafetyAssessment) =>
      a.status === "draft" && !clientDisplayName(a) && !a.clientPhone && !a.clientAddress && pctOf(a) === 0,
    [pctOf],
  );
  const emptyDrafts = useMemo(() => drafts.filter(isEmptyDraft).length, [drafts, isEmptyDraft]);

  const q = query.trim().toLowerCase();
  const source = listTab === "drafts" ? drafts : saved;
  const visible = useMemo(
    () =>
      source.filter((a) =>
        (showEmpty || !isEmptyDraft(a)) &&
        `${clientDisplayName(a)} ${a.clientPhone || ""} ${a.clientAddress || ""} ${a.id}`
          .toLowerCase()
          .includes(q),
      ),
    [q, source, showEmpty, isEmptyDraft],
  );

  function handleStartAssessment() {
    // New assessments start from the Assessments page picker (3-step checklist).
    router.push("/kushalaya/assessments");
  }

  async function handleDelete(a: HomeSafetyAssessment) {
    const name = clientDisplayName(a) || a.id;
    if (!window.confirm(`Delete assessment for ${name}?`)) return;
    setBusy(true);
    try {
      await deleteAssessmentEverywhere(a.id);
      setItems((prev) => prev.filter((row) => row.id !== a.id));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <div className="customers-tabs">
        <button
          type="button"
          className={listTab === "drafts" ? "active" : undefined}
          onClick={() => setListTab("drafts")}
        >
          Drafts ({drafts.length - (showEmpty ? 0 : emptyDrafts)})
        </button>
        <button
          type="button"
          className={listTab === "saved" ? "active" : undefined}
          onClick={() => setListTab("saved")}
        >
          Saved ({saved.length})
        </button>
      </div>

      <div className="customers-hub-list-head">
        <input aria-label={listTab === "drafts" ? "Search drafts" : "Search saved"}
          className="customers-hub-search"
          type="search"
          placeholder={listTab === "drafts" ? "Search drafts" : "Search saved"}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {showStartButton || (sysAdmin && showQuestionsLink) ? (
          <div className="customers-hub-list-actions">
            {sysAdmin && showQuestionsLink ? <Link href="/kushalaya/rubric">Questions</Link> : null}
            {showStartButton ? (
              <button type="button" onClick={handleStartAssessment} disabled={busy}>
                + New
              </button>
            ) : null}
          </div>
        ) : null}
      </div>

      {listTab === "drafts" && emptyDrafts ? (
        <p className="al-empty-toggle">
          <button type="button" className="secondary" aria-pressed={showEmpty} onClick={() => setShowEmpty((v) => !v)}>
            {showEmpty ? "Hide empty drafts" : `Show empty drafts (${emptyDrafts})`}
          </button>
        </p>
      ) : null}

      {loading ? (
        <p className="muted">Loading…</p>
      ) : visible.length === 0 ? (
        <p className="muted">
          {q
            ? "No matching assessments."
            : listTab === "drafts"
              ? "No drafts."
              : "No saved assessments."}
        </p>
      ) : (
        <div className="customers-person-list">
          {visible.slice(0, limit).map((a) => {
            const badge = statusLabel(a);
            const name = clientDisplayName(a) || `${a.status === "draft" ? "Draft" : "Assessment"} · ${shortDate(a.updatedAt || a.createdAt)}`;
            const pct = pctOf(a);
            return (
              <div key={a.id} className="customers-person-row">
                <div>
                  <div className="customers-person-name">{name}</div>
                  <div className="customers-person-meta">
                    <span>{a.clientPhone || a.clientAddress || "No mobile"}</span>
                    {a.status === "draft" ? (
                      <span className="customers-flow-badge customers-flow-badge--warn">
                        Draft · {pct}%
                      </span>
                    ) : (
                      <span className={badge.className}>{badge.label}</span>
                    )}
                  </div>
                </div>
                <div className="customers-row-actions assess-row-actions">
                  <Link href={`${assessBase}/${a.id}`}>
                    {a.status === "draft" ? "Continue" : "Open"}
                  </Link>
                  {a.elderId != null ? (
                    <Link href={`/kushalaya/customers/${a.elderId}`}>Visits</Link>
                  ) : null}
                  {writable ? (
                    <MoreMenu icon label={`More for ${name}`} align="right">
                      <button
                        type="button"
                        className="ks-more-item is-danger"
                        role="menuitem"
                        disabled={busy}
                        onClick={() => void handleDelete(a)}
                      >
                        Delete…
                      </button>
                    </MoreMenu>
                  ) : null}
                </div>
              </div>
            );
          })}
          {visible.length > limit ? (
            <button type="button" className="secondary assess-list-more" onClick={() => setLimit((n) => n + PAGE_SIZE)}>
              Show {Math.min(PAGE_SIZE, visible.length - limit)} more ({visible.length - limit} left)
            </button>
          ) : null}
        </div>
      )}
    </div>
  );
}

const PAGE_SIZE = 20;

function shortDate(iso?: string | null): string {
  if (!iso) return "no date";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "no date";
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", timeZone: "Asia/Kolkata" });
}
