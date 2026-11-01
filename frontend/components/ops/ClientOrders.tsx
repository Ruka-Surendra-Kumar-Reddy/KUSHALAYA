"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createOrder,
  listOrders,
  listProducts,
  MANAGER_DISCOUNT_LIMIT,
  quoteOrder,
  rupees,
  scheduleInstall,
  setOrderStatus,
  type Order,
  type Product,
  type Quote,
} from "@/lib/commerce";
import { isClash } from "@/lib/jobs";
import { api } from "@/lib/api";
import Link from "next/link";
import { aiPreviewHref } from "@/lib/aiPreview";

type Caregiver = { id: number; first_name: string; last_name: string };
type Booking = { orderId: number; at: string; caregiverId: string; note: string; moving: boolean };

/** Tomorrow 10:00 in the browser's time, as a datetime-local value. */
function defaultWhen(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T10:00`;
}

type Suggestions = {
  assessment_id: string | null;
  assessment_status: string | null;
  score: number | null;
  items: {
    product_id: number;
    name: string;
    price_paise: number;
    priced: boolean;
    priority: "high" | "medium";
    reasons: { label: string; severity: string }[];
  }[];
  photos: { document_id: number; room_type: string; caption: string }[];
};
import "./commerce.css";
import { OpsModal } from "./OpsModal";
import { can, isAdmin as isAdminUser } from "@/lib/roles";
import { publicSafetyScoreName } from "@/lib/public-brand";

const STATUS: Record<Order["status"], string> = {
  pending_approval: "Waiting for admin approval",
  approved: "Approved",
  quoted: "Quote sent — waiting for the family",
  family_accepted: "Family accepted and paid",
  scheduled: "Installation scheduled",
  completed: "Completed",
  cancelled: "Cancelled",
};

/** Orders for one client: build a basket, apply a discount or coupon, see the price with GST. */
export function ClientOrders({ elderId }: { elderId: number }) {
  const isAdmin = isAdminUser();
  const canEdit = can("edit");
  const [products, setProducts] = useState<Product[]>([]);
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [qty, setQty] = useState<Record<number, number>>({});
  const [discountPct, setDiscountPct] = useState("");
  const [reason, setReason] = useState("");
  const [coupon, setCoupon] = useState("");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [quoteError, setQuoteError] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [sugg, setSugg] = useState<Suggestions | null>(null);
  const [caregivers, setCaregivers] = useState<Caregiver[]>([]);
  const [booking, setBooking] = useState<Booking | null>(null);
  const [bookError, setBookError] = useState("");
  const [rowBusy, setRowBusy] = useState<number | null>(null);
  const [ordersError, setOrdersError] = useState("");
  // Phone: the product picker stays folded behind "New order" until asked for.
  const [picking, setPicking] = useState(false);
  const [find, setFind] = useState("");
  const [hazards, setHazards] = useState<
    { id: string; note: string; product_id: number | null; product_name: string; status: string; spotted_at: string; order_id: number | null }[]
  >([]);

  const loadHazards = useCallback(
    () => api<typeof hazards>(`/api/v1/team/clients/${elderId}/hazards`).then(setHazards).catch(() => undefined),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [elderId],
  );

  useEffect(() => {
    void loadHazards();
  }, [loadHazards]);

  async function orderForHazard(h: (typeof hazards)[number]) {
    if (!h.product_id) {
      setMessage("Pick the products in New order below, then mark the hazard as ordered.");
      return;
    }
    const prod = products.find((p) => p.id === h.product_id);
    if (prod && !prod.price_paise) {
      setMessage(`${prod.name} has no price yet — set its price under Products before ordering it.`);
      return;
    }
    try {
      const o = await createOrder({ elder_id: elderId, lines: [{ product_id: h.product_id, qty: 1 }], note: `Hazard: ${h.note}` });
      await api(`/api/v1/team/clients/${elderId}/hazards/${h.id}`, {
        method: "POST",
        body: JSON.stringify({ status: "ordered", order_id: o.id }),
      });
      setMessage(`Order #${o.id} created for ${h.product_name}. Schedule the installation below.`);
      await load();
      await loadHazards();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not create the order");
    }
  }

  async function dismissHazard(id: string) {
    await api(`/api/v1/team/clients/${elderId}/hazards/${id}`, { method: "POST", body: JSON.stringify({ status: "dismissed" }) });
    await loadHazards();
  }

  useEffect(() => {
    api<Suggestions>(`/api/v1/suggestions?elder_id=${elderId}`).then(setSugg).catch(() => undefined);
  }, [elderId]);

  const load = useCallback(
    () =>
      listOrders({ elder_id: elderId }).then((o) => {
        setOrders(o);
        setOrdersError("");
      }),
    [elderId],
  );

  useEffect(() => {
    listProducts().then(setProducts).catch(() => undefined);
    load().catch((e) => {
      setOrders([]);
      setOrdersError(e instanceof Error ? e.message : "Could not load orders");
    });
    api<Caregiver[]>("/api/v1/team/caregivers").then(setCaregivers).catch(() => undefined);
  }, [load]);

  // Unpriced products can never be ordered ("Price on request").
  const pricedIds = new Set(products.filter((p) => p.price_paise).map((p) => p.id));
  const lines = Object.entries(qty)
    .filter(([id, n]) => n > 0 && (pricedIds.size === 0 || pricedIds.has(Number(id))))
    .map(([id, n]) => ({ product_id: Number(id), qty: n }));
  const basket = {
    lines,
    discount_bp: discountPct ? Math.round(Number(discountPct) * 100) : 0,
    coupon_code: coupon.trim() || undefined,
  };
  const basketKey = JSON.stringify(basket);

  useEffect(() => {
    if (!lines.length) {
      setQuote(null);
      setQuoteError("");
      return;
    }
    const t = window.setTimeout(() => {
      quoteOrder(JSON.parse(basketKey))
        .then((q) => {
          setQuote(q);
          setQuoteError("");
        })
        .catch((e) => {
          setQuote(null);
          setQuoteError(e instanceof Error ? e.message : "Can't price this order");
        });
    }, 300);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [basketKey]);

  // Your own discount above 10% needs an admin, with or without a coupon.
  const needsApproval = !isAdmin && Number(discountPct || 0) > MANAGER_DISCOUNT_LIMIT;

  async function place() {
    setBusy(true);
    setMessage("");
    try {
      const o = await createOrder({ elder_id: elderId, ...basket, discount_reason: reason });
      setMessage(
        o.status === "pending_approval"
          ? `Order saved. The discount is above ${MANAGER_DISCOUNT_LIMIT}%, so an admin needs to approve it.`
          : "Order saved.",
      );
      setQty({});
      setDiscountPct("");
      setReason("");
      setCoupon("");
      setPicking(false);
      await load();
    } catch (e) {
      setQuoteError(e instanceof Error ? e.message : "Could not save the order");
    } finally {
      setBusy(false);
    }
  }

  async function status(o: Order, s: string, reason?: string) {
    await setOrderStatus(o.id, s, reason);
    await load();
  }

  /** Status change from an order row, with the server's message shown on failure. */
  async function act(o: Order, s: string, done: string, reason?: string) {
    setRowBusy(o.id);
    setMessage("");
    try {
      await status(o, s, reason);
      setMessage(done);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Couldn't update the order");
    } finally {
      setRowBusy(null);
    }
  }

  function reject(o: Order) {
    const reason = window.prompt(`Reject order #${o.id}? Say why (the manager sees this).`, "Discount too high");
    if (reason === null) return;
    void act(o, "cancelled", `Order #${o.id} rejected.`, reason);
  }

  function cancel(o: Order) {
    const paid = (o.paid_paise || 0) > 0;
    const msg =
      `Cancel order #${o.id}?` +
      (o.status === "scheduled" ? " The installation visit is cancelled too and the family is told." : "") +
      (paid ? ` ${rupees(o.paid_paise || 0)} goes back to the family's wallet.` : "");
    if (!window.confirm(msg)) return;
    void act(o, "cancelled", paid ? `Order #${o.id} cancelled and refunded to the wallet.` : `Order #${o.id} cancelled.`);
  }

  async function sendQuote(o: Order) {
    if (!window.confirm(`Send this quote (${rupees(o.total_paise)} incl. GST) to the family to approve and pay?`)) return;
    try {
      await status(o, "quoted");
      setMessage("Quote sent. The family sees it under Requests and can approve and pay from the wallet.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Couldn't send the quote");
    }
  }

  function openBooking(o: Order) {
    setBookError("");
    setBooking({ orderId: o.id, at: defaultWhen(), caregiverId: "", note: "", moving: o.status === "scheduled" });
  }

  async function book(force = false): Promise<void> {
    if (!booking) return;
    const at = new Date(booking.at);
    if (!booking.at || Number.isNaN(at.getTime())) {
      setBookError("Pick a date and time");
      return;
    }
    setBookError("");
    setRowBusy(booking.orderId);
    try {
      const out = await scheduleInstall(booking.orderId, {
        scheduled_at: at.toISOString(),
        ...(booking.caregiverId ? { caregiver_id: Number(booking.caregiverId) } : {}),
        note: booking.note || undefined,
        force,
      });
      const who = out.job.caregiver_name ? ` with ${out.job.caregiver_name}` : " — no caregiver yet";
      const when = at.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
      setMessage(`${booking.moving ? "Installation moved" : "Installation booked"} for ${when}${who}. The family has been told.`);
      setBooking(null);
      await load();
    } catch (e) {
      if (isClash(e) && window.confirm(e.message)) return book(true);
      setBookError(e instanceof Error ? e.message : "Couldn't book the installation");
    } finally {
      setRowBusy(null);
    }
  }

  return (
    <>
      {hazards.some((h) => h.status === "spotted" || h.status === "ordered" || h.status === "fixed") ? (
        <section className="card cm-hazards">
          <h2>Spotted on visits</h2>
          <ul>
            {hazards
              .filter((h) => h.status !== "dismissed")
              .map((h) => (
                <li key={h.id} className={`is-${h.status}`}>
                  <span>
                    <strong>{h.note || h.product_name || "Home safety hazard"}</strong>
                    <small>
                      {new Date(h.spotted_at).toLocaleDateString()} {h.product_name ? `· fix: ${h.product_name}` : ""}
                    </small>
                  </span>
                  <span className="cm-hz-status">
                    {h.status === "spotted" ? "Spotted" : h.status === "ordered" ? `Ordered #${h.order_id}` : "Fixed ✓"}
                  </span>
                  {canEdit && h.status === "spotted" ? (
                    <span className="cm-row-actions">
                      <button type="button" onClick={() => void orderForHazard(h)}>
                        Create order
                      </button>
                      <button type="button" className="secondary" onClick={() => void dismissHazard(h.id)}>
                        Dismiss
                      </button>
                    </span>
                  ) : (
                    <span />
                  )}
                </li>
              ))}
          </ul>
        </section>
      ) : null}

      {canEdit && sugg && sugg.items.length ? (
        <section className="card cm-sugg">
          <h2>
            Suggested from the last assessment
            {sugg.score != null ? <small> · {publicSafetyScoreName()} {sugg.score}/100</small> : null}
          </h2>
          <ul>
            {sugg.items.map((i) => (
              <li key={i.product_id} className={i.priority === "high" ? "is-high" : ""}>
                <span>
                  <strong>{i.name}</strong>
                  <small>{i.reasons.map((r) => r.label).join(" · ")}</small>
                </span>
                <span>{i.priced ? `${rupees(i.price_paise)} + GST` : "Price on request"}</span>
                {i.priced ? (
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => {
                      setQty((q) => ({ ...q, [i.product_id]: Math.max(1, q[i.product_id] ?? 0) }));
                      setPicking(true);
                    }}
                  >
                    {qty[i.product_id] ? "Added" : "Add to order"}
                  </button>
                ) : (
                  <small className="cm-unpriced-note">
                    Can&apos;t be ordered until it has a price
                    {isAdminUser() ? (
                      <>
                        {" "}
                        — <Link href="/kushalaya/catalog">set it under Products</Link>
                      </>
                    ) : " — ask the owner to price it"}
                  </small>
                )}
              </li>
            ))}
          </ul>
          {sugg.photos.length ? (
            <div className="cm-ba">
              <strong>Before / after</strong>
              <span>Show the family their room with these products added.</span>
              {sugg.photos.map((ph) => (
                <Link
                  key={ph.document_id}
                  className="secondary"
                  href={aiPreviewHref({ assessment: sugg.assessment_id, elder: elderId, photo: ph.document_id })}
                >
                  {`Make picture · ${ph.room_type || "room"}`}
                </Link>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      {canEdit ? (
      <section className="card cm-order">
        <h2>New order</h2>
        <button type="button" onClick={() => setPicking(true)}>
          {lines.length ? `+ New order (${lines.length} in basket)` : "+ New order"}
        </button>
        <OpsModal open={picking} title="New order" onClose={() => setPicking(false)} wide>
        <div className="cm-order-body">
        {products.some((p) => !p.price_paise) ? (
          <p className="muted cm-unpriced">
            {(() => {
              const n = products.filter((p) => !p.price_paise).length;
              return `${n} product${n === 1 ? "" : "s"} without a price ${n === 1 ? "is" : "are"} not shown — they are "Price on request" and can't be ordered until a price is set under Products.`;
            })()}
          </p>
        ) : null}
        {/* Search and add, then a short cart: the full grid of ~150 products was 4,500 px tall. */}
        <div className="cm-addprod">
          <input
            type="search"
            className="cm-addprod-input"
            placeholder="Add a product — type to search"
            aria-label="Add a product"
            value={find}
            onChange={(e) => setFind(e.target.value)}
          />
          {find.trim() ? (
            <ul className="cm-addprod-results" role="listbox" aria-label="Matching products">
              {(() => {
                const t = find.trim().toLowerCase();
                const hits = products.filter((p) => p.price_paise && !qty[p.id] && p.name.toLowerCase().includes(t)).slice(0, 8);
                return hits.length ? (
                  hits.map((p) => (
                    <li key={p.id}>
                      <button
                        type="button"
                        role="option"
                        aria-selected={false}
                        onClick={() => {
                          setQty({ ...qty, [p.id]: 1 });
                          setFind("");
                        }}
                      >
                        <strong>{p.name}</strong>
                        <small>{`${rupees(p.price_paise)} + GST`}</small>
                      </button>
                    </li>
                  ))
                ) : (
                  <li className="muted cm-addprod-none">No priced product matches “{find.trim()}”.</li>
                );
              })()}
            </ul>
          ) : null}
        </div>
        {lines.length ? (
          <ul className="cm-cart" aria-label="Products in this order">
            {products
              .filter((p) => qty[p.id])
              .map((p) => (
                <li key={p.id}>
                  <span>
                    <strong>{p.name}</strong>
                    <small>{`${rupees(p.price_paise)} + GST each`}</small>
                  </span>
                  <input
                    type="number"
                    min={0}
                    max={99}
                    value={qty[p.id] ?? 0}
                    onChange={(e) => setQty({ ...qty, [p.id]: Math.max(0, Number(e.target.value || 0)) })}
                    aria-label={`${p.name} quantity`}
                  />
                  <button
                    type="button"
                    className="cm-cart-x"
                    aria-label={`Remove ${p.name}`}
                    onClick={() => setQty({ ...qty, [p.id]: 0 })}
                  >
                    ×
                  </button>
                </li>
              ))}
          </ul>
        ) : (
          <p className="muted cm-cart-empty">No products yet. Search above to add one.</p>
        )}

        <div className="cm-discounts">
          <label>
            Discount (%)
            <input
              type="number"
              min={0}
              max={100}
              step="0.5"
              value={discountPct}
              onChange={(e) => setDiscountPct(e.target.value)}
              placeholder={isAdmin ? "0" : `Up to ${MANAGER_DISCOUNT_LIMIT}% without approval`}
            />
          </label>
          <label>
            Reason
            <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Second product" />
          </label>
          <label>
            Coupon
            <input value={coupon} onChange={(e) => setCoupon(e.target.value.toUpperCase())} placeholder="DIWALI10" />
          </label>
        </div>

        {quoteError ? <p className="cm-error">{quoteError}</p> : null}
        {quote ? (
          <dl className="cm-quote">
            <div>
              <dt>Price before GST</dt>
              <dd>{rupees(quote.subtotal_paise)}</dd>
            </div>
            {quote.discount_paise ? (
              <div>
                <dt>Discount{quote.coupon_code ? ` (${quote.coupon_code})` : ""}</dt>
                <dd>− {rupees(quote.discount_paise)}</dd>
              </div>
            ) : null}
            <div>
              <dt>GST 18%</dt>
              <dd>{rupees(quote.gst_paise)}</dd>
            </div>
            <div className="is-total">
              <dt>Total</dt>
              <dd>{rupees(quote.total_paise)}</dd>
            </div>
            {isAdmin && quote.margin_paise != null ? (
              <div className="is-margin">
                <dt>Our margin · staff only</dt>
                <dd>{rupees(quote.margin_paise)}</dd>
              </div>
            ) : null}
          </dl>
        ) : null}
        <button type="button" disabled={!quote || busy} onClick={() => void place()}>
          {busy ? "Saving…" : needsApproval ? "Send for approval" : "Save order"}
        </button>
        </div>
        </OpsModal>
      </section>
      ) : null}

      <section className="card cm-orders-card">
        <h2>Orders</h2>
        {message ? <p className="cm-ok">{message}</p> : null}
        {orders === null ? (
          <p className="muted">Loading…</p>
        ) : ordersError ? (
          <p className="cm-error" role="alert">
            {ordersError}{" "}
            <button type="button" className="secondary" onClick={() => void load().catch((e) => setOrdersError(e instanceof Error ? e.message : "Could not load orders"))}>
              Try again
            </button>
          </p>
        ) : orders.length === 0 ? (
          <p className="muted">No orders yet.</p>
        ) : (
          <ul className="cm-orders">
            {orders.map((o) => (
              <li key={o.id} className={`is-${o.status}`}>
                <div>
                  <strong>
                    #{o.id} · {rupees(o.total_paise)}
                  </strong>
                  <span className="cm-status">{STATUS[o.status]}</span>
                </div>
                <p>{o.lines.map((l) => `${l.qty} × ${l.name}`).join(", ")}</p>
                <small>
                  {o.discount_paise
                    ? `Discount ${rupees(o.discount_paise)} (${(o.discount_bp / 100).toFixed(1)}%)${
                        o.coupon_code ? ` · coupon ${o.coupon_code}` : ""
                      }${o.discount_reason ? ` · ${o.discount_reason}` : ""} · `
                    : ""}
                  GST {rupees(o.gst_paise)}
                  {isAdmin && o.margin_paise != null ? ` · our margin ${rupees(o.margin_paise)}` : ""}
                  {o.paid_paise ? ` · paid ${rupees(o.paid_paise)} from wallet` : ""}
                  {o.family_note ? ` · family said: “${o.family_note}”` : ""}
                </small>
                {canEdit ? (
                <div className="cm-row-actions">
                  {o.status === "pending_approval" && isAdmin ? (
                    <>
                      <button type="button" disabled={rowBusy === o.id} onClick={() => void act(o, "approved", `Order #${o.id} approved.`)}>
                        Approve discount
                      </button>
                      <button type="button" className="secondary" disabled={rowBusy === o.id} onClick={() => reject(o)}>
                        Reject
                      </button>
                    </>
                  ) : null}
                  {o.status === "approved" ? (
                    <button type="button" onClick={() => void sendQuote(o)}>
                      Send quote to family
                    </button>
                  ) : null}
                  {o.status === "approved" || o.status === "family_accepted" ? (
                    <button
                      type="button"
                      className={o.status === "approved" ? "secondary" : undefined}
                      onClick={() => openBooking(o)}
                    >
                      Schedule installation
                    </button>
                  ) : null}
                  {o.status === "scheduled" ? (
                    <button type="button" className="secondary" onClick={() => openBooking(o)}>
                      Reschedule
                    </button>
                  ) : null}
                  {(o.status === "pending_approval" && !isAdmin) ||
                  o.status === "approved" ||
                  o.status === "quoted" ||
                  o.status === "family_accepted" ||
                  o.status === "scheduled" ? (
                    <button type="button" className="secondary" disabled={rowBusy === o.id} onClick={() => cancel(o)}>
                      Cancel order
                    </button>
                  ) : null}
                </div>
                ) : null}
                {booking?.orderId === o.id ? (
                  <div className="cm-book">
                    <strong className="cm-book-wide">{booking.moving ? "Move the installation" : "Book the installation"}</strong>
                    <label>
                      Date and time
                      <input
                        type="datetime-local"
                        value={booking.at}
                        onChange={(e) => setBooking({ ...booking, at: e.target.value })}
                      />
                    </label>
                    <label>
                      Caregiver
                      <select
                        value={booking.caregiverId}
                        onChange={(e) => setBooking({ ...booking, caregiverId: e.target.value })}
                      >
                        <option value="">{booking.moving ? "Keep the current caregiver" : "Choose later"}</option>
                        {caregivers.map((c) => (
                          <option key={c.id} value={c.id}>
                            {`${c.first_name} ${c.last_name}`.trim()}
                          </option>
                        ))}
                      </select>
                    </label>
                    {!booking.moving ? (
                      <label className="cm-book-wide">
                        Note for the caregiver
                        <input
                          value={booking.note}
                          onChange={(e) => setBooking({ ...booking, note: e.target.value })}
                          placeholder="e.g. Bring the drill; family prefers mornings"
                        />
                      </label>
                    ) : null}
                    {bookError ? <p className="cm-error cm-book-wide">{bookError}</p> : null}
                    <div className="cm-book-actions">
                      <button type="button" className="secondary" onClick={() => setBooking(null)}>
                        Close
                      </button>
                      <button type="button" disabled={rowBusy === o.id} onClick={() => void book()}>
                        {rowBusy === o.id ? "Booking…" : booking.moving ? "Move installation" : "Book installation"}
                      </button>
                    </div>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
