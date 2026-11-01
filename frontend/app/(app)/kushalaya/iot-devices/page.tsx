"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/PageHeader";
import { IotDevicesAdminPanel } from "@/components/livewell/IotDevicesAdminPanel";
import "@/components/ops/clients.css";
import { isAdmin as isAdminUser } from "@/lib/roles";

export default function LiveWellIotDevicesPage() {
  const router = useRouter();
  const isAdmin = isAdminUser();
  useEffect(() => {
    // Admin-only: broker settings are global and hub passwords are secrets.
    if (!isAdmin) router.replace("/unauthorized");
  }, [isAdmin, router]);
  if (!isAdmin) return null;
  return (
    <>
      <IotDevicesAdminPanel header={<PageHeader title="Wearables" subtitle="SOS watches, sensors and their gateways" />} />
    </>
  );
}
