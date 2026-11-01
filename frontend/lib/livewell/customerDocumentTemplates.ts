import { withPublicBrand } from "@/lib/public-brand";
import type { ResidentProfile } from "@/lib/livewell/resident-profile";
import { EMPTY_RESIDENT_PROFILE } from "@/lib/livewell/resident-profile";

/** Hyderabad pilot paper pack — lawyer review required before production. */

export const CUSTOMER_DOC_TEMPLATE_VERSION = "2026.08-HYD";

export type CustomerDocFormCode =
  | "LW_SERVICE_AGREEMENT"
  | "LW_PRIVACY_DPDP_CONSENT"
  | "LW_PHOTO_VIDEO_AI_CONSENT"
  | "LW_HEALTH_EMERGENCY_AUTH"
  | "LW_HOME_ASSESSMENT_CONSENT"
  | "LW_EMERGENCY_INFO_SHEET"
  | "LW_QUOTE_ACCEPTANCE"
  | "LW_WORK_COMPLETION_CERT";

export type CustomerDocPacket = "enrollment" | "assessment" | "installation" | "completion";

export type CustomerDocTemplate = {
  code: CustomerDocFormCode;
  packet: CustomerDocPacket;
  title: string;
  /** Consent/terms forms use this list; data sheets may leave empty. */
  terms: string[];
  /** When true, print layout is the Emergency Information Sheet (not terms). */
  kind?: "consent" | "emergency_info_sheet";
};

export const CUSTOMER_DOC_TEMPLATES: CustomerDocTemplate[] = [
  {
    code: "LW_SERVICE_AGREEMENT",
    packet: "enrollment",
    title: "Service Agreement",
    terms: [
      withPublicBrand("The customer engages LiveWell360 to perform a residential home safety assessment and related services."),
      "Recommendations are advisory and implementation decisions remain with the customer.",
      "Fees, if applicable, are explained before services are provided.",
      withPublicBrand("LiveWell360 is not responsible for hazards introduced after the assessment or for modifications made by third parties."),
      "Any disputes will be handled under applicable Indian law.",
    ],
  },
  {
    code: "LW_PRIVACY_DPDP_CONSENT",
    packet: "enrollment",
    title: "Privacy & DPDP Consent",
    terms: [
      withPublicBrand("The customer consents to the collection and processing of personal information for providing LiveWell360 services."),
      "Information may include contact details, assessment notes, photographs, reports and service history.",
      "The customer may request access or correction of personal information as permitted by law.",
      "Marketing communications require separate consent.",
    ],
  },
  {
    code: "LW_PHOTO_VIDEO_AI_CONSENT",
    packet: "enrollment",
    title: "Photo, Video & AI Consent",
    terms: [
      withPublicBrand("I authorize LiveWell360 to take photographs of the home for assessment purposes."),
      "I authorize the use of AI tools to assist in identifying home safety risks and preparing reports.",
      "I understand AI recommendations support, but do not replace, professional judgement.",
      "Marketing use of photographs requires my separate approval.",
    ],
  },
  {
    code: "LW_HEALTH_EMERGENCY_AUTH",
    packet: "enrollment",
    title: "Health Information & Emergency Contact Authorization",
    terms: [
      "I voluntarily provide relevant health and mobility information needed for the assessment.",
      withPublicBrand("I authorize LiveWell360 to contact the emergency contact listed if an emergency occurs during a scheduled visit."),
      "Only information necessary to provide the requested services will be collected.",
    ],
  },
  {
    code: "LW_HOME_ASSESSMENT_CONSENT",
    packet: "assessment",
    title: "Home Assessment Consent",
    terms: [
      "I authorize the assessor to inspect the agreed areas of my home.",
      "I understand the assessment is a point-in-time evaluation.",
      "I acknowledge that no assessment can identify every possible hazard.",
    ],
  },
  {
    code: "LW_EMERGENCY_INFO_SHEET",
    packet: "assessment",
    title: "Emergency Information Sheet",
    kind: "emergency_info_sheet",
    terms: [
      "Post this sheet where helpers and family can find it quickly (near phone, fridge, or bedside).",
      "Update contacts and medical notes whenever they change.",
      withPublicBrand("This sheet supports emergency response; it is not a medical record or diagnosis."),
    ],
  },
  {
    code: "LW_QUOTE_ACCEPTANCE",
    packet: "installation",
    title: "Installation Quote Acceptance",
    terms: [
      "I approve the products, labor and pricing described in the attached quotation.",
      "Any additional work requires my approval before commencement.",
      "Warranty information has been explained.",
    ],
  },
  {
    code: "LW_WORK_COMPLETION_CERT",
    packet: "completion",
    title: "Work Completion Certificate",
    terms: [
      "I confirm the agreed installation work has been completed.",
      "I have inspected the completed work and any concerns have been documented.",
      "I have received warranty information and maintenance instructions.",
    ],
  },
];

