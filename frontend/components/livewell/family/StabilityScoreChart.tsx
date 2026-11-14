import type { StabilityScorePoint } from "@/lib/livewell/familyApi";

/**
 * The KushLife trend: the per-visit wellbeing score (personal normal = 50)
 * drawn as a heartbeat-style line. Data is the stability score history the
 * backend already records on every completed visit.
 */
export function StabilityScoreChart({
  history,
  delta,
}: {
  history: StabilityScorePoint[];
  delta?: number | null;
}) {
  if (!history.length) return null;

  // API returns newest first; the chart reads left (oldest) to right (latest).
  const points = [...history].sort(
    (a, b) => new Date(a.visited_at ?? 0).getTime() - new Date(b.visited_at ?? 0).getTime(),
  );
  const scores = points.map((p) => p.score);
  const latest = scores[scores.length - 1];

  const w = 640;
  const h = 180;
  const padX = 16;
  const padTop = 18;
  const padBottom = 30;
  const min = Math.max(0, Math.min(...scores, 45) - 5);
  const max = Math.min(100, Math.max(...scores, 55) + 5);
  const x = (i: number) =>
    points.length === 1 ? w / 2 : padX + (i / (points.length - 1)) * (w - padX * 2);
  const y = (v: number) => padTop + (1 - (v - min) / (max - min)) * (h - padTop - padBottom);

  // Smooth curve through the points (Catmull-Rom converted to cubic Bézier).
  const xy = points.map((p, i) => [x(i), y(p.score)] as const);
  let line = `M${xy[0][0].toFixed(1)},${xy[0][1].toFixed(1)}`;
  for (let i = 0; i < xy.length - 1; i++) {
    const p0 = xy[i - 1] ?? xy[i];
    const p1 = xy[i];
    const p2 = xy[i + 1];
    const p3 = xy[i + 2] ?? p2;
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
    const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    line += ` C${c1[0].toFixed(1)},${c1[1].toFixed(1)} ${c2[0].toFixed(1)},${c2[1].toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`;
  }
  const area = `${line} L${xy[xy.length - 1][0].toFixed(1)},${h - padBottom} L${xy[0][0].toFixed(1)},${h - padBottom} Z`;
  const baseY = y(50);

  const label = (p: StabilityScorePoint) =>
    p.visited_at
      ? new Date(p.visited_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", timeZone: "Asia/Kolkata" })
      : "";

  const d = delta ?? (scores.length > 1 ? latest - scores[scores.length - 2] : null);
  const mood = latest >= 55 ? "Thriving" : latest >= 50 ? "Steady" : latest >= 45 ? "Watch" : "Needs care";
  const tone = latest >= 50 ? "is-good" : latest >= 45 ? "is-watch" : "is-low";

  return (
    <section className="kl-card" aria-labelledby="kl-title">
      <header className="kl-head">
        <div>
          <p className="kl-mark" id="kl-title">
            <span className="kl-kush">Kush</span>
            <span className="kl-life">Life</span>
            <span className="kl-mark-sub">trend</span>
          </p>
          <p className="kl-sub">How they are living, visit by visit</p>
        </div>
        <div className="kl-now">
          <strong>{latest}</strong>
          <span className={`kl-chip ${tone}`}>{mood}</span>
          {d != null && d !== 0 ? (
            <span className={d > 0 ? "kl-delta is-up" : "kl-delta is-down"}>
              {d > 0 ? "↑" : "↓"} {Math.abs(d)} since last visit
            </span>
          ) : null}
        </div>
      </header>

      <svg
        className="kl-chart"
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`KushLife score from ${scores[0]} to ${latest} over ${points.length} visits`}
      >
        <defs>
          <linearGradient id="kl-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#7fd4ff" stopOpacity="0.28" />
            <stop offset="100%" stopColor="#7fd4ff" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="kl-stroke" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor="#8ab83e" />
            <stop offset="100%" stopColor="#7fd4ff" />
          </linearGradient>
        </defs>
        <line className="kl-base" x1={padX} x2={w - padX} y1={baseY} y2={baseY} />
        <text className="kl-base-label" x={w - padX} y={baseY + 16} textAnchor="end">
          Personal normal · 50
        </text>
        <path className="kl-area" d={area} />
        <path className="kl-line" d={line} />
        {xy.map(([cx, cy], i) => (
          <circle
            key={points[i].visit_id ?? i}
            className={i === xy.length - 1 ? "kl-dot is-last" : "kl-dot"}
            cx={cx}
            cy={cy}
            r={i === xy.length - 1 ? 6 : 4}
          />
        ))}
        {xy.map(([cx], i) =>
          i === 0 || i === xy.length - 1 || i % 2 === 0 ? (
            <text key={`t${i}`} className="kl-x" x={cx} y={h - 8} textAnchor="middle">
              {label(points[i])}
            </text>
          ) : null,
        )}
      </svg>

      <ul className="kl-legend">
        <li className="kl-legend-title">Checked every visit</li>
        <li>
          <i className="is-safe" /> Safe
        </li>
        <li>
          <i className="is-steady" /> Steady
        </li>
        <li>
          <i className="is-settled" /> Settled
        </li>
        <li>
          <i className="is-connected" /> Connected
        </li>
      </ul>
      <p className="kl-note">
        Scored by the Family Partner from the four KushLife checks on each visit. 50 is their
        personal normal — higher is better than usual. Not a medical diagnosis.
      </p>
    </section>
  );
}
