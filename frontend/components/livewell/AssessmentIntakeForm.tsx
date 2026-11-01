"use client";

import { AssessmentClientPicker, type ClientLinkPatch } from "@/components/livewell/AssessmentClientPicker";
import {
  MEDICAL_CONDITION_OPTIONS,
  type ResidentProfile,
} from "@/lib/livewell/resident-profile";
import type { HomeSafetyAssessment } from "@/lib/livewell/assessment";
import { useEffect, useState } from "react";
import { api, getStoredAuth } from "@/lib/api";
import { suggestedAssessor } from "@/lib/livewell/draftAutosave";

type TeamUser = { id: number; email: string; first_name: string; last_name: string };

/**
 * Team members for the Assessor picker. The signed-in user's name is only a
 * suggestion: opening a draft never writes it (that used to autosave the viewer).
 */
function useAssessorOptions() {
  const [team, setTeam] = useState<TeamUser[]>([]);
  useEffect(() => {
    if (!getStoredAuth()?.access_token) return;
    api<TeamUser[]>("/api/v1/prospects/owners")
      .then(setTeam)
      .catch(() => setTeam([]));
  }, []);
  return {
    names: team.map((u) => `${u.first_name} ${u.last_name}`.trim()).filter(Boolean),
    me: suggestedAssessor(team, getStoredAuth()?.email),
  };
}

type Props = {
  draft: HomeSafetyAssessment;
  onField: <K extends keyof HomeSafetyAssessment>(key: K, value: HomeSafetyAssessment[K]) => void;
  onProfile: (profile: ResidentProfile) => void;
  onApplyLink: (patch: ClientLinkPatch) => void;
};

