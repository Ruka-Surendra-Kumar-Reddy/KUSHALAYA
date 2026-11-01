"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type SignatureValue = { png: string | null; text: string | null };

/**
 * Draw a signature (finger, stylus or mouse — Pointer Events) or type it.
 * Reports a PNG data URL for a drawing, or the typed text.
 */
export function SignaturePad({
  onChange,
  defaultTyped = "",
  label = "Signature",
}: {
  onChange: (v: SignatureValue) => void;
  defaultTyped?: string;
  label?: string;
}) {
  const [mode, setMode] = useState<"draw" | "type">("draw");
  const [typed, setTyped] = useState(defaultTyped);
  const [hasInk, setHasInk] = useState(false);
  const canvas = useRef<HTMLCanvasElement>(null);
  const drawing = useRef(false);
  const last = useRef<{ x: number; y: number } | null>(null);

  const setup = useCallback(() => {
    const c = canvas.current;
    if (!c) return;
    const ratio = Math.max(1, window.devicePixelRatio || 1);
    const w = c.clientWidth;
    const h = c.clientHeight;
    c.width = Math.round(w * ratio);
    c.height = Math.round(h * ratio);
    const ctx = c.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.lineWidth = 2.4;
    ctx.strokeStyle = "#10243a";
  }, []);

  useEffect(() => {
    if (mode === "draw") {
      setup();
      setHasInk(false);
    }
  }, [mode, setup]);

  useEffect(() => {
    if (mode === "type") onChange({ png: null, text: typed.trim() || null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, typed]);

  function point(e: React.PointerEvent<HTMLCanvasElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  }

  function down(e: React.PointerEvent<HTMLCanvasElement>) {
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);
    drawing.current = true;
    last.current = point(e);
    const ctx = e.currentTarget.getContext("2d");
    if (ctx && last.current) {
      ctx.beginPath();
      ctx.arc(last.current.x, last.current.y, 1.1, 0, Math.PI * 2);
      ctx.fillStyle = "#10243a";
      ctx.fill();
    }
  }

  function move(e: React.PointerEvent<HTMLCanvasElement>) {
    if (!drawing.current) return;
    e.preventDefault();
    const ctx = e.currentTarget.getContext("2d");
    const p = point(e);
    if (ctx && last.current) {
      ctx.beginPath();
      ctx.moveTo(last.current.x, last.current.y);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
    }
    last.current = p;
  }

  function up() {
    if (!drawing.current) return;
    drawing.current = false;
    last.current = null;
    setHasInk(true);
    const c = canvas.current;
    if (c) onChange({ png: c.toDataURL("image/png"), text: null });
  }

  function clear() {
    setup();
    setHasInk(false);
    onChange({ png: null, text: null });
  }

  return (
    <div className="ct-sigpad">
      <div className="ct-sigpad-head">
        <span className="ct-sigpad-label">{label}</span>
        <div className="ct-seg" role="tablist" aria-label="How to sign">
          <button type="button" role="tab" aria-selected={mode === "draw"} className={mode === "draw" ? "is-on" : ""} onClick={() => setMode("draw")}>
            Draw
          </button>
          <button type="button" role="tab" aria-selected={mode === "type"} className={mode === "type" ? "is-on" : ""} onClick={() => setMode("type")}>
            Type
          </button>
        </div>
      </div>
      {mode === "draw" ? (
        <>
          <canvas
            ref={canvas}
            className="ct-canvas"
            aria-label="Draw your signature here"
            onPointerDown={down}
            onPointerMove={move}
            onPointerUp={up}
            onPointerCancel={up}
            onPointerLeave={up}
          />
          <div className="ct-sigpad-foot">
            <span className="muted">{hasInk ? "Signature captured" : "Sign with your finger or mouse"}</span>
            <button type="button" className="secondary ct-small" onClick={clear}>
              Clear
            </button>
          </div>
        </>
      ) : (
        <>
          <input
            className="ct-typed-input"
            aria-label="Type your signature"
            value={typed}
            maxLength={100}
            placeholder="Type your name as your signature"
            onChange={(e) => setTyped(e.target.value)}
          />
          <div className="ct-typed-preview" aria-hidden="true">
            {typed || " "}
          </div>
        </>
      )}
    </div>
  );
}

/** Show a saved signature: the image, or the typed text in the signature font. */
export function SignatureView({ png, text }: { png: string | null; text: string | null }) {
  if (png) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img className="ct-sig-img" src={png} alt="Signature" />;
  }
  return <span className="ct-sig-typed">{text || ""}</span>;
}
