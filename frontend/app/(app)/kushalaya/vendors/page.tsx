"use client";

import { VendorsList } from "@/components/ops/VendorsList";
import { getStoredAuth } from "@/lib/api";
import { can } from "@/lib/roles";

/** Sales → Vendors: the tenant's vendor list; edit roles add and edit, viewers read. */
export default function VendorsPage() {
  return <VendorsList canEdit={can("edit", getStoredAuth()?.role || "")} />;
}
