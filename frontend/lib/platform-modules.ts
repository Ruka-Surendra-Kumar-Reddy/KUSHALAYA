import { api } from "./api";

export type PlatformModule = {
  id: string;
  label: string;
  maturity: "shipped" | "partial" | "planned";
  description: string;
  api_paths: string[];
};

export async function fetchPlatformModules(): Promise<PlatformModule[]> {
  const res = await api<{ modules: PlatformModule[] }>("/api/v1/platform/modules");
  return res.modules;
}
