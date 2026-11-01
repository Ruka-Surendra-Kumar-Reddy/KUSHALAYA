/** Family money helpers: quotes (Approve & pay / Not now), wallet top-up, My details. */

import { getStoredAuth } from "@/lib/api";
import type { FamilyQuote, FamilyQuoteAccept } from "@/lib/commerce";
import type { ContactChannel, ContactLevel } from "@/lib/family-contacts";
import {
  familyApi,
  settleFamilyWalletRecharge,
  verifyFamilyWalletRecharge,
  type FamilyServiceRequest,
  type FamilyWalletRecharge,
} from "@/lib/livewell/familyApi";
import { openRazorpayCheckout } from "@/lib/livewell/razorpayCheckout";
import { publicBrandName } from "@/lib/public-brand";

export const fetchFamilyQuotes = () => familyApi<FamilyQuote[]>("/quotes");

/** The server works out the amount from the order; nothing about money is sent from here. */
export const acceptFamilyQuote = (id: number) =>
  familyApi<FamilyQuoteAccept>(`/quotes/${id}/accept`, { method: "POST", body: "{}" });

export const declineFamilyQuote = (id: number, note: string) =>
  familyApi<FamilyQuote>(`/quotes/${id}/decline`, { method: "POST", body: JSON.stringify({ note }) });

/** One on-sale catalog item as a family sees it: selling price before GST (0 = price on request), never cost. */
export type FamilyProduct = {
  id: number;
  product_code: string;
  name: string;
  category: string;
  description: string;
  kind: "product" | "service";
  /** "per visit", "per day"… for services; "" for one-off items. */
  unit: string;
  /** One line on what the price covers. */
  included: string;
  image_url: string | null;
  price_paise: number;
  /** price_paise + 18% GST; 0 when ops has not priced it yet. */
  price_with_gst_paise: number;
  /** Suggested by the latest home safety assessment. */
  recommended: boolean;
  reasons: string[];
};
export const fetchFamilyProducts = () => familyApi<FamilyProduct[]>("/products");

export type TopUpResult = { ok: boolean; message: string };

/** Add money to the wallet with the existing Razorpay top-up (stub gateway settles at once). */
export async function topUpWallet(
  amountMinor: number,
  description = "Wallet top-up",
  /** For "Approve & pay": the server pays this quote as soon as the top-up lands. */
  quoteOrderId?: number,
): Promise<TopUpResult> {
  const recharge = await familyApi<FamilyWalletRecharge>("/wallet/recharge", {
    method: "POST",
    body: JSON.stringify({ amount_minor: amountMinor, ...(quoteOrderId ? { quote_order_id: quoteOrderId } : {}) }),
  });
  if (recharge.provider === "stub") {
    await settleFamilyWalletRecharge(recharge.transaction_id);
    return { ok: true, message: `Added ${inr(recharge.amount_minor)} to the wallet.` };
  }
  const outcome = await openRazorpayCheckout({
    keyId: recharge.public_key,
    orderId: recharge.order_id,
    amountMinor: recharge.amount_minor,
    currency: recharge.currency,
    name: publicBrandName(),
    description,
    prefill: { email: getStoredAuth()?.email || undefined },
  });
  if (outcome.status === "dismissed") return { ok: false, message: "Payment cancelled. Nothing has been charged." };
  if (outcome.status === "failed") return { ok: false, message: outcome.message };
  await verifyFamilyWalletRecharge({
    razorpay_order_id: outcome.result.razorpay_order_id,
    razorpay_payment_id: outcome.result.razorpay_payment_id,
    razorpay_signature: outcome.result.razorpay_signature,
  });
  return { ok: true, message: "Payment successful — your balance is updated." };
}

export const inr = (paise: number) =>
  `₹${(paise / 100).toLocaleString("en-IN", { maximumFractionDigits: paise % 100 ? 2 : 0, minimumFractionDigits: paise % 100 ? 2 : 0 })}`;

export type FamilyMyDetails = {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  channel: ContactChannel;
  timezone: string;
  level: ContactLevel;
  elder_id: number;
  elder_name: string;
  emergency_contact_name: string;
  emergency_contact_phone: string;
  health: { conditions: string; allergies: string; mobility: string };
};

export const fetchMyDetails = () => familyApi<FamilyMyDetails>("/my-details");

export const saveMyDetails = (
  data: Partial<
    Pick<
      FamilyMyDetails,
      | "first_name"
      | "last_name"
      | "phone"
      | "channel"
      | "timezone"
      | "level"
      | "emergency_contact_name"
      | "emergency_contact_phone"
    >
  >,
) => familyApi<FamilyMyDetails>("/my-details", { method: "PUT", body: JSON.stringify(data) });

export const requestDetailsChange = (data: {
  conditions?: string;
  allergies?: string;
  medicines?: string;
  mobility?: string;
  note?: string;
}) => familyApi<FamilyServiceRequest>("/details-change-request", { method: "POST", body: JSON.stringify(data) });
