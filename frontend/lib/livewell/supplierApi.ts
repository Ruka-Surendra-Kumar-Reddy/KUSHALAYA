import { api } from "@/lib/api";
import type { SupplierDirectory } from "./supplier-types";
import { getLocalSupplierDirectory, saveLocalSupplierDirectory } from "./suppliers";

export async function fetchAdminSuppliers(): Promise<SupplierDirectory> {
  const directory = await api<SupplierDirectory>("/api/v1/home-safety/suppliers");
  saveLocalSupplierDirectory(directory);
  return directory;
}

export async function saveAdminSuppliers(directory: SupplierDirectory): Promise<SupplierDirectory> {
  const saved = await api<SupplierDirectory>("/api/v1/home-safety/suppliers", {
    method: "PUT",
    body: JSON.stringify(directory),
  });
  saveLocalSupplierDirectory(saved);
  return saved;
}

export function getCachedSuppliers(): SupplierDirectory {
  return getLocalSupplierDirectory();
}
