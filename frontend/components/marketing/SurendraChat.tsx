"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { getApiUrl } from "@/lib/api";
import {
  CONTACT_HREF,
  PARENT_CARE_CHECK_HREF,
  US_PHONE,
} from "@/lib/marketing/family-contacts";
import { CALLBACK_PROMISE, useSiteConfig, whatsAppHref } from "@/lib/marketing/site-config";
import { phoneError } from "@/lib/marketing/form-checks";
import { CARE_PLANS, PLAN_PRICE_LINE } from "@/lib/marketing/plans";

/** Plan list sent with each question (the server answers from its own catalog copy). */
const PLAN_FACTS = CARE_PLANS.map((p) => ({
  name: p.name,
  annual_inr: p.annualInr,
  monthly_inr: p.monthlyInr ?? 0,
  summary: `${p.fit}. ${p.visitLabel}.`,
}));

/**
 * Website chat. Owner (1 Nov 2026): the assistant is "Kushi" — "Hi, I'm Kushi,
 * let's make your home safe together. How can I help?" — and it opens by itself
 * within 10 s on every screen size, on every visit; closing it only hides it for
 * the rest of that browser tab.
 * Step 1 is scripted: quick replies with links, an emergency answer that never
 * waits on anything, and a call-back request that lands in Ops → Enquiries
 * (kind "website-chat"). It opens by itself a few seconds after a page loads, on
 * laptops and phones, until the visitor closes it (remembered for the tab).
 */

const NAME = "Kushi";
/** Open the chat this long after the visitor arrived (navigation start, not page ready). */
const AUTO_OPEN_MS = 7000;
const CLOSED_KEY = "ks-chat-closed";

type Msg = { from: "bot" | "me"; text: string; links?: { label: string; href: string; external?: boolean }[] };
type Topic = "discovery" | "prices" | "ai" | "emergency" | "abroad" | "callback";

const EMERGENCY_WORDS = /\b(fall|fell|fallen|emergency|ambulance|hospital|unconscious|bleed|bleeding|chest pain|stroke|breath|urgent help)\b/i;

/** Closing the chat hides it for the rest of this tab only (owner: it should greet
 *  every visit). It used to stay closed for a week via localStorage, which is why the
 *  owner saw it "not opening" on a laptop after dismissing it once. */
let closedThisPageView = false;

/** Owner (1 Nov 2026, after testing): a close must not survive a refresh — the
 *  chat greets on every page load. So "closed" lives only in this module instance. */
function wasClosed(): boolean {
  return closedThisPageView;
}

function rememberClosed() {
  closedThisPageView = true;
  try {
    // Clear the flags older builds left behind, or returning visitors never see it.
    window.sessionStorage.removeItem(CLOSED_KEY);
    window.localStorage.removeItem(CLOSED_KEY);
  } catch {
    /* private mode — fine */
  }
}

