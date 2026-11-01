/**
 * K2: family contact preferences (#88) and "Call me" / "Ask about…" (#91).
 * Mirrors backend/app/livewell/family_contacts.py and family_questions.py.
 */

import { api } from "@/lib/api";
import { zonePlace } from "@/lib/ist";
import { familyApi } from "@/lib/livewell/familyApi";

export type ContactChannel = "whatsapp" | "sms" | "call" | "email";
export type ContactLevel = "everything" | "important" | "emergencies";

export const CHANNEL_OPTIONS: { value: ContactChannel; label: string }[] = [
  { value: "whatsapp", label: "WhatsApp" },
  { value: "sms", label: "SMS" },
  { value: "call", label: "Phone call" },
  { value: "email", label: "Email" },
];

export const LEVEL_OPTIONS: { value: ContactLevel; label: string; hint: string }[] = [
  { value: "everything", label: "Everything", hint: "Visits, reports, replies and all alerts" },
  {
    value: "important",
    label: "Important only",
    hint: "Safety concerns, missed visits, orders, worrying changes at a visit and emergencies",
  },
  { value: "emergencies", label: "Emergencies only", hint: "SOS and emergencies" },
];

/** Where Kushalaya families usually live. Times in emails follow this. */
export const TIMEZONE_OPTIONS: { value: string; label: string }[] = [
  { value: "Asia/Kolkata", label: "India (IST)" },
  { value: "America/New_York", label: "US East (New York)" },
  { value: "America/Chicago", label: "US Central (Chicago)" },
  { value: "America/Denver", label: "US Mountain (Denver)" },
  { value: "America/Los_Angeles", label: "US West (Los Angeles)" },
  { value: "America/Toronto", label: "Canada (Toronto)" },
  { value: "Europe/London", label: "UK (London)" },
  { value: "Europe/Berlin", label: "Europe (Berlin / Paris)" },
  { value: "Asia/Dubai", label: "UAE (Dubai)" },
  { value: "Asia/Riyadh", label: "Saudi Arabia / Kuwait / Qatar" },
  { value: "Asia/Singapore", label: "Singapore / Malaysia" },
  { value: "Australia/Sydney", label: "Australia (Sydney)" },
  { value: "Australia/Perth", label: "Australia (Perth)" },
  { value: "Pacific/Auckland", label: "New Zealand" },
];

export function timezoneLabel(tz: string): string {
  return TIMEZONE_OPTIONS.find((o) => o.value === tz)?.label ?? `${zonePlace(tz)} time`;
}

export type FamilyContactRow = {
  key: string;
  user_id: number | null;
  name: string;
  email: string;
  relationship: string | null;
  is_primary: boolean;
  has_login: boolean;
  phone: string;
  channel: ContactChannel;
  timezone: string;
  level: ContactLevel;
};

export type FamilyQuestion = {
  id: number;
  elder_id: number;
  elder_name?: string;
  kind: "call_me" | "ask";
  kind_label: string;
  body: string;
  call_window: string;
  visit_ref: string | null;
  visit_label: string;
  flag_key: string | null;
  status: "open" | "done";
  asker_name: string;
  /** Staff views only: the asker's phone, for calling back. */
  asker_phone?: string;
  is_mine: boolean;
  reply: string;
  replied_by_name: string;
  replied_at: string | null;
  done_at: string | null;
  done_by_name: string;
  created_at: string | null;
};

export type AskInput = {
  kind: "call_me" | "ask";
  body?: string;
  window?: "asap" | "morning" | "afternoon" | "evening";
  day?: "today" | "tomorrow";
  visit_ref?: string;
  visit_label?: string;
  flag_key?: string;
};

// Family
export const fetchFamilyQuestions = () => familyApi<FamilyQuestion[]>("/questions");
export const askCareTeam = (data: AskInput) =>
  familyApi<FamilyQuestion>("/questions", { method: "POST", body: JSON.stringify(data) });

// Staff
const base = (elderId: number) => `/api/v1/home-safety/clients/${elderId}`;
export const fetchClientContacts = (elderId: number) => api<FamilyContactRow[]>(`${base(elderId)}/family-contacts`);
export const saveClientContact = (
  elderId: number,
  data: { key: string } & Partial<Pick<FamilyContactRow, "name" | "phone" | "channel" | "timezone" | "level">>,
) => api<FamilyContactRow>(`${base(elderId)}/family-contacts`, { method: "PUT", body: JSON.stringify(data) });
export const fetchClientQuestions = (elderId: number) => api<FamilyQuestion[]>(`${base(elderId)}/questions`);
export const replyClientQuestion = (elderId: number, id: number, body: string, done = true) =>
  api<FamilyQuestion>(`${base(elderId)}/questions/${id}/reply`, {
    method: "POST",
    body: JSON.stringify({ body, done }),
  });
export const markClientQuestionDone = (elderId: number, id: number) =>
  api<FamilyQuestion>(`${base(elderId)}/questions/${id}/done`, { method: "POST" });
