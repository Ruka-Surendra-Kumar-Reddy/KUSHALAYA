"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

import { Flash } from "@/components/Flash";
import { HomeSafetyShell } from "@/components/livewell/HomeSafetyShell";
import { getStoredAuth } from "@/lib/api";
import { withPublicBrand } from "@/lib/public-brand";
import {
  createRecommendationConversation,
  getRecommendationConversation,
  listRecommendationConversations,
  sendRecommendationMessage,
  type RecommendationChatMessage,
  type RecommendationConversation,
} from "@/lib/livewell/recommendationChatApi";

const SUGGESTIONS = [
  "What are the top 3 recommendations for this elder based on unsafe items?",
  "Which catalog products fit bathroom fall risks on this assessment?",
  "Suggest solutions for lighting and night navigation.",
];

function messageError(err: unknown): string {
  if (!err) return "Something went wrong";
  if (typeof err === "string") return err;
  if (err instanceof Error && err.message) return err.message;
  if (typeof err === "object") {
    const o = err as Record<string, unknown>;
    if (typeof o.message === "string" && o.message) return o.message;
    if (typeof o.detail === "string") return o.detail;
    if (Array.isArray(o.detail)) {
      return o.detail
        .map((d) => (typeof d === "object" && d && "msg" in d ? String((d as { msg: unknown }).msg) : String(d)))
        .join("; ");
    }
  }
  return "Something went wrong";
}

function RecommendationCards({ message }: { message: RecommendationChatMessage }) {
  const recs = message.structured?.recommendations || [];
  if (!recs.length && !message.requires_human_review) return null;
  return (
    <div className="home-safety-rec-chat-cards">
      {message.requires_human_review && (
        <p className="home-safety-rec-chat-review" role="status">
          Human review recommended
          {message.structured?.reason_for_review
            ? `: ${message.structured.reason_for_review}`
            : "."}
        </p>
      )}
      {recs.map((rec, idx) => (
        <article key={`${message.id}-${idx}`} className="home-safety-rec-chat-card">
          <header>
            <strong>{rec.priority || "medium"}</strong>
            {rec.product_id ? <span>Product: {rec.product_id}</span> : null}
            {rec.solution_id ? <span>Solution: {rec.solution_id}</span> : null}
          </header>
          <p>{rec.reason}</p>
          {rec.requires_human_review && rec.review_reason ? (
            <p className="muted">Review: {rec.review_reason}</p>
          ) : null}
        </article>
      ))}
    </div>
  );
}

export default function AssessorRecommendationChatPage() {
  const params = useParams();
  const assessmentId = String(params.id);
  const auth = getStoredAuth();

  const [conversation, setConversation] = useState<RecommendationConversation | null>(null);
  const [messages, setMessages] = useState<RecommendationChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const ensureConversation = useCallback(async () => {
    const existing = await listRecommendationConversations(assessmentId);
    if (existing.length > 0) {
      const detail = await getRecommendationConversation(existing[0].id);
      setConversation(detail);
      setMessages(detail.messages || []);
      return detail;
    }
    const created = await createRecommendationConversation(assessmentId);
    setConversation(created);
    setMessages([]);
    return created;
  }, [assessmentId]);

  useEffect(() => {
    let cancelled = false;
    async function boot() {
      setLoading(true);
      setError("");
      try {
        if (!getStoredAuth()?.access_token) {
          setError(withPublicBrand("Sign in to LiveWell360 to use recommendation chat."));
          return;
        }
        await ensureConversation();
      } catch (err) {
        if (!cancelled) setError(messageError(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void boot();
    return () => {
      cancelled = true;
    };
  }, [ensureConversation]);

  const title = useMemo(
    () => conversation?.title || "AI recommendation chat",
    [conversation?.title],
  );

  async function onSend(e: FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || sending) return;
    setSending(true);
    setError("");
    try {
      let convo = conversation;
      if (!convo) convo = await ensureConversation();
      const result = await sendRecommendationMessage(convo.id, text);
      setConversation(result.conversation);
      setMessages((prev) => [...prev, result.user_message, result.assistant_message]);
      setDraft("");
    } catch (err) {
      setError(messageError(err));
    } finally {
      setSending(false);
    }
  }

  async function onSuggestion(text: string) {
    setDraft(text);
  }

  if (!auth?.access_token && !loading && error) {
    return (
      <HomeSafetyShell title="Recommendation chat" backHref={`/kushalaya/assess/${assessmentId}`}>
        <main className="home-safety-app">
          <div className="card home-safety-empty">
            <h1 style={{ marginTop: 0 }}>Sign in required</h1>
            <p className="muted">{withPublicBrand("Recommendation chat needs a LiveWell360 session.")}</p>
            <p>
              <Link href={`/login?redirect=/kushalaya/assess/${assessmentId}/recommendations`}>
                Sign in
              </Link>
            </p>
          </div>
        </main>
      </HomeSafetyShell>
    );
  }

  return (
    <HomeSafetyShell title={title} backHref={`/kushalaya/assess/${assessmentId}`}>
      <main className="home-safety-app home-safety-rec-chat">
        <Flash error={error} onClear={() => setError("")} />
        <p className="muted home-safety-section-hint">
          Grounded in assessment <code>{assessmentId}</code> plus allowlisted catalog/solutions.
          Verify every suggestion on site. Not medical advice.
        </p>

        {loading ? (
          <p>Loading conversation…</p>
        ) : (
          <>
            <div className="home-safety-rec-chat-suggestions" aria-label="Suggested questions">
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" className="secondary" onClick={() => void onSuggestion(s)}>
                  {s}
                </button>
              ))}
            </div>

            <ul className="home-safety-rec-chat-list" aria-live="polite">
              {messages.length === 0 && (
                <li className="muted">Ask what to recommend for this elder based on the checklist.</li>
              )}
              {messages.map((m) => (
                <li
                  key={m.id}
                  className={`home-safety-rec-chat-bubble home-safety-rec-chat-${m.role}`}
                >
                  <span className="muted home-safety-rec-chat-meta">
                    {m.role === "user" ? "You" : "Assessor Copilot"}
                    {m.latency_ms != null ? ` · ${Math.round(m.latency_ms)} ms` : ""}
                  </span>
                  <p>{m.content}</p>
                  {m.role === "assistant" ? <RecommendationCards message={m} /> : null}
                </li>
              ))}
            </ul>

            <form className="home-safety-rec-chat-compose" onSubmit={(e) => void onSend(e)}>
              <label className="sr-only" htmlFor="rec-chat-input">
                Message
              </label>
              <textarea
                id="rec-chat-input"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={3}
                maxLength={4000}
                placeholder="e.g. What should I recommend for bathroom fall risk?"
                disabled={sending}
              />
              <button type="submit" className="primary" disabled={sending || !draft.trim()}>
                {sending ? "Thinking…" : "Send"}
              </button>
            </form>
          </>
        )}
      </main>
    </HomeSafetyShell>
  );
}
