"use client";

import { FamilyLink as Link } from "@/components/livewell/family/FamilyLink";
import { istInputToISO, istInputValue } from "@/lib/ist";
import { familyDate, familyTime } from "@/lib/livewell/familyTime";
import { useFamilyTimezone } from "@/lib/family-zone";
import { useCallback, useEffect, useRef, useState } from "react";
import { FamilyShell } from "@/components/livewell/family/FamilyShell";
import {
  cancelFamilyServiceRequest,
  createFamilyServiceRequest,
  fetchFamilyElders,
  fetchFamilyServiceCatalog,
  fetchFamilyServiceRequests,
  fetchFamilyWallet,
  payFamilyServiceRequest,
  type FamilyServiceRequest,
  type FamilyServiceType,
  type FamilyWalletBalance,
} from "@/lib/livewell/familyApi";
import { productImageSrc, type FamilyQuote } from "@/lib/commerce";
import { FamilyConfirmSheet } from "@/components/livewell/family/FamilyConfirmSheet";
import {
  acceptFamilyQuote,
  declineFamilyQuote,
  fetchFamilyProducts,
  fetchFamilyQuotes,
  inr,
  topUpWallet,
  type FamilyProduct,
} from "@/lib/family-money";
import { familyPriceLabel, matchesSearch, shelfFor, shelvesWithItems, withAlignedRecommendations } from "@/lib/family-catalog";
import { FamilyProductCard, FamilyProductSheet, FamilyProductThumb } from "@/components/livewell/family/FamilyProductCard";
import { publicSafetyScoreName } from "@/lib/public-brand";
import { findingNeed } from "@/lib/livewell/familyFindings";
import { plainWords } from "@/lib/livewell/familyWords";
import { REQUEST_STEPS, requestStep } from "@/lib/livewell/familyStatus";

/** Plain words: "Waiting to be booked", "Booked for Thu 9 Oct", "Done", "Cancelled". */
function statusWords(r: FamilyServiceRequest): string {
  if (r.status === "requested") return "Waiting to be booked";
  if (r.status === "confirmed")
    return r.preferred_at ? `Booked for ${familyDate(r.preferred_at)}` : "Booked";
  if (r.status === "done") return "Done";
  if (r.status === "declined") return "Not possible — the care team will call you";
  if (r.status === "cancelled") return "Cancelled";
  return r.status.replace(/_/g, " ");
}

const OPEN_STATUSES = new Set(["requested", "confirmed"]);

/** Quoted prices are GST-inclusive (backend gst_invoices.taxable_from_inclusive, 18%). */
function gstSplit(totalPaise: number): { taxable: number; gst: number } {
  const denom = 11800;
  const taxable = Math.floor((totalPaise * 10000 * 2 + denom) / (denom * 2));
  return { taxable, gst: totalPaise - taxable };
}

type Group = "service" | "product" | "assessment";

const GROUPS: { id: Group; title: string; hint: string }[] = [
  { id: "service", title: "A service", hint: "Care visit, physiotherapy, recovery help" },
  { id: "product", title: "A product", hint: "Grab bars, shower chair, SOS wearable and more" },
  { id: "assessment", title: "An assessment visit", hint: "Home safety check with a score and report" },
];

