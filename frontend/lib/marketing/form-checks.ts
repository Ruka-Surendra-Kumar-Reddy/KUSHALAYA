/**
 * Client-side checks for the public enquiry forms. They mirror the server
 * (backend/app/livewell/public_enquiry_service.py normalise_phone / _pincode
 * and pydantic EmailStr) so a visitor sees a friendly message before sending.
 * Each returns null when the value is fine or blank.
 */

export const PHONE_ERROR =
  "Please enter a 10-digit Indian mobile number, or an international number starting with + and the country code.";
export const EMAIL_ERROR = "Please check the email address (for example name@gmail.com).";
export const PINCODE_ERROR = "Please enter a 6-digit PIN code (for example 560001).";

export function phoneError(raw: string): string | null {
  const text = raw.trim();
  if (!text) return null;
  let compact = text.replace(/[\s\-().]/g, "");
  if (/^(?:\+?91|0)?[6-9]\d{9}$/.test(compact)) return null;
  if (compact.startsWith("00")) compact = "+" + compact.slice(2);
  if (/^\+[1-9]\d{7,14}$/.test(compact) && !compact.startsWith("+91")) return null;
  return PHONE_ERROR;
}

export function emailError(raw: string): string | null {
  const text = raw.trim();
  if (!text) return null;
  return /^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/.test(text) ? null : EMAIL_ERROR;
}

export function pincodeError(raw: string): string | null {
  const compact = raw.replace(/\s/g, "");
  if (!compact) return null;
  return /^[1-8]\d{5}$/.test(compact) ? null : PINCODE_ERROR;
}

/** FastAPI/pydantic 422 detail → one readable sentence. */
export function apiErrorMessage(detail: unknown): string | null {
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] as { msg?: unknown };
    if (typeof first?.msg === "string") return first.msg.replace(/^Value error,\s*/i, "");
  }
  return null;
}
