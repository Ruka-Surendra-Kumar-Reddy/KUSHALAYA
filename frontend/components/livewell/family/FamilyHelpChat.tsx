"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { FamilyLink as Link } from "@/components/livewell/family/FamilyLink";
import { fetchFamilyMessages, sendFamilyMessage, type FamilyMessage } from "@/lib/livewell/familyApi";
import { teamReplies } from "@/lib/livewell/familyFeed";
import "./family-help-chat.css";
import { publicSafetyScoreName } from "@/lib/public-brand";
import { CARE_PLANS, PLAN_PRICE_LINE } from "@/lib/marketing/plans";

type Faq = { q: string; a: string; keys: string[] };

/** Fixed answers (owner: no AI). Anything else goes to the care team. */
const FAQS: Faq[] = [
  {
    q: "How do plans and prices work?",
    a: `Plans are priced by how many care-manager visits you get a year: ${CARE_PLANS.map((p) => `${p.shortName} ${p.visitsPerYear}`).join(", ")}. ${PLAN_PRICE_LINE} Monthly billing is available on every plan (it costs a little more than yearly). See Plans in the menu or ask the team.`,
    keys: ["plan", "price", "cost", "subscription", "pay as you go", "charges", "fee"],
  },
  {
    q: "What happens on a visit?",
    a: "A trained caregiver checks in at the home, does the work agreed (medicines check, walk, physio exercises…), and records a KushLife check. You get a notification when they're on the way, when they arrive and when the visit is done.",
    keys: ["visit", "caregiver", "arrive", "on the way"],
  },
  {
    q: "What is KushLife?",
    a: "KushLife is a quick check on every visit — safe, steady, settled and connected — scored against your parent's personal normal (50). Above 50 is better than usual. You can see the trend on Home.",
    keys: ["kushlife", "pulse", "trend", "wellbeing"],
  },
  {
    q: `What is the ${publicSafetyScoreName()}?`,
    a: `It comes from the home safety assessment: a caregiver checks every room and scores it out of 100. The report shows what to fix first, with recommended products. See ${publicSafetyScoreName()} in the menu.`,
    keys: ["independence", "score", "assessment", "report", "safety"],
  },
  {
    q: "How do I get a product installed?",
    a: "Open Requests → A product, pick it and send. Your care team confirms the price (GST included) and schedules the installation with you.",
    keys: ["product", "install", "grab bar", "rail", "chair", "mat"],
  },
  {
    q: "How does the SOS wearable work?",
    a: "Your parent wears a small band. Pressing it (or a fall) raises an SOS alert to the care team straight away, and you are told too. For a medical emergency always call 112 first.",
    keys: ["sos", "wearable", "band", "fall", "alarm"],
  },
  {
    q: "How do I pay?",
    a: "Add money to the Wallet and approve requests from it, or pay the invoice your care team sends. Receipts are under Receipts in the menu.",
    keys: ["pay", "payment", "wallet", "invoice", "receipt", "refund"],
  },
  {
    q: "Can I change or cancel a visit?",
    a: "Yes. Cancel an open request from Requests, or send the team a message here with the new date and time and they will reschedule it.",
    keys: ["change", "cancel", "reschedule", "date", "time"],
  },
];

type Line = { from: "bot" | "you" | "team"; text: string; at?: string; who?: string };


function match(text: string): Faq | null {
  const t = text.toLowerCase();
  let best: Faq | null = null;
  let hits = 0;
  for (const f of FAQS) {
    const n = f.keys.filter((k) => t.includes(k)).length;
    if (n > hits) {
      best = f;
      hits = n;
    }
  }
  return best;
}

/** Help chat in the family portal (opened from the header or the sidebar). */
/** Window event that opens / closes the help chat (sidebar button on desktop). */
export const FAMILY_HELP_TOGGLE = "fh-help-toggle";

export function FamilyHelpChat() {
  const [open, setOpen] = useState(false);
  const [lines, setLines] = useState<Line[]>([
    { from: "bot", text: "Hi! Ask me anything, or pick a question below. For an emergency call 112." },
  ]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [pending, setPending] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);

  // On desktop the opener lives in the sidebar's "Need help?" card (FamilyShell).
  useEffect(() => {
    const toggle = () => setOpen((v) => !v);
    window.addEventListener(FAMILY_HELP_TOGGLE, toggle);
    return () => window.removeEventListener(FAMILY_HELP_TOGGLE, toggle);
  }, []);

  useEffect(() => {
    if (!open) return;
    fetchFamilyMessages()
      .then((rows: FamilyMessage[]) => {
        const replies = teamReplies(rows);
        if (replies.length)
          setLines((l) => [
            ...l.filter((x) => x.from !== "team"),
            ...replies.map((m) => ({ from: "team" as const, text: m.body, at: m.created_at, who: m.sender_name })),
          ]);
      })
      .catch(() => undefined);
  }, [open]);

  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [lines, open]);

  async function toTeam(question: string) {
    setSending(true);
    try {
      await sendFamilyMessage(question);
      setLines((l) => [...l, { from: "bot", text: "Thanks — we've sent this to your care team. They will get back to you shortly, here and in Messages." }]);
    } catch {
      setLines((l) => [...l, { from: "bot", text: "Sorry, that didn't go through. Please try again from Messages." }]);
    } finally {
      setSending(false);
      setPending(null);
    }
  }

  function ask(question: string) {
    const q = question.trim();
    if (!q) return;
    setLines((l) => [...l, { from: "you", text: q }]);
    const f = match(q);
    if (f) {
      setLines((l) => [...l, { from: "bot", text: f.a }]);
      setPending(q);
    } else {
      void toTeam(q);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    ask(text);
    setText("");
  }

  return (
    <>
      {/* No floating button: the header "?" (phones) and the sidebar "? Ask us"
          (desktop) open this panel, so nothing sits over the page. */}
      {open ? (
        <section className="fhc" aria-label="Help chat">
          <header className="fhc-head">
            <strong>Help</strong>
            <span>Answers, requests and your care team</span>
            <button type="button" className="fhc-close" aria-label="Close help" onClick={() => setOpen(false)}>
              ×
            </button>
          </header>
          <div className="fhc-body">
            {lines.map((l, i) => (
              <p key={i} className={`fhc-line is-${l.from}`}>
                {l.from === "team" ? <small>{l.who?.trim() || "Care team"}</small> : null}
                {l.text}
              </p>
            ))}
            {pending ? (
              <div className="fhc-follow">
                <span>Did that answer it?</span>
                <button type="button" onClick={() => setPending(null)}>
                  Yes, thanks
                </button>
                <button type="button" disabled={sending} onClick={() => void toTeam(pending)}>
                  Ask the team
                </button>
              </div>
            ) : null}
            <div className="fhc-chips">
              {FAQS.slice(0, 5).map((f) => (
                <button key={f.q} type="button" onClick={() => ask(f.q)}>
                  {f.q}
                </button>
              ))}
            </div>
            <div className="fhc-actions">
              <Link href="/kushalaya/family/services">Request a service, product or assessment →</Link>
            </div>
            <div ref={end} />
          </div>
          <form className="fhc-form" onSubmit={onSubmit}>
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Type your question"
              aria-label="Your question"
            />
            <button type="submit" disabled={sending || !text.trim()}>
              Send
            </button>
          </form>
        </section>
      ) : null}
    </>
  );
}
