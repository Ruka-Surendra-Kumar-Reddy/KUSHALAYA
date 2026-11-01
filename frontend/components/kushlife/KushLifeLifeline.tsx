"use client";

import { useEffect, useRef, useState } from "react";
import { lifelineScore, lifelineWord, type KushLifeView } from "@/lib/kushlife";
import "./lifeline.css";

const SLEEP: Record<string, string> = { well: "Slept well", poorly: "Slept poorly" };
const APPETITE: Record<string, string> = { usual: "Ate as usual", less: "Ate less", more: "Ate more" };

function time(iso: string | null) {
  return iso ? new Date(iso).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit", timeZone: "Asia/Kolkata" }) : "";
}

const toneOf = (score: number) => (score >= 48 ? "is-good" : score >= 40 ? "is-watch" : "is-low");

function day(iso: string | null) {
  return iso
    ? new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", timeZone: "Asia/Kolkata" })
    : "";
}

/** Smooth curve through the points (Catmull-Rom as cubic Bézier). */
function curve(pts: [number, number][]) {
  let d = `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] ?? p2;
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
    const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    d += ` C${c1[0].toFixed(1)},${c1[1].toFixed(1)} ${c2[0].toFixed(1)},${c2[1].toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`;
  }
  return d;
}

/** One heartbeat from (x, y) to the right: P wave, QRS spike, T wave. */
function beat(x: number, y: number, w: number) {
  const u = w / 64;
  const pts: [number, number][] = [
    [8, 0], [12, -3], [16, 0], [22, 0], [24, 4], [28, -22], [32, 11], [35, 0], [42, 0], [47, -6], [52, 0], [64, 0],
  ];
  return `M${x},${y} ` + pts.map(([dx, dy]) => `L${(x + dx * u).toFixed(1)},${(y + dy).toFixed(1)}`).join(" ");
}

/**
 * The KushLife lifeline: one score per visit (50 = their usual) drawn like a heart monitor,
 * ending in a live beat. Tap a point to see that visit.
 */
export function KushLifeLifeline({ view }: { view: KushLifeView }) {
  const box = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);
  const visits = [...view.visits].reverse(); // oldest → newest
  const [pick, setPick] = useState(visits.length - 1);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.round(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  useEffect(() => setPick(visits.length - 1), [visits.length]);

  if (!visits.length) {
    return (
      <div className="kll">
        <Head />
        <p className="kll-empty">The lifeline starts after the first visit.</p>
      </div>
    );
  }

  const scores = visits.map(lifelineScore);
  const latest = scores[scores.length - 1];
  const delta = scores.length > 1 ? latest - scores[scores.length - 2] : 0;
  const word = lifelineWord(latest);
  const tone = toneOf(latest);
  // Several visits on one day: label them by time so the points can be told apart.
  const days = visits.map((v) => day(v.date));
  const when = (i: number) => (days.filter((d) => d === days[i]).length > 1 ? `${days[i]}, ${time(visits[i].date)}` : days[i]);
  const tick = (i: number) => (days.filter((d) => d === days[i]).length > 1 && days.indexOf(days[i]) !== i ? time(visits[i].date) : days[i]);

  const h = w < 520 ? 170 : 210;
  const tail = Math.min(84, Math.max(56, w * 0.14));
  const padL = 14;
  const padR = tail + 10;
  const padT = 26;
  const padB = 28;
  const lo = Math.max(0, Math.min(...scores, 40) - 6);
  const hi = Math.min(70, Math.max(...scores, 54) + 6);
  const plotW = Math.max(10, w - padL - padR);
  const x = (i: number) => (visits.length === 1 ? padL + plotW / 2 : padL + (i / (visits.length - 1)) * plotW);
  const y = (v: number) => padT + (1 - (v - lo) / (hi - lo)) * (h - padT - padB);
  const pts = scores.map((s, i) => [x(i), y(s)] as [number, number]);
  const lead: [number, number] = [padL - 8, pts[0][1]];
  const line = curve(visits.length === 1 ? [lead, pts[0]] : pts);
  const last = pts[pts.length - 1];
  const area = `${line} L${last[0].toFixed(1)},${h - padB} L${pts[0][0].toFixed(1)},${h - padB} Z`;
  const usualY = y(50);
  const every = Math.max(1, Math.ceil(visits.length / Math.max(2, Math.floor(plotW / 64))));
  const sel = visits[pick] ?? visits[visits.length - 1];
  const selScore = scores[pick] ?? latest;
  const changed = Object.values(sel.chips).flat();

  return (
    <div className="kll">
      <Head>
        <div className="kll-now">
          <strong>{latest}</strong>
          <span className={`kll-chip ${tone}`}>{word}</span>
          {delta ? (
            <span className={delta > 0 ? "kll-delta is-up" : "kll-delta is-down"}>
              {delta > 0 ? "▲" : "▼"} {Math.abs(delta)} since last visit
            </span>
          ) : (
            <span className="kll-delta">Same as last visit</span>
          )}
        </div>
      </Head>

      <div className="kll-screen" ref={box}>
        {w ? (
          <svg
            width={w}
            height={h}
            viewBox={`0 0 ${w} ${h}`}
            role="img"
            aria-label={`KushLife lifeline: ${scores.length} visits, latest ${latest} (${word}). 50 is their usual.`}
          >
            <defs>
              <pattern id="kll-grid" width="20" height="20" patternUnits="userSpaceOnUse">
                <path d="M20 0H0V20" fill="none" className="kll-gridline" />
              </pattern>
              <linearGradient id="kll-stroke" x1="0" x2="1" y1="0" y2="0">
                <stop offset="0%" stopColor="#7fd4ff" />
                <stop offset="100%" stopColor="#9be15d" />
              </linearGradient>
              <linearGradient id="kll-fill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="#9be15d" stopOpacity="0.28" />
                <stop offset="100%" stopColor="#7fd4ff" stopOpacity="0" />
              </linearGradient>
              <filter id="kll-glow" x="-20%" y="-50%" width="140%" height="200%">
                <feGaussianBlur stdDeviation="3" result="b" />
                <feMerge>
                  <feMergeNode in="b" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>
            <rect width={w} height={h} fill="url(#kll-grid)" />
            <line className="kll-usual" x1={padL} x2={w - 6} y1={usualY} y2={usualY} />
            <text className="kll-usual-label" x={padL} y={usualY - 6}>
              Their usual · 50
            </text>
            <path className="kll-area" d={area} />
            <path className="kll-line" d={line} pathLength={1} filter="url(#kll-glow)" />
            <path className="kll-beat" d={beat(last[0], last[1], tail)} pathLength={1} filter="url(#kll-glow)" />
            {pts.map(([cx, cy], i) => (
              <g
                key={visits[i].job_id}
                className={`kll-pt ${toneOf(scores[i])}${i === pick ? " is-picked" : ""}`}
                tabIndex={0}
                role="button"
                aria-label={`${when(i)}: ${scores[i]}, ${lifelineWord(scores[i])}`}
                onClick={() => setPick(i)}
                onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setPick(i)}
              >
                <circle className="kll-hit" cx={cx} cy={cy} r={16} />
                {i === pts.length - 1 ? <circle className="kll-pulse" cx={cx} cy={cy} r={6} /> : null}
                <circle className="kll-dot" cx={cx} cy={cy} r={i === pts.length - 1 ? 6 : 4.5} />
              </g>
            ))}
            {pts.map(([cx], i) =>
              i === pts.length - 1 || (i % every === 0 && pts[pts.length - 1][0] - cx > 44) ? (
                <text key={`d${i}`} className="kll-x" x={cx} y={h - 9} textAnchor="middle">
                  {tick(i)}
                </text>
              ) : null,
            )}
          </svg>
        ) : (
          <div style={{ height: 190 }} />
        )}
      </div>

      <p className="kll-visit" aria-live="polite">
        <strong>
          {when(pick)} · {selScore} · {lifelineWord(selScore)}
        </strong>
        <span>
          {[SLEEP[sel.sleep ?? ""], APPETITE[sel.appetite ?? ""]].filter(Boolean).join(" · ")}
          {changed.length ? ` · Changed: ${changed.join(", ").toLowerCase()}` : " · All four checks as usual"}
        </span>
      </p>
      <p className="kll-note">
        Above the line is better than usual, below means something changed. Built from the Safe, Steady,
        Settled and Connected checks at every visit. Not a medical score.
      </p>
    </div>
  );
}

function Head({ children }: { children?: React.ReactNode }) {
  return (
    <div className="kll-head">
      <p className="kll-mark">
        <span className="kll-kush">Kush</span>
        <span className="kll-life">Life</span>
        <span className="kll-sub">lifeline</span>
      </p>
      {children}
    </div>
  );
}
