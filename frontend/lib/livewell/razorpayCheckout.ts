/**
 * Razorpay Standard Checkout loader.
 *
 * The script is fetched on first use rather than in the app shell, so families
 * who never top up do not pay for it — and the family portal is a PWA that is
 * often opened on a phone over mobile data.
 *
 * The publishable key comes from the create-order response rather than a
 * NEXT_PUBLIC_* build variable, so the key and the order can never come from
 * two different Razorpay accounts. The key secret stays on the server.
 */

const CHECKOUT_SRC = "https://checkout.razorpay.com/v1/checkout.js";

type RazorpayHandlerResponse = {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
};

type RazorpayFailure = {
  error?: {
    description?: string;
    reason?: string;
    step?: string;
  };
};

type RazorpayInstance = {
  open: () => void;
  on: (event: string, handler: (payload: RazorpayFailure) => void) => void;
};

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => RazorpayInstance;
  }
}

let loader: Promise<void> | null = null;

function loadCheckoutScript(): Promise<void> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("Checkout is only available in the browser"));
  }
  if (window.Razorpay) return Promise.resolve();
  if (loader) return loader;

  loader = new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      `script[src="${CHECKOUT_SRC}"]`,
    );
    const script = existing ?? document.createElement("script");
    script.addEventListener("load", () => resolve());
    script.addEventListener("error", () => {
      // Let the next attempt retry rather than caching the failure forever.
      loader = null;
      reject(new Error("Could not load the payment window. Check your connection."));
    });
    if (!existing) {
      script.src = CHECKOUT_SRC;
      script.async = true;
      document.body.appendChild(script);
    }
  });
  return loader;
}

export type OpenCheckoutArgs = {
  keyId: string;
  orderId: string;
  amountMinor: number;
  currency: string;
  name: string;
  description?: string;
  prefill?: { name?: string; email?: string; contact?: string };
};

export type CheckoutOutcome =
  | { status: "paid"; result: RazorpayHandlerResponse }
  | { status: "dismissed" }
  | { status: "failed"; message: string };

/** Opens the payment modal and resolves once the family finishes or backs out. */
export async function openRazorpayCheckout(
  args: OpenCheckoutArgs,
): Promise<CheckoutOutcome> {
  await loadCheckoutScript();
  const Razorpay = window.Razorpay;
  if (!Razorpay) {
    throw new Error("Payment window is unavailable");
  }

  return new Promise<CheckoutOutcome>((resolve) => {
    // Razorpay can fire both `payment.failed` and the dismiss handler for one
    // attempt; settle on whichever arrives first.
    let settled = false;
    const settle = (outcome: CheckoutOutcome) => {
      if (settled) return;
      settled = true;
      resolve(outcome);
    };

    const checkout = new Razorpay({
      key: args.keyId,
      order_id: args.orderId,
      amount: args.amountMinor,
      currency: args.currency,
      name: args.name,
      description: args.description,
      prefill: args.prefill,
      handler: (result: RazorpayHandlerResponse) => settle({ status: "paid", result }),
      modal: {
        ondismiss: () => settle({ status: "dismissed" }),
      },
    });

    checkout.on("payment.failed", (payload: RazorpayFailure) =>
      settle({
        status: "failed",
        message:
          payload?.error?.description ||
          payload?.error?.reason ||
          "The payment did not go through.",
      }),
    );

    checkout.open();
  });
}
