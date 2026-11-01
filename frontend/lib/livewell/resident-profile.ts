/** SafeHome 360™ — Section 1 resident profile (not scored). */

export type ResidentProfile = {
  residentAge?: string;
  gender?: string;
  dwellingType?: "" | "apartment" | "villa";
  communityName?: string;
  floorNumber?: string;
  elevatorAvailable?: boolean | null;
  livesAlone?: boolean | null;
  livesWithSpouse?: boolean | null;
  domesticHelper?: boolean | null;
  fullTimeCaregiver?: boolean | null;
  childrenSameCity?: boolean;
  childrenAnotherCity?: boolean;
  childrenAbroad?: boolean;
  primaryContact?: string;
  secondaryContact?: string;
  /** Phone for secondary family / emergency contact */
  secondaryContactPhone?: string;
  emergencyContact?: string;
  preferredHospital?: string;
  primaryDoctor?: string;
  primaryDoctorPhone?: string;
  medicalConditions?: string[];
  /** Free text — use "None" if no known allergies */
  allergies?: string;
  bloodType?: string;
  insuranceNotes?: string;
  mobilityDevice?: "" | "none" | "cane" | "walker" | "wheelchair";
  historyOfFalls?: boolean | null;
  currentMedications?: string;
  /** Used for conditional logic — stairs in home? */
  hasStairs?: boolean | null;
  /** Skip smart-home section when false */
  smartHomeAssessment?: boolean | null;
  /** When smart-home section is on, include advanced device questions */
  smartHomeAdvanced?: boolean | null;
  /** Home has a balcony/outdoor terrace to assess */
  hasBalcony?: boolean | null;
  /**
   * Explicit cognitive-risk flag ("none" | "mild" | "moderate" | "high").
   * When set it overrides the medicalConditions-derived signal — see
   * livewell-rules.cognitiveRiskFromProfile.
   */
  cognitiveRisk?: "" | "none" | "mild" | "moderate" | "high";
  /** Alias for childrenAbroad on imported profiles (backend reads both). */
  familyAbroad?: boolean;
};

export const MEDICAL_CONDITION_OPTIONS = [
  "Diabetes",
  "Arthritis",
  "Parkinson's",
  "Stroke",
  "Dementia",
  "Heart disease",
  "Vision problems",
  "Hearing problems",
] as const;

export const EMPTY_RESIDENT_PROFILE: ResidentProfile = {
  dwellingType: "",
  mobilityDevice: "",
  medicalConditions: [],
  childrenSameCity: false,
  childrenAnotherCity: false,
  childrenAbroad: false,
  smartHomeAssessment: true,
  smartHomeAdvanced: false,
  hasBalcony: true,
};

export function parseResidentAge(profile: ResidentProfile): number | null {
  const n = Number(profile.residentAge);
  return Number.isFinite(n) && n > 0 ? n : null;
}
