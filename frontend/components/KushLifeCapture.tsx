"use client";

import { useState } from "react";
import { KL_CHECKS, KL_CHIPS, KL_RED_CHIPS, type CheckKey, type KushLifeCapture } from "@/lib/kushlife";
import "./kushlife.css";

/**
 * The KushLife check on a visit: each of the four starts unanswered; "Same as usual" is one tap,
 * "Changed" opens quick chips. Sleep and appetite are asked every visit. Vitals are optional.
 */
export function KushLifeCaptureForm({ value, onChange }: { value: KushLifeCapture; onChange: (v: KushLifeCapture) => void }) {
  const [vitalsOpen, setVitalsOpen] = useState(false);

  function setCheck(key: CheckKey, patch: Partial<KushLifeCapture["checks"][CheckKey]>) {
    onChange({ ...value, checks: { ...value.checks, [key]: { ...value.checks[key], ...patch } } });
  }

  function toggleChip(key: CheckKey, chip: string) {
    const cur = value.checks[key].chips;
    setCheck(key, { chips: cur.includes(chip) ? cur.filter((c) => c !== chip) : [...cur, chip] });
  }

  const allUsual = () =>
    onChange({
      ...value,
      checks: {
        safe: { status: "ok", chips: [], note: "" },
        steady: { status: "ok", chips: [], note: "" },
        settled: { status: "ok", chips: [], note: "" },
        connected: { status: "ok", chips: [], note: "" },
      },
    });

  const red = KL_CHECKS.some((k) => value.checks[k.key].chips.some((c) => KL_RED_CHIPS.has(c)));

  return (
    <div className="kl-capture">
      <div className="kl-capture-head">
        <span>
          <strong>KushLife check</strong>
          <small>Compare with how they usually are.</small>
        </span>
        <button type="button" className="kl-all" onClick={allUsual}>
          All same as usual
        </button>
      </div>

      {KL_CHECKS.map((k) => {
        const c = value.checks[k.key];
        return (
          <div key={k.key} className={`kl-check${c.status === "concern" ? " is-changed" : c.status === "ok" ? " is-usual" : ""}`}>
            <div className="kl-check-row">
              <span className="kl-check-name">
                <strong>{k.label}</strong>
                <small>{k.hint}</small>
              </span>
              <span className="kl-seg" role="radiogroup" aria-label={k.label}>
                <button
                  type="button"
                  role="radio"
                  aria-checked={c.status === "ok"}
                  className={c.status === "ok" ? "is-on is-ok" : ""}
                  onClick={() => setCheck(k.key, { status: "ok", chips: [] })}
                >
                  Same as usual
                </button>
                <button
                  type="button"
                  role="radio"
                  aria-checked={c.status === "concern"}
                  className={c.status === "concern" ? "is-on is-changed" : ""}
                  onClick={() => setCheck(k.key, { status: "concern" })}
                >
                  Changed
                </button>
              </span>
            </div>
            {c.status === "concern" ? (
              <div className="kl-chips">
                {KL_CHIPS[k.key].map((chip) => (
                  <button
                    key={chip.key}
                    type="button"
                    aria-pressed={c.chips.includes(chip.key)}
                    className={`kl-chip${c.chips.includes(chip.key) ? " is-on" : ""}${KL_RED_CHIPS.has(chip.key) ? " is-red" : ""}`}
                    onClick={() => toggleChip(k.key, chip.key)}
                  >
                    {chip.label}
                  </button>
                ))}
                <input
                  className="kl-chip-note"
                  value={c.note}
                  maxLength={300}
                  placeholder="What changed? (optional)"
                  onChange={(e) => setCheck(k.key, { note: e.target.value })}
                />
              </div>
            ) : null}
          </div>
        );
      })}

      <div className="kl-pair">
        <span className="kl-pair-label">Slept</span>
        <span className="kl-seg" role="radiogroup" aria-label="Sleep">
          {(["well", "poorly", "unsure"] as const).map((v) => (
            <button key={v} type="button" role="radio" aria-checked={value.sleep === v}
              className={value.sleep === v ? "is-on" : ""} onClick={() => onChange({ ...value, sleep: v })}>
              {v === "well" ? "Well" : v === "poorly" ? "Poorly" : "Not sure"}
            </button>
          ))}
        </span>
        <span className="kl-pair-label">Ate</span>
        <span className="kl-seg" role="radiogroup" aria-label="Appetite">
          {(["usual", "less", "more"] as const).map((v) => (
            <button key={v} type="button" role="radio" aria-checked={value.appetite === v}
              className={value.appetite === v ? "is-on" : ""} onClick={() => onChange({ ...value, appetite: v })}>
              {v === "usual" ? "As usual" : v === "less" ? "Less" : "More"}
            </button>
          ))}
        </span>
      </div>

      <button type="button" className="kl-vitals-toggle" aria-expanded={vitalsOpen} onClick={() => setVitalsOpen((o) => !o)}>
        {vitalsOpen ? "− Hide readings" : "+ Add readings (BP, oxygen, pulse, sugar)"}
      </button>
      {vitalsOpen ? (
        <div className="kl-vitals">
          {([
            ["bp_sys", "BP top", "120"],
            ["bp_dia", "BP bottom", "80"],
            ["spo2", "Oxygen %", "97"],
            ["pulse", "Pulse /min", "72"],
            ["sugar", "Sugar mg/dL", "110"],
          ] as const).map(([key, label, ph]) => (
            <label key={key}>
              {label}
              <input inputMode="numeric" value={value.vitals[key] ?? ""} placeholder={ph}
                onChange={(e) => onChange({ ...value, vitals: { ...value.vitals, [key]: e.target.value.replace(/[^0-9]/g, "") } })} />
            </label>
          ))}
        </div>
      ) : null}

      {red ? (
        <p className="kl-red-note" role="alert">
          Marked <strong>red</strong>: we&apos;ll tell the family their care manager will call within 2 hours.
        </p>
      ) : null}
    </div>
  );
}
