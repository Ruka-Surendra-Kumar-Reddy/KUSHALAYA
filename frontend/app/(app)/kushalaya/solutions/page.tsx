"use client";

import Link from "next/link";
import { SolutionsAdminEditor } from "@/components/livewell/SolutionsAdminEditor";

export default function HomeSafetySolutionsAdminPage() {
  return (
    <>
      <h1 style={{ marginBottom: "0.25rem" }}>Home safety solution library</h1>
      <p className="muted" style={{ marginBottom: "1.25rem" }}>
        Map assessment findings to corrective actions, costs, and priorities. Generated automatically
        on the assessor{" "}
        <Link href="/kushalaya" target="_blank" rel="noopener noreferrer">
          review step
        </Link>
        . Also see{" "}
        <Link href="/kushalaya/rubric">checklist</Link> and{" "}
        <Link href="/kushalaya/catalog">product catalog</Link>.
      </p>
      <SolutionsAdminEditor />
    </>
  );
}
