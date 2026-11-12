"use client";

import { PageHeader } from "@/components/PageHeader";
import { TeamTargets } from "@/components/ops/TeamTargets";
import "@/components/ops/dashboard.css";

/** Sales → Team targets: each person's KPIs against their monthly target. */
export default function TeamTargetsPage() {
  return (
    <>
      <PageHeader title="Team targets" subtitle="Each person's results this month against their target" />
      <TeamTargets />
    </>
  );
}
