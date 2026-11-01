"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/PageHeader";
import { RubricAdminEditor } from "@/components/livewell/RubricAdminEditor";
import { isAdmin as isAdminUser } from "@/lib/roles";

export default function HomeSafetyRubricAdminPage() {
  const router = useRouter();
  const canEdit = isAdminUser();
  useEffect(() => {
    if (!canEdit) router.replace("/unauthorized");
  }, [canEdit, router]);
  if (!canEdit) return null;
  return (
    <RubricAdminEditor
      header={<PageHeader title="Assessment questions" subtitle="What caregivers ask on every home check" />}
    />
  );
}
