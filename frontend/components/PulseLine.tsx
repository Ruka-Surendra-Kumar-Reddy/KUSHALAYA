import "./pulse-line.css";

export type PulseItem = { label: string; note: string };

/**
 * "KushLife pulse" — a glowing heartbeat trace that sweeps across the panel,
 * with a headline number and a row of checks that light up in turn. Used on
 * the family and staff sign-in pages. Decorative: hidden from assistive tech.
 */
export function PulseLine({
  title,
  value,
  status,
  caption,
  items,
  points,
}: {
  title: string;
  value: string;
  status: string;
  caption: string;
  items: PulseItem[];
  /** Real scores, oldest first. When given, the line plots them instead of a heartbeat. */
  points?: { score: number; label: string }[];
}) {
  // Three heartbeats across a 600×120 strip; baseline at y=70.
  const beat = (x: number) =>
    `L${x + 60},70 Q${x + 70},60 ${x + 80},70 L${x + 92},70 L${x + 98},82 L${x + 108},12 L${x + 118},104 L${x + 126},70 L${x + 140},70 Q${x + 155},52 ${x + 170},70 L${x + 200},70`;
  const d = `M0,70 ${beat(0)} ${beat(200)} ${beat(400)}`;

  return (
    <div className="pl" aria-hidden="true">
      <div className="pl-head">
        <span className="pl-title">
          <i className="pl-live" />
          {title}
        </span>
        <span className="pl-value">
          <strong>{value}</strong>
          <em>{status}</em>
        </span>
      </div>
      <svg className="pl-svg" viewBox="0 0 600 120" preserveAspectRatio="none">
        <defs>
          <linearGradient id="pl-grad" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor="#8ab83e" />
            <stop offset="100%" stopColor="#7fd4ff" />
          </linearGradient>
        </defs>
        <path className="pl-grid" d="M0,30 H600 M0,70 H600 M0,110 H600" />
        {points && points.length > 1 ? (
          <DataTrace points={points} />
        ) : (
          <>
            <path className="pl-ghost" d={d} />
            <path className="pl-trace" d={d} />
          </>
        )}
      </svg>
      <p className="pl-caption">{caption}</p>
      <ul className="pl-pills">
        {items.map((it, i) => (
          <li key={it.label} style={{ ["--i" as string]: i }} title={it.note}>
            <span className="pl-pill-tick">✓</span>
            {it.label}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Real KushLife scores as a glowing line: baseline at 50, dots per visit, dates below. */
function DataTrace({ points }: { points: { score: number; label: string }[] }) {
  const w = 600;
  const top = 14;
  const bottom = 96;
  const min = Math.min(...points.map((p) => p.score), 45) - 3;
  const max = Math.max(...points.map((p) => p.score), 55) + 3;
  const x = (i: number) => 14 + (i / (points.length - 1)) * (w - 28);
  const y = (v: number) => top + (1 - (v - min) / (max - min)) * (bottom - top);
  const xy = points.map((p, i) => [x(i), y(p.score)] as const);
  let d = `M${xy[0][0]},${xy[0][1]}`;
  for (let i = 0; i < xy.length - 1; i++) {
    const p0 = xy[i - 1] ?? xy[i];
    const p1 = xy[i];
    const p2 = xy[i + 1];
    const p3 = xy[i + 2] ?? p2;
    d += ` C${p1[0] + (p2[0] - p0[0]) / 6},${p1[1] + (p2[1] - p0[1]) / 6} ${p2[0] - (p3[0] - p1[0]) / 6},${p2[1] - (p3[1] - p1[1]) / 6} ${p2[0]},${p2[1]}`;
  }
  const base = y(50);
  return (
    <>
      <line className="pl-base" x1={0} x2={w} y1={base} y2={base} />
      <path className="pl-ghost pl-ghost-data" d={d} pathLength={1000} />
      <path className="pl-trace pl-trace-data" d={d} pathLength={1000} />
      {xy.map(([cx, cy], i) => (
        <circle key={i} className={i === xy.length - 1 ? "pl-dot is-last" : "pl-dot"} cx={cx} cy={cy} r={i === xy.length - 1 ? 5.5 : 3.5} />
      ))}
      {xy.map(([cx], i) =>
        i === 0 || i === xy.length - 1 || i % 2 === 0 ? (
          <text key={`t${i}`} className="pl-date" x={cx} y={116} textAnchor={i === 0 ? "start" : i === xy.length - 1 ? "end" : "middle"}>
            {points[i].label}
          </text>
        ) : null,
      )}
    </>
  );
}
