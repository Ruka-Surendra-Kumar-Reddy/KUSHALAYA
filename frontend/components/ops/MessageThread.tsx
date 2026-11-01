"use client";

import Link from "next/link";
import "@/components/ops/messages.css";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { formatIST } from "@/lib/ist";
import { can } from "@/lib/roles";

/** Mirrors the care_router family-messages endpoints in home_safety_family.py. */
export type FamilyMessage = { id: string; body: string; sender_role: string; sender_name: string; created_at: string };
export type InboxRow = {
  elder_id: number;
  elder_name: string;
  message_count: number;
  unread_count: number;
  staff_read_at: string | null;
  last_message: FamilyMessage;
};
type Thread = { elder_id: number; elder_name: string; unread_count: number; messages: FamilyMessage[] };
type Context = { manager_name: string; next_visit_at: string | null; next_visit_title: string | null; open_alerts: number };

export const FAMILY_MESSAGES_API = "/api/v1/home-safety/care/family-messages";
const BASE = FAMILY_MESSAGES_API;

const QUICK_REPLIES = [
  "Thanks, we're on it.",
  "We'll call you shortly.",
  "Visit booked — details in your Schedule.",
  "Thank you for letting us know.",
];

/** A family "Call me" / "Ask about…" lands in the thread as "Please call me — …" or "Question…: …". */
export function isCallRequest(m: FamilyMessage | null | undefined): boolean {
  return !!m && m.sender_role !== "team" && /^(Please call me|Question\b)/.test(m.body);
}

function contextLine(c: Context): string {
  const parts: string[] = [];
  if (c.manager_name) parts.push(`Manager: ${c.manager_name}`);
  parts.push(c.next_visit_at ? `Next visit ${formatIST(c.next_visit_at).replace(/ IST.*$/, "")}` : "No visit booked");
  if (c.open_alerts) parts.push(`${c.open_alerts} open alert${c.open_alerts === 1 ? "" : "s"}`);
  return parts.join(" · ");
}

function stamp(value: string): string {
  return new Date(value).toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "Asia/Kolkata",
  });
}

/**
 * One family conversation: header (client link, context), messages, and a reply box pinned to the
 * bottom. Loads itself, marks the thread read when it has unread messages, and sends replies.
 * Give it a parent with a height (or pass `embedded`) — the message list scrolls inside.
 */
