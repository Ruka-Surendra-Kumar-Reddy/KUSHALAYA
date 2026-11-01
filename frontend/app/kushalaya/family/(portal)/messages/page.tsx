"use client";

import { withPublicBrand } from "@/lib/public-brand";

import { FormEvent, useEffect, useState } from "react";
import { familyTime } from "@/lib/livewell/familyTime";
import { useFamilyTimezone } from "@/lib/family-zone";
import { FamilyShell } from "@/components/livewell/family/FamilyShell";
import { FamilyError } from "@/components/livewell/family/FamilyError";
import {
  fetchFamilyMessages,
  sendFamilyMessage,
  type FamilyMessage,
} from "@/lib/livewell/familyApi";

export default function FamilyMessagesPage() {
  const [items, setItems] = useState<FamilyMessage[]>([]);
  const [body, setBody] = useState("");
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [sent, setSent] = useState(false);
  const [sending, setSending] = useState(false);
  const tz = useFamilyTimezone();

  async function load() {
    setItems(await fetchFamilyMessages());
  }

  function retry() {
    setLoadError("");
    load().catch((e) => setLoadError(e instanceof Error ? e.message : "Failed to load"));
  }

  useEffect(() => {
    retry();
  }, []);

  async function onSend(e: FormEvent) {
    e.preventDefault();
    if (!body.trim()) return;
    setSending(true);
    setError("");
    setSent(false);
    try {
      await sendFamilyMessage(body.trim());
      setBody("");
      setSent(true);
      await load();
    } catch (err) {
      setError("Your message did not send. Please try again, or call the care team.");
    } finally {
      setSending(false);
    }
  }

  return (
    <FamilyShell title="Messages" subtitle={withPublicBrand("Talk with your LiveWell360 care team")}>
      <FamilyError message={loadError} onRetry={retry} what="your messages" />
      {error ? <p className="error-text">{error}</p> : null}
      {sent ? (
        <p className="home-safety-family-success" role="status">
          Sent. Your care manager usually replies within a day. Replies appear here.
        </p>
      ) : null}
      <p className="muted home-safety-section-hint">
        Send a question or update. Your care manager usually replies within a day. Replies appear here.
      </p>

      <div className="home-safety-family-chat">
        {items.length === 0 ? (
          <p className="muted">No messages yet. Say hello below.</p>
        ) : (
          <ul className="home-safety-family-chat-list">
            {items.map((m) => (
              <li
                key={m.id}
                className={`home-safety-family-chat-bubble ${
                  m.sender_role === "family" ? "from-family" : "from-team"
                }`}
              >
                <span className="muted home-safety-family-chat-meta">
                  {m.sender_name} · {familyTime(m.created_at, tz)}
                </span>
                <p>{m.body}</p>
              </li>
            ))}
          </ul>
        )}

        <form className="home-safety-family-chat-compose" onSubmit={(e) => void onSend(e)}>
          <label className="home-safety-field">
            Your message
            <textarea
              rows={3}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="e.g. Can someone check on the grab bar install next week?"
              required
            />
          </label>
          <button type="submit" className="primary" disabled={sending || !body.trim()}>
            {sending ? "Sending…" : "Send to care team"}
          </button>
        </form>
      </div>
    </FamilyShell>
  );
}
