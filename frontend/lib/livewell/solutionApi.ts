import { api } from "@/lib/api";
import type { SolutionLibrary } from "./solution-types";
import { getLocalSolutionLibrary, saveLocalSolutionLibrary, trimSolutionLibraryForSave } from "./solutions";

export async function fetchAdminSolutions(): Promise<SolutionLibrary> {
  const library = await api<SolutionLibrary>("/api/v1/home-safety/solutions");
  saveLocalSolutionLibrary(library);
  return library;
}

export async function saveAdminSolutions(library: SolutionLibrary): Promise<SolutionLibrary> {
  const payload = trimSolutionLibraryForSave(library);
  const saved = await api<SolutionLibrary>("/api/v1/home-safety/solutions", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  saveLocalSolutionLibrary(saved);
  return saved;
}

export function getCachedSolutions(): SolutionLibrary {
  return getLocalSolutionLibrary();
}
