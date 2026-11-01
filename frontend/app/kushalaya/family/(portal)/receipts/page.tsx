"use client";

import { FamilyShell } from "@/components/livewell/family/FamilyShell";
import { WalletReceipts } from "@/components/livewell/family/WalletReceipts";

/** Receipts now live in Wallet → History; this page shows the same list until /receipts redirects. */
export default function FamilyReceiptsPage() {
  return (
    <FamilyShell title="Receipts" subtitle="Every top-up and payment, with a printable receipt">
      <WalletReceipts />
    </FamilyShell>
  );
}