export default function FamilyServicesPage() {
  const tz = useFamilyTimezone();
  const [catalog, setCatalog] = useState<FamilyServiceType[]>([]);
  const [requests, setRequests] = useState<FamilyServiceRequest[]>([]);
  const [wallet, setWallet] = useState<FamilyWalletBalance | null>(null);
  const [group, setGroup] = useState<Group>("service");
  const [serviceType, setServiceType] = useState("");
  const [pick, setPick] = useState<FamilyProduct | null>(null);
  const [viewing, setViewing] = useState<FamilyProduct | null>(null);
  const [query, setQuery] = useState("");
  // Opens on "Recommended" when there is anything recommended (set once products load).
  const [shelf, setShelf] = useState("");
  const [productsState, setProductsState] = useState<"loading" | "ok" | "failed">("loading");
  const [seniorName, setSeniorName] = useState("");
  const formRef = useRef<HTMLElement | null>(null);
  const catalogRef = useRef<HTMLElement | null>(null);
  const hashHandled = useRef(false);
  const [preferredAt, setPreferredAt] = useState("");
  const [notes, setNotes] = useState("");
  const [busyId, setBusyId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [quotes, setQuotes] = useState<FamilyQuote[]>([]);
  const [products, setProducts] = useState<FamilyProduct[]>([]);
  const [declining, setDeclining] = useState<number | null>(null);
  const [declineNote, setDeclineNote] = useState("");
  const [confirmReq, setConfirmReq] = useState<FamilyServiceRequest | null>(null);

  const load = useCallback(async () => {
    try {
      const [types, rows, balance] = await Promise.all([
        fetchFamilyServiceCatalog(),
        fetchFamilyServiceRequests(),
        fetchFamilyWallet(),
      ]);
      setCatalog(types);
      setRequests(rows);
      setWallet(balance);
      // "Request a visit →" on Home links to #book: open the form on "Care visit".
      const booking = !hashHandled.current && typeof window !== "undefined" && window.location.hash === "#book";
      hashHandled.current = true;
      const careVisit = types.find((t) => t.id === "care_visit") ?? types.find((t) => t.group === "service" && /care visit/i.test(t.label));
      setServiceType(
        (current) =>
          current || (booking && careVisit?.id) || types.find((t) => t.group === "service")?.id || "",
      );
      if (booking) {
        setGroup("service");
        requestAnimationFrame(() => formRef.current?.scrollIntoView({ block: "start" }));
      }
      // Quotes and product pictures are extras: the page still works without them.
      fetchFamilyQuotes().then(setQuotes).catch(() => setQuotes([]));
      fetchFamilyProducts()
        .then((raw) => {
          // Product ↔ finding pairs re-checked (lib/family-catalog), same as Score & plan.
          const rows = withAlignedRecommendations(raw);
          setProducts(rows);
          setProductsState("ok");
          setShelf((cur) => cur || (rows.some((p) => p.recommended) ? "recommended" : "all"));
        })
        .catch(() => setProductsState("failed"));
      fetchFamilyElders()
        .then((list) => {
          const active = list.elders.find((e) => e.id === list.active_elder_id);
          setSeniorName((active?.name || list.senior_name || "").split(" ")[0]);
        })
        .catch(() => undefined);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load services");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function submit() {
    setError("");
    setNotice("");
    const type = pick
      ? pick.kind === "service"
        ? "catalog_service"
        : "product"
      : group === "service"
        ? serviceType
        : group;
    if (!type) {
      setError("Pick a service");
      return;
    }
    if (type === "product" && !pick) {
      setError("Pick a product from the list above");
      return;
    }
    setSubmitting(true);
    try {
      await createFamilyServiceRequest({
        service_type: type,
        preferred_at: preferredAt ? istInputToISO(preferredAt) : null,
        notes: notes.trim(),
        product_name: pick?.name,
        product_id: pick?.id,
      });
      setPick(null);
      setNotes("");
      setPreferredAt("");
      setNotice("Request sent. Your care team will schedule it and let you know the date and time.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not send the request");
    } finally {
      setSubmitting(false);
    }
  }

  async function approveAndPay(request: FamilyServiceRequest) {
    setConfirmReq(null);
    setError("");
    setNotice("");
    setBusyId(request.id);
    try {
      await payFamilyServiceRequest(request.id);
      setNotice(`Paid ${request.quoted_amount_display} for ${request.service_label}.`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Payment failed");
    } finally {
      setBusyId("");
    }
  }

  async function payQuote(q: FamilyQuote) {
    setError("");
    setNotice("");
    setBusyId(`q${q.id}`);
    try {
      let res = await acceptFamilyQuote(q.id);
      if (!res.paid) {
        // Not enough in the wallet: top up the difference with the usual payment, then pay.
        const top = await topUpWallet(res.topup_paise, `Top-up to pay quote #${q.id}`, q.id);
        if (!top.ok) {
          setError(`${top.message} You need ${inr(res.shortfall_paise)} more to pay this quote.`);
          await load();
          return;
        }
        // The server usually pays it already when the top-up lands; this call is the fallback.
        res = await acceptFamilyQuote(q.id);
      }
      if (res.paid) {
        setNotice(`Paid ${inr(q.total_paise)}. We'll call you to book a time.`);
      } else {
        setError(res.message);
      }
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Payment failed");
    } finally {
      setBusyId("");
    }
  }

  async function notNow(q: FamilyQuote) {
    setError("");
    setNotice("");
    setBusyId(`q${q.id}`);
    try {
      await declineFamilyQuote(q.id, declineNote.trim());
      setDeclining(null);
      setDeclineNote("");
      setNotice("Thanks — we've told the care team. Nothing has been charged.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't send your answer");
    } finally {
      setBusyId("");
    }
  }

  async function cancel(request: FamilyServiceRequest) {
    setError("");
    setNotice("");
    setBusyId(request.id);
    try {
      await cancelFamilyServiceRequest(request.id);
      setNotice(
        request.payment_status === "paid"
          ? "Cancelled — refunded to your KushAlaya wallet."
          : "Request cancelled.",
      );
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not cancel");
    } finally {
      setBusyId("");
    }
  }

  // A cancelled / declined / finished request has nothing left to approve.
  const awaitingPayment = requests.filter(
    (r) => r.payment_status === "awaiting_approval" && OPEN_STATUSES.has(r.status),
  );
  const recommended = products.filter((p) => p.recommended);
  const shelves = shelvesWithItems(products);
  const searching = query.trim().length > 0;
  const shown = products.filter(
    (p) =>
      matchesSearch(p, query) &&
      (shelf === "all" || (shelf === "recommended" ? p.recommended : shelfFor(p.category) === shelf)),
  );
  // "All" with no search: one heading per shelf, so a long list stays easy to scan.
  // Recommended items live under the Recommended chip only, so they are not listed twice.
  const byShelf = shelves.map((s) => ({ ...s, items: products.filter((p) => shelfFor(p.category) === s.id) }));
  const byShelfRest = byShelf
    .map((g) => ({ ...g, items: g.items.filter((p) => !p.recommended) }))
    .filter((g) => g.items.length);

  function requestItem(p: FamilyProduct) {
    setViewing(null);
    setPick(p);
    setGroup(p.kind === "service" ? "service" : "product");
    setError("");
    setNotice("");
    formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function pickGroup(g: Group) {
    setGroup(g);
    if (pick && (g === "assessment" || (g === "service") !== (pick.kind === "service"))) setPick(null);
  }

  function backToList() {
    catalogRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  const openQuotes = quotes.filter((q) => q.needs_action);
  const pastQuotes = quotes.filter((q) => !q.needs_action);

  return (
    <FamilyShell title="Requests" subtitle="Ask for a service, a product or an assessment visit">
      {error && <p className="error-text">{error}</p>}
      {notice && <p className="muted">{notice}</p>}

      {openQuotes.length > 0 && (
        <section className="card home-safety-section fh-quotes" id="quotes">
          <h2>Needs you: {openQuotes.length === 1 ? "a quote to approve" : `${openQuotes.length} quotes to approve`}</h2>
          {openQuotes.map((q) => (
            <QuoteCard key={q.id} q={q}>
              <div className="fh-quote-actions">
                <button type="button" disabled={busyId === `q${q.id}`} onClick={() => void payQuote(q)}>
                  {busyId === `q${q.id}`
                    ? "Paying…"
                    : wallet && wallet.balance_minor < q.total_paise
                      ? `Top up ${inr(q.total_paise - wallet.balance_minor)} and pay`
                      : `Approve & pay ${inr(q.total_paise)}`}
                </button>
                <button
                  type="button"
                  className="secondary"
                  disabled={busyId === `q${q.id}`}
                  onClick={() => setDeclining(declining === q.id ? null : q.id)}
                >
                  Not now
                </button>
              </div>
              {wallet ? (
                <small className="muted">
                  Paid from your wallet (balance {inr(wallet.balance_minor)})
                  {wallet.balance_minor < q.total_paise ? " — we'll ask you to top up the difference first." : "."}
                </small>
              ) : null}
              {declining === q.id ? (
                <div className="fh-quote-decline">
                  <label>
                    <span className="muted">Tell us why (optional)</span>
                    <input value={declineNote} onChange={(e) => setDeclineNote(e.target.value)} placeholder="e.g. after Diwali" />
                  </label>
                  <button type="button" className="secondary" disabled={busyId === `q${q.id}`} onClick={() => void notNow(q)}>
                    Send “Not now”
                  </button>
                </div>
              ) : null}
            </QuoteCard>
          ))}
        </section>
      )}


      {awaitingPayment.length > 0 && (
        <section className="card home-safety-section">
          <h2>Waiting for your approval</h2>
          <ul className="home-safety-family-more-list">
            {awaitingPayment.map((request) => {
              const affordable =
                wallet != null && wallet.balance_minor >= (request.quoted_amount_minor ?? 0);
              return (
                <li key={request.id}>
                  <div className="card home-safety-family-more-card">
                    <strong>
                      {request.service_label} — {request.quoted_amount_display}
                    </strong>
                    {request.staff_note && <span className="muted">{request.staff_note}</span>}
                    {affordable ? (
                      <button
                        type="button"
                        disabled={busyId === request.id}
                        onClick={() => setConfirmReq(request)}
                        style={{ marginTop: "0.5rem" }}
                      >
                        {busyId === request.id ? "Paying…" : "Approve & pay from wallet"}
                      </button>
                    ) : (
                      <Link
                        href="/kushalaya/family/wallet"
                        className="home-safety-family-inline-link"
                      >
                        Not enough balance — add money →
                      </Link>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <section className="card home-safety-section">
        <h2>Your requests</h2>
        {pastQuotes.length > 0 ? (
          <div className="fh-quotes-past">
            {pastQuotes.map((q) => (
              <QuoteCard key={q.id} q={q} />
            ))}
          </div>
        ) : null}
        {requests.length === 0 && pastQuotes.length === 0 ? (
          <p className="muted">No requests yet.</p>
        ) : (
          <ul className="home-safety-family-more-list">
            {requests.map((request) => (
              <li key={request.id}>
                <div className="card home-safety-family-more-card">
                  <strong>
                    {plainWords(request.service_label)}
                    {request.quoted_amount_display ? ` — ${request.quoted_amount_display}` : ""}
                  </strong>
                  <span className="muted">
                    {statusWords(request)}
                    {request.preferred_at
                      ? ` · ${familyTime(request.preferred_at, tz)}`
                      : request.status === "requested"
                        ? " · Time: any"
                        : ""}
                    {request.created_at ? ` · Sent ${familyDate(request.created_at)}` : ""}
                    {request.payment_status === "paid" ? " · Paid" : ""}
                    {request.payment_status === "refunded" ? " · Refunded" : ""}
                  </span>
                  <RequestTracker step={requestStep(request)} />
                  {request.notes && <span className="muted">“{request.notes}”</span>}
                  {request.staff_note && (
                    <span className="muted">Care team: {request.staff_note}</span>
                  )}
                  {OPEN_STATUSES.has(request.status) && (
                    <button
                      type="button"
                      className="secondary"
                      disabled={busyId === request.id}
                      onClick={() => void cancel(request)}
                      style={{ marginTop: "0.5rem" }}
                    >
                      {busyId === request.id ? "Working…" : "Cancel"}
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <Link href="/kushalaya/family/wallet" className="home-safety-family-p0-card">
        <span className="muted">Wallet balance</span>
        {/* Whole rupees when there are no paise ("₹200", not "₹200.00"), as on Wallet. */}
        <strong>{wallet ? inr(wallet.balance_minor) : "—"}</strong>
        <span className="muted">Tap to add money</span>
      </Link>

      <section className="card home-safety-section fh-anchor" id="book" ref={formRef}>
        <h2>Book a visit or ask for something</h2>
        <div className="fh-req-groups" role="radiogroup" aria-label="Request type">
          {GROUPS.map((g) => (
            <button
              key={g.id}
              type="button"
              role="radio"
              aria-checked={group === g.id}
              className={group === g.id ? "fh-req-group is-on" : "fh-req-group"}
              onClick={() => pickGroup(g.id)}
            >
              <strong>{g.title}</strong>
              <span>{g.hint}</span>
            </button>
          ))}
        </div>

        {pick ? (
          <div className="fh-cat-pick">
            <FamilyProductThumb src={pick.image_url} size={56} />
            <div className="fh-cat-text">
              <span className="muted">{pick.kind === "service" ? "Service" : "Product"}</span>
              <strong>{pick.name}</strong>
              <span className="fh-prod-price">{familyPriceLabel(pick)}</span>
            </div>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setPick(null);
                backToList();
              }}
            >
              Change
            </button>
          </div>
        ) : null}

        {group === "service" && !pick ? (
          <label>
            <span className="muted">Which service? Or pick any service from the list below.</span>
            <select value={serviceType} onChange={(e) => setServiceType(e.target.value)}>
              {catalog
                .filter((type) => type.group === "service")
                .map((type) => (
                  <option key={type.id} value={type.id}>
                    {type.label}
                  </option>
                ))}
            </select>
          </label>
        ) : null}

        {group === "product" && !pick ? (
          <div className="fh-cat-empty">
            <p>Choose a product from the list below, then tap Request.</p>
            <button type="button" className="secondary" onClick={backToList}>
              See the list
            </button>
          </div>
        ) : null}

        {group === "assessment" ? (
          <p className="muted">
            A trained caregiver visits, checks every room and gives you a {publicSafetyScoreName()} with a
            clear report.
          </p>
        ) : null}

        <label>
          <span className="muted">Preferred time (IST)</span>
          <input
            type="datetime-local"
            value={preferredAt}
            min={istInputValue(60 * 60 * 1000)}
            onChange={(e) => setPreferredAt(e.target.value)}
          />
          {preferredAt ? (
            <small className="muted">That is {familyTime(istInputToISO(preferredAt), tz)}</small>
          ) : (
            <small className="muted">Type the time in India. We show your own time beside it.</small>
          )}
        </label>
        <label>
          <span className="muted">Anything we should know?</span>
          <textarea
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Optional details for the care team"
          />
        </label>
        <button
          type="button"
          disabled={submitting}
          onClick={() => void submit()}
          style={{ marginTop: "0.75rem" }}
        >
          {submitting ? "Sending…" : "Send request"}
        </button>
      </section>

      <section className="card home-safety-section fh-cat" id="catalog" ref={catalogRef}>
        <h2>What would you like?</h2>
        <p className="muted">
          {products.length
            ? `Everything we offer — ${products.filter((p) => p.kind === "product").length} products and ${products.filter((p) => p.kind === "service").length} services. Find one and tap Request.`
            : "Products and services you can ask for."}
        </p>

        {productsState === "failed" ? (
          <div className="fh-cat-empty">
            <p>We couldn&apos;t load the list just now. You can still write what you need in the request above.</p>
            <button type="button" className="secondary" onClick={() => void load()}>
              Try again
            </button>
          </div>
        ) : null}
        {productsState === "loading" ? <p className="muted">Loading the list…</p> : null}

        {products.length ? (
          <>
            <label className="fh-cat-search">
              <input
                type="search"
                aria-label="Search products and services"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search — e.g. grab bar, nurse, BP monitor"
                autoComplete="off"
              />
            </label>
            <div className="fh-cat-chips" role="group" aria-label="Show">
              {[
                ...(recommended.length ? [{ id: "recommended", label: "Recommended", n: recommended.length }] : []),
                { id: "all", label: "All", n: products.length },
                ...byShelf.map((s) => ({ id: s.id, label: s.label, n: s.items.length })),
              ].map((c) => (
                <button
                  key={c.id}
                  type="button"
                  aria-pressed={shelf === c.id}
                  className={shelf === c.id ? "fh-cat-chip is-on" : "fh-cat-chip"}
                  onClick={() => setShelf(c.id)}
                >
                  {c.label} <small>{c.n}</small>
                </button>
              ))}
            </div>


            {shown.length === 0 ? (
              <div className="fh-cat-empty">
                <p>
                  Nothing matches{searching ? ` “${query.trim()}”` : " here"}. Try another word, or describe what you
                  need in the request above — your care team will find it.
                </p>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    setQuery("");
                    setShelf("all");
                  }}
                >
                  Show everything
                </button>
              </div>
            ) : shelf === "recommended" && !searching ? (
              <div className="fh-cat-group fh-cat-rec">
                <h3>Recommended for {seniorName || "your senior"}</h3>
                <p className="muted">From the latest home safety check.</p>
                <ul className="fh-cat-list">
                  {recommended.map((p) => (
                    <FamilyProductCard
                      key={p.id}
                      p={p}
                      onOpen={setViewing}
                      onRequest={requestItem}
                      note={p.reasons.length ? `Helps with: ${plainWords(findingNeed(p.reasons[0]))}` : undefined}
                    />
                  ))}
                </ul>
              </div>
            ) : shelf === "all" && !searching ? (
              <>
                {recommended.length ? (
                  <p className="muted">
                    The {recommended.length} recommended {recommended.length === 1 ? "item is" : "items are"} under
                    Recommended.
                  </p>
                ) : null}
                {byShelfRest.map((g) => (
                <div key={g.id} className="fh-cat-group">
                  <h3>{g.label}</h3>
                  <ul className="fh-cat-list">
                    {g.items.map((p) => (
                      <FamilyProductCard key={p.id} p={p} onOpen={setViewing} onRequest={requestItem} />
                    ))}
                  </ul>
                </div>
                ))}
              </>
            ) : (
              <div className="fh-cat-group">
                <p className="muted" aria-live="polite">
                  {shown.length} {shown.length === 1 ? "item" : "items"}
                </p>
                <ul className="fh-cat-list">
                  {shown.map((p) => (
                    <FamilyProductCard key={p.id} p={p} onOpen={setViewing} onRequest={requestItem} />
                  ))}
                </ul>
              </div>
            )}
          </>
        ) : null}
      </section>

      <FamilyConfirmSheet
        open={!!confirmReq}
        title="Approve and pay?"
        confirmLabel={confirmReq ? `Confirm — pay ${inr(confirmReq.quoted_amount_minor ?? 0)}` : "Confirm"}
        onConfirm={() => confirmReq && void approveAndPay(confirmReq)}
        onCancel={() => setConfirmReq(null)}
        busy={!!confirmReq && busyId === confirmReq.id}
        extra={
          confirmReq ? (
            <button
              type="button"
              className="secondary"
              onClick={() => {
                const r = confirmReq;
                setConfirmReq(null);
                void cancel(r);
              }}
            >
              Decline this price
            </button>
          ) : null
        }
      >
        {confirmReq ? (() => {
          const total = confirmReq.quoted_amount_minor ?? 0;
          const { taxable, gst } = gstSplit(total);
          const balance = wallet?.balance_minor ?? 0;
          return (
            <>
              <p>{confirmReq.service_label}</p>
              <dl className="fh-sheet-rows">
                <div>
                  <dt>Price</dt>
                  <dd>{inr(taxable)}</dd>
                </div>
                <div>
                  <dt>GST (18%)</dt>
                  <dd>{inr(gst)}</dd>
                </div>
                <div className="is-total">
                  <dt>Total</dt>
                  <dd>{inr(total)}</dd>
                </div>
                <div>
                  <dt>Wallet now</dt>
                  <dd>{inr(balance)}</dd>
                </div>
                <div>
                  <dt>Wallet after</dt>
                  <dd>{inr(balance - total)}</dd>
                </div>
              </dl>
            </>
          );
        })() : null}
      </FamilyConfirmSheet>
      <FamilyProductSheet p={viewing} onClose={() => setViewing(null)} onRequest={requestItem} />
    </FamilyShell>
  );
}

/** One quote: lines with quantities, GST and the total including GST. */
function QuoteCard({ q, children }: { q: FamilyQuote; children?: React.ReactNode }) {
  return (
    <div className={`card fh-quote is-${q.status}`}>
      <div className="fh-quote-head">
        <strong>Quote #{q.id}</strong>
        <span className="fh-quote-status">{q.status_label}</span>
      </div>
      <ul className="fh-quote-lines">
        {q.lines.map((l, i) => (
          <li key={i}>
            <FamilyProductThumb src={l.image_url} size={44} />
            <span>
              {l.qty} × {l.name}
            </span>
            <span>{inr(l.line_paise)}</span>
          </li>
        ))}
      </ul>
      <dl className="fh-quote-sum">
        {q.discount_paise ? (
          <>
            <dt>Discount</dt>
            <dd>−{inr(q.discount_paise)}</dd>
          </>
        ) : null}
        <dt>GST {q.gst_bp / 100}%</dt>
        <dd>{inr(q.gst_paise)}</dd>
        <dt>Total (incl. GST)</dt>
        <dd>
          <strong>{inr(q.total_paise)}</strong>
        </dd>
      </dl>
      {q.paid_at ? <small className="muted">Paid {familyDate(q.paid_at)} from your wallet</small> : null}
      {children}
    </div>
  );
}

/** requested → quoted → booked → done, from the request's status. */
function RequestTracker({ step }: { step: number | null }) {
  if (step == null) return null;
  return (
    <ol className="fh-tracker" aria-label={`Progress: ${REQUEST_STEPS[step]}`}>
      {REQUEST_STEPS.map((label, i) => (
        <li key={label} className={i < step ? "is-done" : i === step ? "is-now" : ""} aria-current={i === step ? "step" : undefined}>
          {label}
        </li>
      ))}
    </ol>
  );
}
