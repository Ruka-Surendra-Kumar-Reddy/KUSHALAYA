"use client";

import { useEffect, useState } from "react";
import { formatCoordinates, previewGeocode } from "@/lib/geocoding";

type Props = {
  address: string;
  savedLatitude?: string;
  savedLongitude?: string;
};

export function AddressCoordinates({
  address,
  savedLatitude = "",
  savedLongitude = "",
}: Props) {
  const [latitude, setLatitude] = useState(savedLatitude);
  const [longitude, setLongitude] = useState(savedLongitude);
  const [status, setStatus] = useState<"idle" | "loading" | "missing">("idle");

  useEffect(() => {
    setLatitude(savedLatitude);
    setLongitude(savedLongitude);
  }, [savedLatitude, savedLongitude]);

  useEffect(() => {
    const query = address.trim();
    if (query.length < 3) {
      setLatitude("");
      setLongitude("");
      setStatus("idle");
      return;
    }

    setStatus("loading");
    const timer = window.setTimeout(async () => {
      const result = await previewGeocode(query);
      if (result) {
        setLatitude(String(result.latitude));
        setLongitude(String(result.longitude));
        setStatus("idle");
        return;
      }
      setLatitude(savedLatitude);
      setLongitude(savedLongitude);
      setStatus(savedLatitude && savedLongitude ? "idle" : "missing");
    }, 700);

    return () => window.clearTimeout(timer);
  }, [address, savedLatitude, savedLongitude]);

  const display = formatCoordinates(latitude, longitude);

  return (
    <div style={{ gridColumn: "1 / -1" }}>
      <label>Coordinates (from address)</label>
      <p
        className="muted"
        style={{
          margin: "0.35rem 0 0",
          padding: "0.65rem 0.75rem",
          border: "1px solid var(--border)",
          borderRadius: "6px",
          background: "var(--surface-muted, #f8fafc)",
        }}
        aria-live="polite"
      >
        {status === "loading" && "Calculating coordinates…"}
        {status !== "loading" && display && display}
        {status !== "loading" && !display && status === "missing" && (
          <>Could not geocode this address yet. Coordinates will be saved if geocoding succeeds on submit.</>
        )}
        {status !== "loading" && !display && status === "idle" && (
          <>Enter a full street address to calculate map coordinates.</>
        )}
      </p>
    </div>
  );
}
