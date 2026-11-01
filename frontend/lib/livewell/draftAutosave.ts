/**
 * Opening a draft must never write to it. Autosave runs only after a real
 * user edit; load-time fills (client age, suggested assessor) stay local.
 */
export type AutosaveGate = {
  /** Call from handlers that run because the user changed something. */
  markUserEdit(): void;
  /** Call on pointer/key input inside the form (not step navigation). */
  markInteraction(now?: number): void;
  /** True for a change caused by input in the last `windowMs`. */
  recentInteraction(now?: number, windowMs?: number): boolean;
  shouldSave(status: string): boolean;
};

export function createAutosaveGate(): AutosaveGate {
  let edited = false;
  let lastInteraction = 0;
  return {
    markUserEdit() {
      edited = true;
    },
    markInteraction(now = Date.now()) {
      lastInteraction = now;
    },
    recentInteraction(now = Date.now(), windowMs = 1500) {
      return lastInteraction > 0 && now - lastInteraction <= windowMs;
    },
    shouldSave(status: string) {
      return edited && status === "draft";
    },
  };
}

type TeamMember = { email: string; first_name: string; last_name: string };

/** The signed-in user's name, offered as a suggestion for a blank assessor (never written on load). */
export function suggestedAssessor(team: TeamMember[], email: string | null | undefined): string {
  const me = team.find((u) => u.email.toLowerCase() === (email || "").toLowerCase().trim());
  return me ? `${me.first_name} ${me.last_name}`.trim() : "";
}
