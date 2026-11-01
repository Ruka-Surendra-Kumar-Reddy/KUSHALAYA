"use client";

/** Hazards our staff confirmed from room photos — confirmed only, plain words. */
import { useEffect, useState } from "react";
import { familyRoomHazards, type FamilyRoomHazard } from "@/lib/livewell/aiHazardCheck";

export function FamilyRoomHazards() {
  const [items, setItems] = useState<FamilyRoomHazard[]>([]);
  useEffect(() => {
    familyRoomHazards()
      .then((r) => setItems(r.hazards))
      .catch(() => setItems([]));
  }, []);
  if (!items.length) return null;
  return (
    <section className="card home-safety-section">
      <h2>Room by room: what our team confirmed</h2>
      <ul className="home-safety-family-domain-list">
        {items.map((h, i) => (
          <li key={`${h.room_label}-${h.label}-${i}`}>
            <div className="home-safety-family-domain-row">
              <span>
                <strong>{h.room_label}:</strong> {h.label}
              </span>
              <strong>{h.severity_label}</strong>
            </div>
            <p className="muted" style={{ margin: "0.2rem 0 0", fontSize: "0.85rem" }}>
              What we suggest: {h.suggestion}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}
