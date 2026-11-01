"use client";

import { useEffect, useRef, useState } from "react";
import { postFormData } from "@/lib/api";
import { fieldJobBase } from "@/lib/jobs";

const MAX_S = 60;

function pickMime(): string {
  if (typeof MediaRecorder === "undefined") return "";
  for (const m of ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"]) {
    if (MediaRecorder.isTypeSupported?.(m)) return m;
  }
  return "";
}

/** #100: a short voice note on a visit (≤ 60 s). Staff hear it; the family only if the manager shares it. */
export function VoiceNoteRecorder({ jobId, className = "" }: { jobId: number; className?: string }) {
  const [state, setState] = useState<"idle" | "recording" | "saving">("idle");
  const [secs, setSecs] = useState(0);
  const [saved, setSaved] = useState(0);
  const [msg, setMsg] = useState("");
  const rec = useRef<MediaRecorder | null>(null);
  const timer = useRef<number | null>(null);
  const started = useRef(0);
  const [supported, setSupported] = useState(true);

  useEffect(() => {
    setSupported(typeof MediaRecorder !== "undefined" && !!navigator.mediaDevices?.getUserMedia);
  }, []);

  useEffect(() => () => {
    if (timer.current) window.clearInterval(timer.current);
    rec.current?.stream.getTracks().forEach((t) => t.stop());
  }, []);

  if (!supported) {
    return (
      <div className={`cg-row ${className}`}>
        <button type="button" className="cg-btn is-ghost" disabled>
          🎙 Voice note
        </button>
        <small>This phone can&apos;t record voice notes — type a note instead.</small>
      </div>
    );
  }

  async function start() {
    setMsg("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = pickMime();
      const r = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      const chunks: Blob[] = [];
      r.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      r.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        if (timer.current) window.clearInterval(timer.current);
        const duration = Math.max(1, Math.min(MAX_S, Math.round((Date.now() - started.current) / 1000)));
        const type = (r.mimeType || mime || "audio/webm").split(";")[0];
        void upload(new Blob(chunks, { type }), type, duration);
      };
      rec.current = r;
      started.current = Date.now();
      setSecs(0);
      r.start();
      setState("recording");
      timer.current = window.setInterval(() => {
        const s = Math.round((Date.now() - started.current) / 1000);
        setSecs(s);
        if (s >= MAX_S && r.state === "recording") r.stop();
      }, 250);
    } catch {
      setMsg("Allow the microphone in your browser settings to record a voice note.");
    }
  }

  async function upload(blob: Blob, type: string, duration: number) {
    setState("saving");
    const ext = type.includes("ogg") ? "ogg" : type.includes("mp4") ? "m4a" : "webm";
    const form = new FormData();
    form.append("file", new File([blob], `voice-note.${ext}`, { type }));
    form.append("duration_s", String(duration));
    try {
      await postFormData(`${fieldJobBase(jobId)}/voice-notes`, form);
      setSaved((n) => n + 1);
      setMsg("");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Could not save the voice note");
    } finally {
      setState("idle");
    }
  }

  return (
    <div className={`cg-row ${className}`}>
      {state === "recording" ? (
        <button type="button" className="cg-btn is-out" onClick={() => rec.current?.stop()}>
          ■ Stop ({MAX_S - secs}s left)
        </button>
      ) : (
        <button type="button" className="cg-btn is-ghost" disabled={state === "saving"} onClick={() => void start()}>
          🎙 {state === "saving" ? "Saving…" : "Voice note"}
        </button>
      )}
      {saved ? <small className="cg-ok">{saved} voice note{saved === 1 ? "" : "s"} saved</small> : null}
      {msg ? <small role="alert">{msg}</small> : null}
    </div>
  );
}
