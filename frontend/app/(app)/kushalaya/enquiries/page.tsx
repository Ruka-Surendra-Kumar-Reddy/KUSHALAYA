"use client";

import { useState } from "react";
import { Flash } from "@/components/Flash";
import { SalesBoard } from "@/components/ops/SalesBoard";

/**
 * Operations: the sales pipeline (New -> Assessment booked -> Assessment done ->
 * Follow-up 1 -> Follow-up 2 -> Won / Lost). Website enquiries land in New; Won
 * creates the client's plan in Pending approval. Route stays /kushalaya/enquiries so
 * menu links, the Dashboard and Settings -> Website keep working.
 */
export default function OperationsPage() {
  const [message, setMessage] = useState("");
  return (
    <SalesBoard
      onMessage={setMessage}
      flash={<Flash error="" message={message} onClear={() => setMessage("")} />}
    />
  );
}
