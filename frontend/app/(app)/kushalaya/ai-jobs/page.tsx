"use client";

import Link from "next/link";
import { AIJobsAdminEditor } from "@/components/livewell/AIJobsAdminEditor";

export default function HomeSafetyAIJobsAdminPage() {
  return (
    <>
      <h1 style={{ marginBottom: "0.25rem" }}>AI visualization jobs</h1>
      <p className="muted" style={{ marginBottom: "1.25rem" }}>
        Review tier concept jobs by phase. Select a row to open the Assessment → Recommendations →
        Analysis → Plan → Render → Review board. Configure tiers and prompts via{" "}
        <Link href="/kushalaya/master-data">master data import</Link> (sheets 12–18). Default{" "}
        <code>local_stub</code> builds reviewable concepts without JarvisLabs.
      </p>
      <AIJobsAdminEditor />
    </>
  );
}
