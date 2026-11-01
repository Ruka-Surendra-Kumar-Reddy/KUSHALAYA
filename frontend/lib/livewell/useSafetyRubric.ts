"use client";

import { useEffect, useState } from "react";
import type { AssessmentCategory } from "./assessment";
import { getCachedRubric, getSafetyCategories } from "./rubric";
import { fetchAdminRubric } from "./rubricApi";

export function useSafetyRubric(): AssessmentCategory[] {
  const [categories, setCategories] = useState<AssessmentCategory[]>(() => {
    const cached = getCachedRubric();
    return cached.length ? cached : getSafetyCategories();
  });

  useEffect(() => {
    fetchAdminRubric()
      .then((next) => setCategories(next))
      .catch(() => setCategories(getSafetyCategories()));

    const onUpdate = () => setCategories(getSafetyCategories());
    window.addEventListener("home-safety-rubric-updated", onUpdate);
    return () => window.removeEventListener("home-safety-rubric-updated", onUpdate);
  }, []);

  return categories;
}
