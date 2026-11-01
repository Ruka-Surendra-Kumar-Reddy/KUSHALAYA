"use client";

import { useCallback, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import "./before-after.css";

export type SliderMarker = { n: number; product?: string; x: number; y: number; w: number; h: number };

/**
 * Before/after wipe: drag the handle (mouse or touch), or focus it and use ←/→,
 * PageUp/PageDown, Home/End. Used in ops review and the family view.
 * `markers` are real positions from the product check (fractions of the image);
 * none are drawn when there are none — positions are never invented.
 */
export function BeforeAfterSlider({
  beforeSrc,
  afterSrc,
  beforeAlt,
  afterAlt,
  markers = [],
  initial = 50,
  label = "Before and after",
}: {
  beforeSrc: string;
  afterSrc: string;
  beforeAlt: string;
  afterAlt: string;
  markers?: SliderMarker[];
  initial?: number;
  label?: string;
}) {
  const [pos, setPos] = useState(initial);
  const box = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const fromClientX = useCallback((clientX: number) => {
    const r = box.current?.getBoundingClientRect();
    if (!r || r.width === 0) return;
    setPos(Math.min(100, Math.max(0, ((clientX - r.left) / r.width) * 100)));
  }, []);

  function onPointerDown(e: PointerEvent<HTMLDivElement>) {
    dragging.current = true;
    e.currentTarget.setPointerCapture?.(e.pointerId);
    fromClientX(e.clientX);
  }
  function onPointerMove(e: PointerEvent<HTMLDivElement>) {
    if (dragging.current) fromClientX(e.clientX);
  }
  function onPointerUp(e: PointerEvent<HTMLDivElement>) {
    dragging.current = false;
    e.currentTarget.releasePointerCapture?.(e.pointerId);
  }
  function onKey(e: KeyboardEvent<HTMLDivElement>) {
    const step = e.key === "PageUp" || e.key === "PageDown" ? 20 : 5;
    let next = pos;
    if (e.key === "ArrowLeft" || e.key === "ArrowDown" || e.key === "PageDown") next = pos - step;
    else if (e.key === "ArrowRight" || e.key === "ArrowUp" || e.key === "PageUp") next = pos + step;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = 100;
    else return;
    e.preventDefault();
    setPos(Math.min(100, Math.max(0, next)));
  }

  return (
    <div className="ba" role="group" aria-label={label}>
      <div
        className="ba-frame"
        ref={box}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img className="ba-img" src={afterSrc} alt={afterAlt} draggable={false} />
        {markers.map((m) => (
          <span
            key={m.n}
            className="ba-marker"
            style={{ left: `${(m.x + m.w / 2) * 100}%`, top: `${(m.y + m.h / 2) * 100}%` }}
            title={m.product}
            aria-hidden="true"
          >
            {m.n}
          </span>
        ))}
        <div className="ba-before" style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img className="ba-img" src={beforeSrc} alt={beforeAlt} draggable={false} />
        </div>
        <span className="ba-tag ba-tag-before" aria-hidden="true">Before</span>
        <span className="ba-tag ba-tag-after" aria-hidden="true">After</span>
        <div
          className="ba-handle"
          style={{ left: `${pos}%` }}
          role="slider"
          tabIndex={0}
          aria-label="Drag to compare before and after"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(pos)}
          aria-valuetext={`${Math.round(pos)}% before shown`}
          onKeyDown={onKey}
        >
          <span className="ba-knob" aria-hidden="true">
            ‹ ›
          </span>
        </div>
      </div>
    </div>
  );
}
