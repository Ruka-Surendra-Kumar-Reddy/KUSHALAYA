"use client";

import type { ThemeOption } from "@/lib/branding";
import { useBranding } from "./BrandingProvider";

const SWATCHES: Record<string, { bar: string; primary: string }> = {
  classic: { bar: "linear-gradient(90deg,#1a2b3c,#1e5a8a)", primary: "#1e5a8a" },
  ocean: { bar: "linear-gradient(90deg,#0a3d3d,#0d6e6e)", primary: "#0d6e6e" },
  warm: { bar: "linear-gradient(90deg,#3d2914,#b45309)", primary: "#b45309" },
};

export function ThemePicker({
  themes,
  selected,
  onSelect,
}: {
  themes: ThemeOption[];
  selected: string;
  onSelect: (id: string) => void;
}) {
  const branding = useBranding();

  return (
    <div className="grid-2">
      {themes.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`theme-preview ${selected === t.id ? "selected" : ""}`}
          onClick={() => onSelect(t.id)}
          style={{ textAlign: "left", background: "var(--card)" }}
        >
          <div
            className="theme-swatch"
            style={{ background: SWATCHES[t.id]?.bar || SWATCHES.classic.bar }}
          />
          <strong>{t.name}</strong>
          <p className="muted" style={{ margin: "0.25rem 0 0", fontSize: "0.85rem" }}>
            {t.description}
          </p>
          {branding.theme === t.id && (
            <span className="muted" style={{ fontSize: "0.75rem" }}>
              Current
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