export const PACKET_LABELS: Record<CustomerDocPacket, string> = {
  enrollment: "Elder Enrollment Packet",
  assessment: "Assessment Packet",
  installation: "Installation Packet",
  completion: "Completion Packet",
};

export type CustomerDocFillContext = {
  customerName: string;
  elderName: string;
  address: string;
  phone: string;
  assessmentId: string;
  assessorName: string;
  emergencyContact?: string;
  /** Extra fields for Emergency Information Sheet */
  age?: string;
  livesAlone?: string;
  mobility?: string;
  primaryContactName?: string;
  primaryContactPhone?: string;
  secondaryContactName?: string;
  secondaryContactPhone?: string;
  medicalConditions?: string;
  allergies?: string;
  medications?: string;
  preferredHospital?: string;
  primaryDoctor?: string;
  doctorPhone?: string;
  historyOfFalls?: string;
  bloodType?: string;
  insuranceNotes?: string;
  missingRequired: string[];
};

function yn(v: boolean | null | undefined): string {
  if (v === true) return "Yes";
  if (v === false) return "No";
  return "";
}

function blank(v: string | undefined | null, fallback = "__________________________"): string {
  const t = (v ?? "").trim();
  return t || fallback;
}

export function fillContextFromAssessment(a: {
  id: string;
  clientFirstName: string;
  clientLastName: string;
  clientAddress: string;
  clientPhone: string;
  familyContactName: string;
  familyContactPhone: string;
  assessorName: string;
  residentProfile?: ResidentProfile;
}): CustomerDocFillContext {
  const profile = a.residentProfile ?? EMPTY_RESIDENT_PROFILE;
  const elderName = [a.clientFirstName, a.clientLastName].filter(Boolean).join(" ").trim();
  const customerName =
    a.familyContactName.trim() || elderName || "__________________________";
  const emergency =
    [a.familyContactName, a.familyContactPhone].filter(Boolean).join(" · ").trim() || undefined;

  const primaryName = (profile.primaryContact || a.familyContactName || "").trim();
  const primaryPhone = (a.familyContactPhone || "").trim();
  const secondaryName = (profile.secondaryContact || "").trim();
  const secondaryPhone = (profile.secondaryContactPhone || "").trim();
  const conditions = (profile.medicalConditions || []).join(", ");
  const allergies = (profile.allergies || "").trim();
  const medications = (profile.currentMedications || "").trim();
  const hospital = (profile.preferredHospital || "").trim();
  const doctor = (profile.primaryDoctor || "").trim();

  const missingRequired: string[] = [];
  if (!elderName) missingRequired.push("Resident name");
  if (!(a.clientAddress || "").trim()) missingRequired.push("Home address");
  if (!(a.clientPhone || "").trim()) missingRequired.push("Resident phone");
  if (!primaryName || !primaryPhone) missingRequired.push("Primary emergency contact (name + phone)");
  if (!hospital) missingRequired.push("Preferred hospital");
  if (!allergies) missingRequired.push("Allergies (or write None)");

  return {
    customerName: customerName || "__________________________",
    elderName: elderName || "__________________________",
    address: blank(a.clientAddress),
    phone: blank(a.clientPhone),
    assessmentId: a.id,
    assessorName: blank(a.assessorName),
    emergencyContact: emergency,
    age: blank(profile.residentAge, ""),
    livesAlone: yn(profile.livesAlone ?? null),
    mobility: profile.mobilityDevice || "",
    primaryContactName: blank(primaryName),
    primaryContactPhone: blank(primaryPhone),
    secondaryContactName: blank(secondaryName, ""),
    secondaryContactPhone: blank(secondaryPhone, ""),
    medicalConditions: blank(conditions, ""),
    allergies: blank(allergies, ""),
    medications: blank(medications, ""),
    preferredHospital: blank(hospital),
    primaryDoctor: blank(doctor, ""),
    doctorPhone: blank(profile.primaryDoctorPhone, ""),
    historyOfFalls: yn(profile.historyOfFalls ?? null),
    bloodType: blank(profile.bloodType, ""),
    insuranceNotes: blank(profile.insuranceNotes, ""),
    missingRequired,
  };
}

/** Required intake fields before printing a complete Emergency Information Sheet. */
export function emergencyInfoSheetChecklist(ctx: CustomerDocFillContext): {
  ready: boolean;
  missing: string[];
} {
  return {
    ready: ctx.missingRequired.length === 0,
    missing: ctx.missingRequired,
  };
}
