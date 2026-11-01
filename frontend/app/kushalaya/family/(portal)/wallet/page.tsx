"use client";

import { useCallback, useEffect, useState } from "react";
import { FamilyShell } from "@/components/livewell/family/FamilyShell";
import { WalletReceipts } from "@/components/livewell/family/WalletReceipts";
import { FamilyInvoices } from "@/components/livewell/family/FamilyInvoices";
import { fetchFamilyWallet, type FamilyWalletBalance } from "@/lib/livewell/familyApi";
import { topUpWallet } from "@/lib/family-money";
import { inr } from "@/lib/business";

const QUICK_AMOUNTS_RUPEES = [500, 1000, 2500, 5000];

export default function FamilyWalletPage() {
  const [wallet, setWallet] = useState<FamilyWalletBalance | null>(null);
  const [amountRupees, setAmountRupees] = useState("1000");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  const load = useCallback(async () => {
    try {
      setWallet(await fetchFamilyWallet());
      setReloadKey((k) => k + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load your wallet");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function addMoney() {
    setError("");
    setNotice("");
    const rupees = Number(amountRupees);
    if (!Number.isFinite(rupees) || rupees <= 0) {
      setError("Enter an amount");
      return;
    }
    // Rupees → paise, rounded so "100.005" never becomes a fractional paisa.
    const amountMinor = Math.round(rupees * 100);
    setBusy(true);
    try {
      const res = await topUpWallet(amountMinor);
      if (res.ok) setNotice(res.message);
      else setError(res.message);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the top-up");
    } finally {
      setBusy(false);
    }
  }

  return (
    <FamilyShell title="Wallet" subtitle="Prepaid balance for care services, and every payment with its receipt">
      {error && <p className="error-text">{error}</p>}
      {notice && <p className="muted">{notice}</p>}

      <section className="card home-safety-section">
        <span className="muted">Available balance</span>
        <p style={{ fontSize: "2rem", fontWeight: 700, margin: "0.25rem 0 0" }}>
          {/* Same ₹ format as the history below ("₹200", not "₹200.00"). */}
          {wallet ? inr(wallet.balance_minor) : "—"}
        </p>
        {wallet?.status === "frozen" && (
          <p className="error-text">This wallet is on hold — please contact the care team.</p>
        )}
      </section>

      <section className="card home-safety-section">
        <h2>Add money</h2>
        <div
          style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", margin: "0.75rem 0" }}
        >
          {QUICK_AMOUNTS_RUPEES.map((amount) => (
            <button
              key={amount}
              type="button"
              className={`secondary fh-amount-chip${Number(amountRupees) === amount ? " is-on" : ""}`}
              aria-pressed={Number(amountRupees) === amount}
              onClick={() => setAmountRupees(String(amount))}
            >
              ₹{amount.toLocaleString("en-IN")}
            </button>
          ))}
        </div>
        <label>
          <span className="muted">Amount (₹)</span>
          <input
            type="number"
            min={1}
            step="1"
            inputMode="numeric"
            value={amountRupees}
            onChange={(e) => setAmountRupees(e.target.value)}
          />
        </label>
        <button
          type="button"
          disabled={busy || wallet?.status === "frozen"}
          onClick={() => void addMoney()}
          style={{ marginTop: "0.75rem" }}
        >
          {busy ? "Please wait…" : "Add money"}
        </button>
      </section>

      <FamilyInvoices reloadKey={reloadKey} />
      <WalletReceipts reloadKey={reloadKey} />
    </FamilyShell>
  );
}
