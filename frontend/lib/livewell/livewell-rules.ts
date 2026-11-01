/** LiveWell360 membership + ECM + risk helpers (mirrors backend rule_engine_defaults). */

import type { ResidentProfile } from "./resident-profile";

export type MembershipId =
  | "mbr_independent"
  | "mbr_assisted"
  | "mbr_premium"
  | "mbr_nri";

export type RiskBand = "excellent" | "good" | "moderate" | "high" | "critical";

export type CognitiveRisk = "none" | "mild" | "moderate" | "high" | null | undefined;

export function recommendMembership(opts: {
  independenceScore: number;
  livesAlone?: boolean;
  familyAbroad?: boolean;
  cognitiveRisk?: CognitiveRisk;
}): MembershipId {
  const {
    independenceScore: score,
    livesAlone = false,
    familyAbroad = false,
    cognitiveRisk = null,
  } = opts;
  const cog = normalizeCognitive(cognitiveRisk);

  if (familyAbroad) return "mbr_nri";
  if (livesAlone && cog !== "none") return "mbr_assisted";
  if (cog === "moderate" || cog === "high") return "mbr_assisted";
  if (score < 40) return "mbr_premium";
  if (score >= 75 && cog === "none") return "mbr_independent";
  if (score >= 60) return "mbr_assisted";
  return "mbr_premium";
}

export function ecmRecommended(opts: {
  independenceScore: number;
  livesAlone?: boolean;
  familyAbroad?: boolean;
  familyRequestsEcm?: boolean;
  cognitiveRisk?: CognitiveRisk;
}): boolean {
  const {
    independenceScore: score,
    livesAlone = false,
    familyAbroad = false,
    familyRequestsEcm = false,
    cognitiveRisk = null,
  } = opts;
  if (score < 60) return true;
  if (livesAlone && score < 75) return true;
  if (familyAbroad) return true;
  if (familyRequestsEcm) return true;
  if (normalizeCognitive(cognitiveRisk) !== "none") return true;
  return false;
}

const RISK_BAND_ORDER: Record<RiskBand, number> = {
  excellent: 0,
  good: 1,
  moderate: 2,
  high: 3,
  critical: 4,
};

/**
 * Risk band for a score. `criticalUnsafe` caps the band at "high" — a critical
 * item rated unsafe never reads as Excellent/Good/Moderate (backend
 * risk_band_for_score does the same).
 */
export function riskBandForScore(
  score: number,
  opts: { criticalUnsafe?: boolean } = {},
): {
  band: RiskBand;
  label: string;
  escalation: string;
  capped?: boolean;
} {
  const raw = rawRiskBandForScore(score);
  if (opts.criticalUnsafe && RISK_BAND_ORDER[raw.band] < RISK_BAND_ORDER.high) {
    return { ...rawRiskBandForScore(59), capped: true };
  }
  return raw;
}

function rawRiskBandForScore(score: number): {
  band: RiskBand;
  label: string;
  escalation: string;
} {
  if (score >= 90) {
    return { band: "excellent", label: "Fully independent", escalation: "none" };
  }
  if (score >= 75) {
    return {
      band: "good",
      label: "Minor improvements recommended",
      escalation: "low",
    };
  }
  if (score >= 60) {
    return {
      band: "moderate",
      label: "Several improvements recommended",
      escalation: "medium",
    };
  }
  if (score >= 40) {
    return {
      band: "high",
      label: "Comprehensive intervention recommended",
      escalation: "high",
    };
  }
  return {
    band: "critical",
    label: "Immediate safety, healthcare, and care coordination required",
    escalation: "critical",
  };
}

export const MEMBERSHIP_LABELS: Record<MembershipId, string> = {
  mbr_independent: "Independent Living",
  mbr_assisted: "Assisted Living at Home",
  mbr_premium: "Premium Care",
  mbr_nri: "NRI Family Peace of Mind",
};

export function normalizeCognitive(
  value: CognitiveRisk | boolean | string | null | undefined,
): "none" | "mild" | "moderate" | "high" {
  if (value == null) return "none";
  if (typeof value === "boolean") return value ? "mild" : "none";
  const v = String(value).trim().toLowerCase();
  if (!v || v === "none" || v === "no" || v === "false" || v === "0") return "none";
  if (v === "high" || v === "severe" || v === "critical") return "high";
  if (v === "moderate" || v === "med" || v === "medium") return "moderate";
  return "mild";
}

const COGNITIVE_CONDITION_TERMS = ["dementia", "alzheimer", "parkinson", "stroke"];

/** Derive a coarse cognitive risk signal from resident profile medical conditions. */
export function cognitiveRiskFromConditions(conditions: string[] | undefined): CognitiveRisk {
  const list = (conditions || []).map((c) => String(c).toLowerCase());
  if (list.some((c) => COGNITIVE_CONDITION_TERMS.some((t) => c.includes(t)))) return "mild";
  return "none";
}

/**
 * Single cognitive-risk helper (mirrored by backend scoring.cognitive_risk_from_payload).
 * An explicit profile flag (cognitiveRisk / mildDementia / dementia) wins; otherwise
 * the medical-conditions list.
 */
export function cognitiveRiskFromProfile(
  profile: ResidentProfile | null | undefined,
): "none" | "mild" | "moderate" | "high" {
  const p = (profile ?? {}) as ResidentProfile & Record<string, unknown>;
  const explicit = p.cognitiveRisk ?? p.mildDementia ?? p.dementia;
  if (explicit != null && String(explicit).trim() !== "") {
    return normalizeCognitive(explicit as CognitiveRisk | boolean | string);
  }
  return normalizeCognitive(cognitiveRiskFromConditions(p.medicalConditions));
}

/** NRI flag — the profile form writes childrenAbroad; imports may carry familyAbroad. */
export function familyAbroadFromProfile(profile: ResidentProfile | null | undefined): boolean {
  const p = (profile ?? {}) as ResidentProfile & Record<string, unknown>;
  return Boolean(p.childrenAbroad || p.familyAbroad);
}

export function livesAloneFromProfile(profile: ResidentProfile | null | undefined): boolean {
  return Boolean(profile?.livesAlone);
}

/** Membership + ECM in one call from an assessment's score and profile. */
export function carePathwayFor(
  independenceScore: number,
  profile: ResidentProfile | null | undefined,
): { membershipId: MembershipId; membershipLabel: string; ecm: boolean } {
  const cognitiveRisk = cognitiveRiskFromProfile(profile);
  const familyAbroad = familyAbroadFromProfile(profile);
  const livesAlone = livesAloneFromProfile(profile);
  const membershipId = recommendMembership({
    independenceScore,
    livesAlone,
    familyAbroad,
    cognitiveRisk,
  });
  const ecm = ecmRecommended({
    independenceScore,
    livesAlone,
    familyAbroad,
    cognitiveRisk,
  });
  return { membershipId, membershipLabel: MEMBERSHIP_LABELS[membershipId], ecm };
}