export function MessageThread({
  elderId,
  onBack,
  onChanged,
  onMarkedUnread,
  showClientLink = true,
  embedded = false,
}: {
  elderId: number;
  /** Shows a "← Back" button (phone list ↔ thread). */
  onBack?: () => void;
  /** Called after the thread is read, replied to or marked unread — refresh any inbox counts. */
  onChanged?: () => void;
  /** Called after "Mark as unread"; the parent usually closes the thread. Hidden when omitted. */
  onMarkedUnread?: () => void;
  showClientLink?: boolean;
  /** Fixed height for use inside another page (e.g. the client page). */
  embedded?: boolean;
}) {
  const [thread, setThread] = useState<Thread | null>(null);
  const [ctx, setCtx] = useState<Context | null>(null);
  const [reply, setReply] = useState("");
  // View-only staff read the conversation; replying is for staff who can act.
  const edit = can("edit");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [failed, setFailed] = useState(false);
  // The thread on screen, so a late reply for another client is dropped.
  const openId = useRef(elderId);
  const listRef = useRef<HTMLUListElement | null>(null);
  const changed = useRef(onChanged);
  changed.current = onChanged;

  const load = useCallback(async (id: number) => {
    setError("");
    setFailed(false);
    try {
      const t = await api<Thread>(`${BASE}/${id}`);
      if (openId.current !== id) return;
      setThread(t);
      window.requestAnimationFrame(() => {
        if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
      });
      if (t.unread_count > 0 && can("edit")) {
        await api(`${BASE}/${id}/read`, { method: "POST" });
        changed.current?.();
      }
    } catch (e) {
      if (openId.current !== id) return;
      setFailed(true);
      setError(e instanceof Error ? e.message : "Could not open this conversation");
    }
  }, []);

  useEffect(() => {
    openId.current = elderId;
    setThread(null);
    setCtx(null);
    setReply("");
    void load(elderId);
    api<Context>(`${BASE}/${elderId}/context`)
      .then((c) => {
        if (openId.current === elderId) setCtx(c);
      })
      .catch(() => undefined);
  }, [elderId, load]);

  async function markUnread() {
    setError("");
    try {
      await api(`${BASE}/${elderId}/unread`, { method: "POST" });
      changed.current?.();
      onMarkedUnread?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not mark unread");
    }
  }

  async function sendReply() {
    if (!reply.trim()) return;
    setBusy(true);
    setError("");
    try {
      await api(`${BASE}/${elderId}/reply`, { method: "POST", body: JSON.stringify({ body: reply.trim() }) });
      setReply("");
      await load(elderId);
      changed.current?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not send");
    } finally {
      setBusy(false);
    }
  }

  const name = thread?.elder_name || "";

  return (
    <section className={`km-thread${embedded ? " is-embedded" : ""}`} aria-label={name ? `Messages with ${name}'s family` : "Conversation"}>
      <header className="km-thread-head">
        {onBack ? (
          <button type="button" className="km-back" onClick={onBack}>
            ← Back
          </button>
        ) : null}
        <div className="km-thread-title">
          <h2>
            {!name ? (
              "Loading…"
            ) : showClientLink ? (
              <Link href={`/kushalaya/customers/${elderId}`}>{name}</Link>
            ) : (
              name
            )}
          </h2>
          {ctx ? <p className="km-context">{contextLine(ctx)}</p> : null}
        </div>
        {thread && onMarkedUnread && edit ? (
          <button type="button" className="km-link-btn" onClick={() => void markUnread()}>
            Mark unread
          </button>
        ) : null}
      </header>

      <ul ref={listRef} className="km-messages">
        {failed ? (
          <li className="km-state">
            <p>Could not open this conversation.</p>
            <button type="button" className="secondary" onClick={() => void load(elderId)}>
              Try again
            </button>
          </li>
        ) : !thread ? (
          <li className="km-state">Loading messages…</li>
        ) : thread.messages.length === 0 ? (
          <li className="km-state">No messages yet. Write the first one below — the family sees it in their portal.</li>
        ) : (
          thread.messages.map((m) => {
            const team = m.sender_role === "team";
            return (
              <li key={m.id} className={`km-msg ${team ? "is-team" : "is-family"}${isCallRequest(m) ? " is-call" : ""}`}>
                {isCallRequest(m) ? <span className="km-tag">{m.body.startsWith("Please call") ? "Call me" : "Question"}</span> : null}
                <p>{m.body}</p>
                <span className="km-meta">
                  {m.sender_name || (team ? "Care team" : "Family")} · {stamp(m.created_at)}
                </span>
              </li>
            );
          })
        )}
      </ul>

      {edit ? (
      <footer className="km-compose">
        {error && !failed ? <p className="error-text km-error">{error}</p> : null}
        <div className="km-quick" aria-label="Quick replies">
          {QUICK_REPLIES.map((q) => (
            <button key={q} type="button" className="km-chip" onClick={() => setReply(q)}>
              {q}
            </button>
          ))}
        </div>
        <div className="km-reply">
          <textarea
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                void sendReply();
              }
            }}
            placeholder="Write a reply…"
            aria-label="Reply"
            rows={2}
            maxLength={2000}
          />
          <button type="button" disabled={busy || !reply.trim() || !thread} onClick={() => void sendReply()}>
            {busy ? "Sending…" : "Send"}
          </button>
        </div>
        <p className="km-hint">The family sees this in their portal. Ctrl+Enter sends.</p>
      </footer>
      ) : null}
    </section>
  );
}