export function AssessmentIntakeForm({ draft, onField, onProfile, onApplyLink }: Props) {
  const profile = draft.residentProfile;
  const { names: assessors, me } = useAssessorOptions();

  function setProfile<K extends keyof ResidentProfile>(key: K, value: ResidentProfile[K]) {
    onProfile({ ...profile, [key]: value });
  }

  function toggleCondition(name: string) {
    const current = profile.medicalConditions ?? [];
    const next = current.includes(name)
      ? current.filter((c) => c !== name)
      : [...current, name];
    setProfile("medicalConditions", next);
  }

  return (
    <div className="home-safety-intake">
      <div className="home-safety-intake-block">
        <AssessmentClientPicker draft={draft} onApply={onApplyLink} />
      </div>

      <div className="home-safety-intake-block">
        <h3>Resident</h3>
        <div className="home-safety-field-row">
          <label className="home-safety-field">
            First name <span className="home-safety-required">*</span>
            <input
              value={draft.clientFirstName}
              onChange={(e) => onField("clientFirstName", e.target.value)}
              placeholder="Resident"
              autoComplete="given-name"
            />
          </label>
          <label className="home-safety-field">
            Last name
            <input
              value={draft.clientLastName}
              onChange={(e) => onField("clientLastName", e.target.value)}
              autoComplete="family-name"
            />
          </label>
        </div>
        <div className="home-safety-field-row">
          <label className="home-safety-field">
            Age
            <input
              type="number"
              min={1}
              max={120}
              inputMode="numeric"
              value={profile.residentAge ?? ""}
              onChange={(e) => setProfile("residentAge", e.target.value)}
            />
          </label>
          <label className="home-safety-field">
            Gender
            <input
              value={profile.gender ?? ""}
              onChange={(e) => setProfile("gender", e.target.value)}
              placeholder="Optional"
            />
          </label>
        </div>
        <label className="home-safety-field">
          Home address
          <input
            value={draft.clientAddress}
            onChange={(e) => onField("clientAddress", e.target.value)}
            placeholder="Apartment / villa, community, city"
            autoComplete="street-address"
          />
        </label>
        <div className="home-safety-field-row">
          <label className="home-safety-field">
            Community / building
            <input
              value={profile.communityName ?? ""}
              onChange={(e) => setProfile("communityName", e.target.value)}
            />
          </label>
          <label className="home-safety-field">
            Floor
            <input
              value={profile.floorNumber ?? ""}
              onChange={(e) => setProfile("floorNumber", e.target.value)}
            />
          </label>
        </div>
        <div className="home-safety-field-row">
          <label className="home-safety-field">
            Dwelling
            <select
              value={profile.dwellingType ?? ""}
              onChange={(e) =>
                setProfile("dwellingType", e.target.value as ResidentProfile["dwellingType"])
              }
            >
              <option value="">—</option>
              <option value="apartment">Apartment</option>
              <option value="villa">Villa</option>
            </select>
          </label>
          <label className="home-safety-field">
            Resident phone
            <input
              type="tel"
              value={draft.clientPhone}
              onChange={(e) => onField("clientPhone", e.target.value)}
              autoComplete="tel"
            />
          </label>
        </div>
      </div>

      <div className="home-safety-intake-block">
        <h3>Living situation</h3>
        <div className="home-safety-profile-checks home-safety-profile-checks-grid">
          <label>
            <input
              type="checkbox"
              checked={profile.elevatorAvailable === true}
              onChange={(e) => setProfile("elevatorAvailable", e.target.checked)}
            />
            Elevator
          </label>
          <label>
            <input
              type="checkbox"
              checked={profile.hasStairs === true}
              onChange={(e) => setProfile("hasStairs", e.target.checked)}
            />
            Has stairs
          </label>
          <label>
            <input
              type="checkbox"
              checked={profile.livesAlone === true}
              onChange={(e) => setProfile("livesAlone", e.target.checked)}
            />
            Lives alone
          </label>
          <label>
            <input
              type="checkbox"
              checked={profile.livesWithSpouse === true}
              onChange={(e) => setProfile("livesWithSpouse", e.target.checked)}
            />
            With spouse
          </label>
          <label>
            <input
              type="checkbox"
              checked={profile.domesticHelper === true}
              onChange={(e) => setProfile("domesticHelper", e.target.checked)}
            />
            Domestic helper
          </label>
          <label>
            <input
              type="checkbox"
              checked={profile.fullTimeCaregiver === true}
              onChange={(e) => setProfile("fullTimeCaregiver", e.target.checked)}
            />
            Full-time caregiver
          </label>
          <label>
            <input
              type="checkbox"
              checked={profile.hasBalcony !== false}
              onChange={(e) => setProfile("hasBalcony", e.target.checked)}
            />
            Has balcony / terrace
          </label>
          <label>
            <input
              type="checkbox"
              checked={profile.smartHomeAssessment !== false}
              onChange={(e) =>
                setProfile("smartHomeAssessment", e.target.checked ? true : false)
              }
            />
            Include smart-home section
          </label>
          {profile.smartHomeAssessment !== false && (
            <label>
              <input
                type="checkbox"
                checked={profile.smartHomeAdvanced === true}
                onChange={(e) => setProfile("smartHomeAdvanced", e.target.checked)}
              />
              Include advanced smart devices
            </label>
          )}
        </div>
        <label className="home-safety-field">
          Mobility device
          <select
            value={profile.mobilityDevice ?? ""}
            onChange={(e) =>
              setProfile("mobilityDevice", e.target.value as ResidentProfile["mobilityDevice"])
            }
          >
            <option value="">—</option>
            <option value="none">None</option>
            <option value="cane">Cane</option>
            <option value="walker">Walker</option>
            <option value="wheelchair">Wheelchair</option>
          </select>
        </label>
        <label className="home-safety-field home-safety-check-inline">
          <input
            type="checkbox"
            checked={profile.historyOfFalls === true}
            onChange={(e) => setProfile("historyOfFalls", e.target.checked)}
          />
          History of falls (last 12 months)
        </label>
      </div>

      <div className="home-safety-intake-block">
        <h3>Family &amp; emergency contacts</h3>
        <label className="home-safety-field">
          Primary emergency contact (name)
          <input
            value={profile.primaryContact ?? draft.familyContactName}
            onChange={(e) => {
              setProfile("primaryContact", e.target.value);
              onField("familyContactName", e.target.value);
            }}
            required
          />
        </label>
        <div className="home-safety-field-row">
          <label className="home-safety-field">
            Primary contact phone
            <input
              type="tel"
              value={draft.familyContactPhone}
              onChange={(e) => {
                onField("familyContactPhone", e.target.value);
                setProfile("emergencyContact", e.target.value);
              }}
              required
            />
          </label>
          <label className="home-safety-field">
            Resident email
            <input
              type="email"
              value={draft.clientEmail}
              onChange={(e) => onField("clientEmail", e.target.value)}
            />
          </label>
        </div>
        <div className="home-safety-field-row">
          <label className="home-safety-field">
            Secondary contact (name)
            <input
              value={profile.secondaryContact ?? ""}
              onChange={(e) => setProfile("secondaryContact", e.target.value)}
              placeholder="Optional"
            />
          </label>
          <label className="home-safety-field">
            Secondary contact phone
            <input
              type="tel"
              value={profile.secondaryContactPhone ?? ""}
              onChange={(e) => setProfile("secondaryContactPhone", e.target.value)}
            />
          </label>
        </div>
        <div className="home-safety-profile-checks">
          <label>
            <input
              type="checkbox"
              checked={profile.childrenSameCity === true}
              onChange={(e) => setProfile("childrenSameCity", e.target.checked)}
            />
            Children — same city
          </label>
          <label>
            <input
              type="checkbox"
              checked={profile.childrenAnotherCity === true}
              onChange={(e) => setProfile("childrenAnotherCity", e.target.checked)}
            />
            Children — another city
          </label>
          <label>
            <input
              type="checkbox"
              checked={profile.childrenAbroad === true}
              onChange={(e) => setProfile("childrenAbroad", e.target.checked)}
            />
            Children abroad
          </label>
        </div>
      </div>

      <div className="home-safety-intake-block">
        <h3>Medical</h3>
        <fieldset className="home-safety-profile-fieldset">
          <legend>Conditions</legend>
          <div className="home-safety-profile-checks home-safety-profile-checks-grid">
            {MEDICAL_CONDITION_OPTIONS.map((c) => (
              <label key={c}>
                <input
                  type="checkbox"
                  checked={(profile.medicalConditions ?? []).includes(c)}
                  onChange={() => toggleCondition(c)}
                />
                {c}
              </label>
            ))}
          </div>
        </fieldset>
        <div className="home-safety-field-row">
          <label className="home-safety-field">
            Allergies
            <input
              value={profile.allergies ?? ""}
              onChange={(e) => setProfile("allergies", e.target.value)}
              placeholder="e.g. Penicillin, or None"
            />
          </label>
          <label className="home-safety-field">
            Blood type
            <input
              value={profile.bloodType ?? ""}
              onChange={(e) => setProfile("bloodType", e.target.value)}
              placeholder="e.g. O+"
            />
          </label>
        </div>
        <div className="home-safety-field-row">
          <label className="home-safety-field">
            Preferred hospital
            <input
              value={profile.preferredHospital ?? ""}
              onChange={(e) => setProfile("preferredHospital", e.target.value)}
              placeholder="Nearest preferred hospital"
            />
          </label>
          <label className="home-safety-field">
            Primary doctor
            <input
              value={profile.primaryDoctor ?? ""}
              onChange={(e) => setProfile("primaryDoctor", e.target.value)}
            />
          </label>
        </div>
        <div className="home-safety-field-row">
          <label className="home-safety-field">
            Doctor phone
            <input
              type="tel"
              value={profile.primaryDoctorPhone ?? ""}
              onChange={(e) => setProfile("primaryDoctorPhone", e.target.value)}
            />
          </label>
          <label className="home-safety-field">
            Insurance / ID
            <input
              value={profile.insuranceNotes ?? ""}
              onChange={(e) => setProfile("insuranceNotes", e.target.value)}
              placeholder="Policy # or insurance name"
            />
          </label>
        </div>
        <label className="home-safety-field">
          Current medications
          <textarea
            className="home-safety-notes"
            rows={2}
            value={profile.currentMedications ?? ""}
            onChange={(e) => setProfile("currentMedications", e.target.value)}
          />
        </label>
      </div>

      <div className="home-safety-intake-block">
        <h3>Visit notes</h3>
        <label className="home-safety-field">
          Assessor
          <input
            value={draft.assessorName}
            onChange={(e) => onField("assessorName", e.target.value)}
            placeholder={me ? `Suggested: ${me}` : "Pick a team member or type a name"}
            list="assessor-options"
            autoComplete="off"
          />
          {me && !draft.assessorName.trim() && draft.status !== "completed" ? (
            <button type="button" className="btn btn-ghost btn-sm home-safety-assessor-me" onClick={() => onField("assessorName", me)}>
              Use my name ({me})
            </button>
          ) : null}
          <datalist id="assessor-options">
            {assessors.map((n) => (
              <option key={n} value={n} />
            ))}
          </datalist>
        </label>
        <label className="home-safety-field">
          Pain points &amp; concerns
          <textarea
            className="home-safety-notes"
            rows={3}
            value={draft.painPoints}
            onChange={(e) => onField("painPoints", e.target.value)}
            placeholder="Falls, mobility fears, family worries…"
          />
        </label>
      </div>
    </div>
  );
}