export function SurendraChat() {
  const site = useSiteConfig();
  const [open, setOpen] = useState(false);
  // Phones: a small greeting next to the button instead of the full panel over the page.
  const [greet, setGreet] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([
    {
      from: "bot",
      text: `Hi, I'm ${NAME} from KushAlaya 👋 Let's make your parents' home safe together. How can I help you today?`,
    },
  ]);
  const [form, setForm] = useState(false);
  const [text, setText] = useState("");
  const [typing, setTyping] = useState(false);
  // Once the visitor scrolls past the first screen the launcher shrinks to the
  // round avatar, so it doesn't sit over right-hand content (tables, sidebars).
  const [compact, setCompact] = useState(false);
  // After the first close the launcher stays a round avatar.
  const [closedOnce, setClosedOnce] = useState(false);
  useEffect(() => {
    try {
      window.localStorage.removeItem(CLOSED_KEY);
      window.sessionStorage.removeItem(CLOSED_KEY);
    } catch {
      /* ignore */
    }
    if (wasClosed()) setClosedOnce(true);
    const onScroll = () => setCompact(window.scrollY > 320);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  const listRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  // Owner (2026-10-29): the chat opens by itself within 10 s of arriving — on every
  // screen size. Not again once the visitor has closed it, and never while they are
  // typing in a form on the page.
  useEffect(() => {
    if (wasClosed()) return;
    const t = window.setTimeout(() => {
      if (wasClosed()) return;
      const el = document.activeElement;
      const typing = el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement;
      if (typing) {
        setGreet(true); // a small nudge instead of covering the form
        return;
      }
      setOpen(true);
      setGreet(false);
    }, Math.max(0, AUTO_OPEN_MS - performance.now()));
    return () => window.clearTimeout(t);
  }, []);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [msgs, form]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeChat();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const wa = whatsAppHref(site, "Hi KushAlaya, I'd like to know about care for my parents.");

  function openChat() {
    setOpen(true);
    setGreet(false);
  }

  function closeChat() {
    setOpen(false);
    setGreet(false);
    setClosedOnce(true);
    rememberClosed();
  }

  function say(me: string, reply: Msg) {
    setMsgs((m) => [...m, { from: "me", text: me }, reply]);
  }

  function pick(topic: Topic, label: string) {
    setForm(false);
    if (topic === "callback") {
      setMsgs((m) => [...m, { from: "me", text: label }, { from: "bot", text: "Happy to call you. Leave your details:" }]);
      setForm(true);
      return;
    }
    say(label, ANSWERS(topic, site.phone, site.phone_tel, wa));
  }

  async function send(e: FormEvent) {
    e.preventDefault();
    const q = text.trim();
    if (!q || typing) return;
    setText("");
    if (EMERGENCY_WORDS.test(q)) {
      say(q, ANSWERS("emergency", site.phone, site.phone_tel, wa));
      return;
    }
    const history = msgs.slice(-6).map((m) => ({ from: m.from, text: m.text }));
    setMsgs((m) => [...m, { from: "me", text: q }]);
    setTyping(true);
    try {
      const res = await fetch(`${getApiUrl()}/api/v1/public/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: q, history, plans: PLAN_FACTS }),
      });
      if (!res.ok) throw new Error(String(res.status));
      const a = (await res.json()) as { reply: string; link?: string | null; link_label?: string | null; offer_callback?: boolean };
      setMsgs((m) => [
        ...m,
        { from: "bot", text: a.reply, links: a.link ? [{ label: a.link_label || "Open", href: a.link }] : undefined },
      ]);
      if (a.offer_callback) setForm(true);
    } catch {
      setMsgs((m) => [
        ...m,
        {
          from: "bot",
          text: "Sorry, I couldn't answer that just now. Leave your number and we'll call you, or message us on WhatsApp.",
          links: [{ label: "WhatsApp us", href: wa, external: true }],
        },
      ]);
      setForm(true);
    } finally {
      setTyping(false);
    }
  }

  return (
    <div className={compact || closedOnce ? "ks-chat is-compact" : "ks-chat"}>
      {open ? (
        <div className="ks-chat-panel" role="dialog" aria-label={`Chat with ${NAME}`} ref={panelRef}>
          <header className="ks-chat-head">
            <span className="ks-chat-avatar" aria-hidden="true">
              {NAME[0]}
            </span>
            <span className="ks-chat-who">
              <strong>{NAME}</strong>
              <small>KushAlaya assistant · a person calls you back</small>
            </span>
            <button type="button" className="ks-chat-x" onClick={closeChat} aria-label="Close chat">
              ✕
            </button>
          </header>

          <div className="ks-chat-body" ref={listRef} aria-live="polite">
            {msgs.map((m, i) => (
              <div key={i} className={`ks-chat-msg ks-chat-msg--${m.from}`}>
                <p>{m.text}</p>
                {m.links?.length ? (
                  <span className="ks-chat-links">
                    {m.links.map((l) => (
                      <a key={l.href + l.label} href={l.href} {...(l.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}>
                        {l.label}
                      </a>
                    ))}
                  </span>
                ) : null}
              </div>
            ))}
            {typing ? (
              <div className="ks-chat-msg ks-chat-msg--bot ks-chat-typing" aria-label="Typing">
                <p>
                  <span />
                  <span />
                  <span />
                </p>
              </div>
            ) : null}
            {form ? <CallbackForm onDone={(ref) => {
              setForm(false);
              setMsgs((m) => [...m, { from: "bot", text: `Thank you! ${CALLBACK_PROMISE}. Your reference is ${ref}.` }]);
            }} /> : null}
          </div>

          <div className="ks-chat-quick" role="group" aria-label="Quick questions">
            {QUICK.map((q) => (
              <button key={q.topic} type="button" onClick={() => pick(q.topic, q.label)}>
                {q.label}
              </button>
            ))}
          </div>

          <form className="ks-chat-input" onSubmit={send}>
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Type your question…"
              aria-label="Your message"
              maxLength={500}
            />
            <button type="submit" aria-label="Send">
              ➤
            </button>
          </form>
        </div>
      ) : null}

      {!open && greet ? (
        <div className="ks-chat-greet" role="status">
          <button type="button" className="ks-chat-greet-text" onClick={openChat}>
            Hi, I&apos;m {NAME} 👋 <strong>Let&apos;s make your home safe together.</strong>
          </button>
          <button type="button" className="ks-chat-greet-x" onClick={closeChat} aria-label="Hide">
            ✕
          </button>
        </div>
      ) : null}
      {!open ? (
        <button type="button" className="ks-chat-launch" onClick={openChat} aria-label={`Chat with ${NAME}`}>
          <span className="ks-chat-avatar" aria-hidden="true">
            {NAME[0]}
          </span>
          <span className="ks-chat-launch-text">Chat with {NAME}</span>
        </button>
      ) : null}
    </div>
  );
}

const QUICK: { topic: Topic; label: string }[] = [
  { topic: "discovery", label: "Book free KushCare Discovery" },
  { topic: "prices", label: "Plans & prices" },
  { topic: "ai", label: "Home safety check" },
  { topic: "abroad", label: "I live abroad" },
  { topic: "emergency", label: "Emergency help" },
  { topic: "callback", label: "Call me back" },
];

function ANSWERS(topic: Exclude<Topic, "callback">, phone: string, phoneTel: string, wa: string): Msg {
  switch (topic) {
    case "discovery":
      return {
        from: "bot",
        text: "KushCare Discovery is our home visit: we check the home room by room, talk with your parents, and give you a KushAlaya Safety Score with a clear plan. It is free, with no payment and no obligation. It takes a few minutes to book.",
        links: [{ label: "Book free KushCare Discovery", href: PARENT_CARE_CHECK_HREF }],
      };
    case "prices":
      return {
        from: "bot",
        text: `${PLAN_PRICE_LINE} Four plans: ${CARE_PLANS.map((p) => p.shortName).join(", ")}. You always see the price before we book anything.`,
        links: [{ label: "See all plans", href: "/packages" }],
      };
    case "ai":
      return {
        from: "bot",
        text: "Send us a photo of a room and our AI points out common risks — no grab bar, slippery floor, loose rugs — and shows the room with safety products fitted. A care manager checks every finding.",
        links: [{ label: "See how it works", href: "/safe-homes#ai" }],
      };
    case "abroad":
      return {
        from: "bot",
        text: "Most of our families live in another city or country. You get an update after every visit, a weekly summary and a monthly letter in the family app, and we call at a time that suits your time zone.",
        links: [
          { label: `Call from US/Canada ${US_PHONE.display}`, href: US_PHONE.tel },
          { label: "WhatsApp us", href: wa, external: true },
        ],
      };
    case "emergency":
      return {
        from: "bot",
        text: "If someone is hurt or unwell right now, call 112 (or 108 for an ambulance) first. Then call us and we will help.",
        links: [
          { label: "Call 112", href: "tel:112" },
          { label: `Call us ${phone}`, href: `tel:${phoneTel}` },
        ],
      };
  }
}

function CallbackForm({ onDone }: { onDone: (reference: string) => void }) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [city, setCity] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [trap, setTrap] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return setErr("Please add your name.");
    if (!phone.trim()) return setErr("Please add your phone number.");
    const pErr = phoneError(phone);
    if (pErr) return setErr(pErr);
    setErr("");
    setBusy(true);
    try {
      const res = await fetch(`${getApiUrl()}/api/v1/home-safety/enquiries`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          phone,
          area: city.trim() || null,
          notes: "Asked for a call back from the website chat.",
          kind: "website-chat",
          company: trap || null,
          landing_page: typeof window !== "undefined" ? window.location.pathname : null,
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body?.detail || "Could not send");
      onDone(body.reference || "—");
    } catch {
      setErr("Sorry, that didn't go through. Please call or WhatsApp us.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="ks-chat-form" onSubmit={submit}>
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" aria-label="Your name" maxLength={120} />
      <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Phone (with country code if abroad)" aria-label="Phone" inputMode="tel" maxLength={40} />
      <input value={city} onChange={(e) => setCity(e.target.value)} placeholder="Parents' city" aria-label="Parents' city" maxLength={80} />
      <input className="ks-chat-trap" tabIndex={-1} autoComplete="off" value={trap} onChange={(e) => setTrap(e.target.value)} aria-hidden="true" />
      {err ? <p className="ks-chat-err" role="alert">{err}</p> : null}
      <button type="submit" disabled={busy}>
        {busy ? "Sending…" : "Call me back"}
      </button>
      <small>
        By sending, you agree we may call you about care. <a href={CONTACT_HREF}>Other ways to reach us</a>
      </small>
    </form>
  );
}
