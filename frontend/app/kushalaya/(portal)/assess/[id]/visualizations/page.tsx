"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AIVisualizationsPanel } from "@/components/livewell/AIVisualizationsPanel";
import { HomeSafetyShell } from "@/components/livewell/HomeSafetyShell";
import {
  clientDisplayName,
  type HomeSafetyAssessment,
} from "@/lib/livewell/assessment";
import { loadAssessmentMerged } from "@/lib/livewell/assessmentSync";
import { DEFAULT_SAFETY_CATALOG } from "@/lib/livewell/catalog-defaults";
import { fetchAdminCatalog, getCachedCatalog } from "@/lib/livewell/catalogApi";
import type { SafetyCatalog } from "@/lib/livewell/catalog-types";
import { hydratePhotoPreviews } from "@/lib/livewell/photoPersist";
import { DEFAULT_SOLUTION_LIBRARY } from "@/lib/livewell/solution-defaults";
import { fetchAdminSolutions, getCachedSolutions } from "@/lib/livewell/solutionApi";
import type { SolutionLibrary } from "@/lib/livewell/solution-types";
import { getAssessment } from "@/lib/livewell/storage";
import { useSafetyRubric } from "@/lib/livewell/useSafetyRubric";
import { ACTIVE_TIERS } from "@/lib/livewell/aiVisualizations";

export default function AssessmentVisualizationsPage() {
  const params = useParams();
  const id = String(params.id);
  const categories = useSafetyRubric();
  const [draft, setDraft] = useState<HomeSafetyAssessment | null>(null);
  const [missing, setMissing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [solutions, setSolutions] = useState<SolutionLibrary>(
    () => getCachedSolutions() ?? DEFAULT_SOLUTION_LIBRARY,
  );
  const [catalog, setCatalog] = useState<SafetyCatalog>(
    () => getCachedCatalog() ?? DEFAULT_SAFETY_CATALOG,
  );
  const [selectedPackageTiers, setSelectedPackageTiers] = useState<string[]>([
    ...ACTIVE_TIERS,
  ]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        let found = getAssessment(id);
        const merged = await loadAssessmentMerged(id);
        if (merged) found = merged;
        if (cancelled) return;
        if (!found) {
          setMissing(true);
          setDraft(null);
        } else {
          setMissing(false);
          setDraft(await hydratePhotoPreviews(found));
        }
      } catch {
        if (!cancelled) {
          setMissing(true);
          setDraft(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    void fetchAdminSolutions()
      .then(setSolutions)
      .catch(() => undefined);
    void fetchAdminCatalog()
      .then(setCatalog)
      .catch(() => undefined);
  }, []);

  if (loading) {
    return (
      <main className="home-safety-app home-safety-loading">
        <p>Loading…</p>
      </main>
    );
  }

  if (missing || !draft) {
    return (
      <main className="home-safety-app home-safety-loading">
        <div className="card home-safety-empty">
          <h1 style={{ marginTop: 0 }}>Assessment not found</h1>
          <p>
            <Link href="/kushalaya" className="home-safety-cta">
              Back to assessments
            </Link>
          </p>
        </div>
      </main>
    );
  }

  const client = clientDisplayName(draft);

  return (
    <HomeSafetyShell
      title="AI room visualizations"
      subtitle={`${client} · ${draft.id}`}
      backHref={`/kushalaya/assess/${draft.id}`}
      showNav={false}
    >
      <p className="muted home-safety-section-hint">
        Analyze the room photo, pick solutions and catalog products, then generate after concepts.
        Return to the assessment review step to build the family report and quotes.
      </p>
      <p className="home-safety-viz-page-nav">
        <Link href={`/kushalaya/assess/${draft.id}`} className="secondary">
          ← Back to assessment
        </Link>
      </p>
      <AIVisualizationsPanel
        assessment={draft}
        categories={categories}
        library={solutions}
        catalog={catalog}
        selectedPackageTiers={selectedPackageTiers}
        onPackageTiersChange={setSelectedPackageTiers}
        onAssessmentChange={setDraft}
      />
    </HomeSafetyShell>
  );
}
