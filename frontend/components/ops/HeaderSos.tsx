"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { RaiseEmergencyModal } from "@/components/ops/RaiseEmergency";

/**
 * Red SOS in the Ops top bar, on every page: anyone in Ops who can act picks the
 * client (search), says what happened, confirms, and the linked team and family
 * hear the siren. Opens the SOS page on the new emergency.
 */
export function HeaderSos() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  // The top bar is its own containing block (it would trap a fixed overlay in its
  // 67-px strip), so the form opens on the page body.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return (
    <>
      <button
        type="button"
        className="ko-sos-btn"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
      >
        SOS
      </button>
      {open && mounted
        ? createPortal(
            <RaiseEmergencyModal
              onClose={() => setOpen(false)}
              onRaised={(row) => {
                setOpen(false);
                router.push(`/kushalaya/alerts?incident=${row.id}`);
              }}
            />,
            document.body,
          )
        : null}
    </>
  );
}
