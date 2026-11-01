"use client";

import { hoursWaiting, waitLabel } from "@/lib/run-sheet";
import "@/components/ops/messages.css";
import { useCallback, useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { FAMILY_MESSAGES_API, isCallRequest, MessageThread, type InboxRow } from "@/components/ops/MessageThread";
import { api } from "@/lib/api";
import { dayMonth, timeIST } from "@/lib/ist";

type Filter = "unread" | "all" | "callme";
const FILTERS: { key: Filter; label: string }[] = [
  { key: "unread", label: "Awaiting reply" },
  { key: "all", label: "All" },
  { key: "callme", label: "Call-me" },
];

const IST_DAY = (d: Date) => d.toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });

/** "10:42 am" today, "Yesterday", else the date: "Mon 5 Oct" (with the year when not this year). */
function shortTime(value: string): string {
  const d = new Date(value);
  const now = new Date();
  if (IST_DAY(d) === IST_DAY(now)) return timeIST(d);
  if (IST_DAY(d) === IST_DAY(new Date(now.getTime() - 86_400_000))) return "Yesterday";
  const sameYear = IST_DAY(d).slice(0, 4) === IST_DAY(now).slice(0, 4);
  return sameYear ? dayMonth(d, undefined, true) : `${dayMonth(d)} ${IST_DAY(d).slice(0, 4)}`;
}

/** Unread family messages, or a family message nobody has answered yet (even if read). */
function awaiting(r: InboxRow): boolean {
  return r.unread_count > 0 || (r.last_message?.sender_role ?? "family") === "family";
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join("");
}

/** Keep ?filter= and ?elder= in the URL so a reload (or a Dashboard link) lands in the same place. */
function syncUrl(filter: Filter, elder: number | null) {
  const qs = new URLSearchParams(window.location.search);
  if (filter === "all") qs.delete("filter");
  else qs.set("filter", filter);
  if (elder) qs.set("elder", String(elder));
  else qs.delete("elder");
  const q = qs.toString();
  window.history.replaceState(window.history.state, "", `${window.location.pathname}${q ? `?${q}` : ""}`);
}

export default function FamilyMessagesInboxPage() {
  const [rows, setRows] = useState<InboxRow[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  const loadInbox = useCallback(() => {
    api<InboxRow[]>(FAMILY_MESSAGES_API)
      .then((r) => {
        setRows(r);
        setLoaded(true);
        setLoadFailed(false);
      })
      .catch(() => setLoadFailed(true));
  }, []);

  // Refresh every 60 s and when the tab regains focus. Nothing opens (or is marked read) by itself,
  // except the thread named in ?elder= (from the dashboard or a client page).
  useEffect(() => {
    const qs = new URLSearchParams(window.location.search);
    const f = qs.get("filter");
    if (f === "unread" || f === "callme") setFilter(f);
    const elder = Number(qs.get("elder"));
    if (elder) setSelected(elder);
    loadInbox();
    const timer = window.setInterval(loadInbox, 60_000);
    window.addEventListener("focus", loadInbox);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", loadInbox);
    };
  }, [loadInbox]);

  function choose(f: Filter) {
    setFilter(f);
    syncUrl(f, selected);
  }

  function open(id: number | null) {
    setSelected(id);
    syncUrl(filter, id);
  }

  const counts = useMemo(
    () => ({
      unread: rows.filter(awaiting).length,
      callme: rows.filter((r) => isCallRequest(r.last_message)).length,
    }),
    [rows],
  );

  const q = search.trim().toLowerCase();
  const shown = rows.filter((r) => {
    if (filter === "unread" && !awaiting(r) && r.elder_id !== selected) return false;
    if (filter === "callme" && !isCallRequest(r.last_message)) return false;
    if (q && !r.elder_name.toLowerCase().includes(q) && !r.last_message.body.toLowerCase().includes(q)) return false;
    return true;
  });

  let emptyText = "";
  if (loaded && shown.length === 0) {
    if (rows.length === 0) emptyText = "No family messages yet. When a family writes from their portal, it appears here.";
    else if (q) emptyText = `No conversations match “${search.trim()}”.`;
    else if (filter === "unread") emptyText = "All caught up — no family is waiting for a reply.";
    else emptyText = "No call-me requests or questions waiting.";
  }

  return (
    <>
      <PageHeader title="Messages" subtitle="Family messages, call-me requests and questions." />
      <div className={`km-shell${selected ? " has-thread" : ""}`}>
        <aside className="km-list-pane" aria-label="Conversations">
          <div className="km-search">
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search clients or messages"
              aria-label="Search conversations"
            />
          </div>
          <div className="tabs ks-ltabs km-filters" role="tablist" aria-label="Show">
            {FILTERS.map((f) => {
              const n = f.key === "unread" ? counts.unread : f.key === "callme" ? counts.callme : 0;
              return (
                <button
                  key={f.key}
                  type="button"
                  role="tab"
                  aria-selected={filter === f.key}
                  className={`tab${filter === f.key ? " active" : ""}`}
                  onClick={() => choose(f.key)}
                >
                  {f.label}
                  {n ? <span className="km-count">{n}</span> : null}
                </button>
              );
            })}
          </div>
          {loadFailed ? (
            <p className="error-text km-retry">
              Could not load messages.
              <button type="button" className="km-link-btn" onClick={loadInbox}>
                Retry
              </button>
            </p>
          ) : null}
          <ul className="km-rows">
            {!loaded && !loadFailed ? <li className="km-state">Loading conversations…</li> : null}
            {emptyText ? (
              <li className="km-state">
                <p>{emptyText}</p>
                {filter !== "all" && rows.length > 0 && !q ? (
                  <button type="button" className="secondary" onClick={() => choose("all")}>
                    Show all conversations
                  </button>
                ) : null}
              </li>
            ) : null}
            {shown.map((r) => {
              const call = isCallRequest(r.last_message);
              return (
                <li key={r.elder_id}>
                  <button
                    type="button"
                    className={`km-row${selected === r.elder_id ? " is-active" : ""}${r.unread_count ? " is-unread" : ""}`}
                    aria-current={selected === r.elder_id ? "true" : undefined}
                    onClick={() => open(r.elder_id)}
                  >
                    <span className="km-avatar" aria-hidden="true">
                      {initials(r.elder_name)}
                    </span>
                    <span className="km-row-body">
                      <span className="km-row-top">
                        <strong>{r.elder_name}</strong>
                        <time dateTime={r.last_message.created_at}>{shortTime(r.last_message.created_at)}</time>
                      </span>
                      <span className="km-row-bottom">
                        <span className="km-preview">
                          {call ? <span className="km-tag">{r.last_message.body.startsWith("Please call") ? "Call me" : "Question"}</span> : null}
                          {r.last_message.sender_role === "team" ? "You: " : ""}
                          {r.last_message.body}
                        </span>
                        {r.unread_count > 0 ? (
                          <span className="km-unread" aria-label={`${r.unread_count} unread`}>
                            {r.unread_count}
                          </span>
                        ) : awaiting(r) ? (
                          <span className="km-tag km-awaiting" title="Awaiting reply">
                            Waiting {waitLabel(hoursWaiting(r.last_message.created_at))}
                          </span>
                        ) : null}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </aside>

        <div className="km-thread-pane">
          {selected ? (
            <MessageThread
              key={selected}
              elderId={selected}
              onBack={() => open(null)}
              onChanged={loadInbox}
              onMarkedUnread={() => open(null)}
            />
          ) : (
            <div className="km-pick">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
              <p>{rows.length ? "Pick a conversation on the left." : "Family conversations will show here."}</p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
