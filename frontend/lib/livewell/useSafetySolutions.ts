"use client";

import { useEffect, useState } from "react";
import type { SolutionLibrary } from "./solution-types";
import { DEFAULT_SOLUTION_LIBRARY } from "./solution-defaults";
import { getLocalSolutionLibrary } from "./solutions";

export function useSafetySolutions(): SolutionLibrary {
  const [library, setLibrary] = useState<SolutionLibrary>(DEFAULT_SOLUTION_LIBRARY);

  useEffect(() => {
    setLibrary(getLocalSolutionLibrary());
    const onUpdate = () => setLibrary(getLocalSolutionLibrary());
    window.addEventListener("home-safety-solutions-updated", onUpdate);
    return () => window.removeEventListener("home-safety-solutions-updated", onUpdate);
  }, []);

  return library;
}
