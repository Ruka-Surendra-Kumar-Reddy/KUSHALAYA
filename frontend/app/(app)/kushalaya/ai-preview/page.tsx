"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { AiRoomPreview } from "@/components/ops/AiRoomPreview";
import { parseProductCodes } from "@/lib/aiPreview";

/**
 * /kushalaya/ai-preview?assessment=<id>&photo=<documentId>&products=BTH-002,BTH-009
 * Also: ?elder=<clientId> (client page entry) and ?job=<AIJ-…> (reopen a preview).
 */
function PreviewFromQuery() {
  const q = useSearchParams();
  const num = (k: string) => {
    const n = Number(q.get(k));
    return Number.isFinite(n) && n > 0 ? n : null;
  };
  return (
    <AiRoomPreview
      assessment={q.get("assessment")}
      elder={num("elder")}
      photo={num("photo")}
      products={parseProductCodes(q.get("products"))}
      job={q.get("job")}
    />
  );
}

export default function AiPreviewPage() {
  return (
    <Suspense fallback={<p className="muted">Loading…</p>}>
      <PreviewFromQuery />
    </Suspense>
  );
}
