"use client";

import { useState } from "react";

/**
 * Before/after photo compare: drag the handle (or use the arrow keys on the
 * range input) to reveal the "after" picture over the "before" one.
 */
export function BeforeAfter({
  before,
  after,
  beforeAlt,
  afterAlt,
  width,
  height,
}: {
  before: string;
  after: string;
  beforeAlt: string;
  afterAlt: string;
  width: number;
  height: number;
}) {
  const [pos, setPos] = useState(50);
  return (
    <figure className="mk-ba" style={{ aspectRatio: `${width} / ${height}` }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img className="mk-ba-img" src={before} alt={beforeAlt} width={width} height={height} loading="lazy" />
      <div className="mk-ba-after" style={{ clipPath: `inset(0 0 0 ${pos}%)` }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img className="mk-ba-img" src={after} alt={afterAlt} width={width} height={height} loading="lazy" />
      </div>
      <span className="mk-ba-tag mk-ba-tag--before">Before</span>
      <span className="mk-ba-tag mk-ba-tag--after">AI preview</span>
      <span className="mk-ba-line" style={{ left: `${pos}%` }} aria-hidden="true">
        <span className="mk-ba-knob">‹ ›</span>
      </span>
      <input
        className="mk-ba-range"
        type="range"
        min={0}
        max={100}
        value={pos}
        onChange={(e) => setPos(Number(e.target.value))}
        aria-label="Slide to compare the room before and with the safety products"
      />
    </figure>
  );
}
