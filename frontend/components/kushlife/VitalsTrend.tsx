"use client";

import { useState } from "react";
import type { VitalKey, VitalsSeries } from "@/lib/kushlife-quality";
import "./vitals-trend.css";

/** Small multiples (one axis each): blood pressure (top + bottom), oxygen, pulse. Dashed line = their normal. */
const CHARTS: { title: string; unit: string; range: [number, number]; series: { key: VitalKey; label: string; cls: string }[] }[] = [
  { title: "Blood pressure", unit: "mmHg", range: [60, 200], series: [{ key: "bp_sys", label: "Top", cls: "is-a" }, { key: "bp_dia", label: "Bottom", cls: "is-b" }] },
  { title: "Oxygen", unit: "%", range: [85, 100], series: [{ key: "spo2", label: "Oxygen", cls: "is-a" }] },
  { title: "Pulse", unit: "per min", range: [40, 130], series: [{ key: "pulse", label: "Pulse", cls: "is-a" }] },
];

const W = 320;
const H = 120;
const PAD = { l: 34, r: 40, t: 10, b: 20 };

function day(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", timeZone: "Asia/Kolkata" });
}

function Chart({ data, chart }: { data: VitalsSeries; chart: (typeof CHARTS)[number] }) {
  const [hover, setHover] = useState<number | null>(null);
  const pts = data.points.filter((p) => chart.series.some((s) => p[s.key] != null));
  if (!pts.length) return null;
  const t0 = new Date(pts[0].date).getTime();
  const t1 = new Date(pts[pts.length - 1].date).getTime();
  const vals: number[] = [];
  for (const p of pts) for (const s of chart.series) if (p[s.key] != null) vals.push(p[s.key] as number);
  for (const s of chart.series) if (data.baseline[s.key] != null) vals.push(data.baseline[s.key] as number);
  // Fixed ranges so a small wobble doesn't look like a big swing; widen only for a reading outside them.
  const lo = Math.floor(Math.min(chart.range[0], ...vals));
  const hi = Math.ceil(Math.max(chart.range[1], ...vals));
  const x = (iso: string) =>
    pts.length === 1 || t1 === t0 ? (PAD.l + W - PAD.r) / 2 : PAD.l + ((new Date(iso).getTime() - t0) / (t1 - t0)) * (W - PAD.l - PAD.r);
  const y = (v: number) => PAD.t + (1 - (v - lo) / (hi - lo)) * (H - PAD.t - PAD.b);
  const hp = hover != null ? pts[hover] : null;

  return (
    <figure className="vt-chart">
      <figcaption>
        <strong>{chart.title}</strong> <small>{chart.unit}</small>
        {chart.series.length > 1 ? (
          <span className="vt-legend">
            {chart.series.map((s) => (
              <span key={s.key}><i className={`vt-swatch ${s.cls}`} />{s.label}</span>
            ))}
            <span><i className="vt-swatch is-normal" />Their usual</span>
          </span>
        ) : data.baseline[chart.series[0].key] != null ? (
          <span className="vt-legend"><span><i className="vt-swatch is-normal" />Their usual</span></span>
        ) : null}
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${chart.title} over the last ${data.days} days`}
        onMouseLeave={() => setHover(null)}>
        {[lo, hi].map((v) => (
          <g key={v}>
            <line className="vt-grid" x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} />
            <text className="vt-axis" x={PAD.l - 4} y={y(v) + 3} textAnchor="end">{v}</text>
          </g>
        ))}
        <text className="vt-axis" x={PAD.l} y={H - 4}>{day(pts[0].date)}</text>
        {pts.length > 1 ? <text className="vt-axis" x={W - PAD.r} y={H - 4} textAnchor="end">{day(pts[pts.length - 1].date)}</text> : null}
        {chart.series.map((s) => {
          const b = data.baseline[s.key];
          return b != null ? <line key={`n${s.key}`} className="vt-normal" x1={PAD.l} x2={W - PAD.r} y1={y(b)} y2={y(b)} /> : null;
        })}
        {chart.series.map((s) => {
          const sp = pts.filter((p) => p[s.key] != null);
          const d = sp.map((p, i) => `${i ? "L" : "M"}${x(p.date).toFixed(1)},${y(p[s.key] as number).toFixed(1)}`).join(" ");
          const last = sp[sp.length - 1];
          return (
            <g key={s.key} className={`vt-series ${s.cls}`}>
              <path d={d} />
              {sp.map((p) => <circle key={p.date} cx={x(p.date)} cy={y(p[s.key] as number)} r={3} />)}
              {last ? (
                <text className="vt-label" x={x(last.date) + 6} y={y(last[s.key] as number) + 3}>{last[s.key]}</text>
              ) : null}
            </g>
          );
        })}
        {hp ? <line className="vt-cross" x1={x(hp.date)} x2={x(hp.date)} y1={PAD.t} y2={H - PAD.b} /> : null}
        {pts.map((p, i) => {
          const left = i === 0 ? PAD.l : (x(pts[i - 1].date) + x(p.date)) / 2;
          const right = i === pts.length - 1 ? W - PAD.r : (x(p.date) + x(pts[i + 1].date)) / 2;
          return (
            <rect key={p.date} className="vt-hit" x={left} y={0} width={Math.max(1, right - left)} height={H}
              onMouseEnter={() => setHover(i)} onTouchStart={() => setHover(i)} />
          );
        })}
      </svg>
      {hp ? (
        <p className="vt-tip" aria-live="polite">
          {day(hp.date)}: {chart.series.map((s) => (hp[s.key] != null ? `${s.label} ${hp[s.key]}` : null)).filter(Boolean).join(" · ")}
        </p>
      ) : null}
    </figure>
  );
}

export function VitalsTrend({ data, title = "Readings — last 3 months" }: { data: VitalsSeries | null; title?: string }) {
  if (!data) return null;
  if (!data.points.length) {
    return (
      <div className="vt">
        <h3>{title}</h3>
        <p className="vt-muted">No readings recorded on visits in the last 3 months.</p>
      </div>
    );
  }
  return (
    <div className="vt">
      <h3>{title}</h3>
      <p className="vt-muted">Each dot is a visit. Dashed line = their usual reading. Care observations, not a diagnosis.</p>
      <div className="vt-grid-wrap">
        {CHARTS.map((c) => <Chart key={c.title} data={data} chart={c} />)}
      </div>
      <details className="vt-table">
        <summary>Show as a table</summary>
        <table>
          <thead><tr><th>Date</th><th>BP</th><th>Oxygen</th><th>Pulse</th></tr></thead>
          <tbody>
            {[...data.points].reverse().map((p) => (
              <tr key={p.date}>
                <td>{day(p.date)}</td>
                <td>{p.bp_sys && p.bp_dia ? `${p.bp_sys}/${p.bp_dia}` : "—"}</td>
                <td>{p.spo2 != null ? `${p.spo2}%` : "—"}</td>
                <td>{p.pulse ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}
