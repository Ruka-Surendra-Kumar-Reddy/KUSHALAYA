"use client";

import { FamilyRedirect } from "@/components/livewell/family/FamilyRedirect";

/** Visit reports are in Updates now (Phase 2E). Detail pages stay at /visits/<id>. */
export default function FamilyVisitsPage() {
  return <FamilyRedirect to="/kushalaya/family/updates" />;
}
