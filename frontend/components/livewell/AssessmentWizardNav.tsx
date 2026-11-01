"use client";

export function AssessmentWizardNav({
  stepIndex,
  stepCount,
  onPrev,
  onNext,
  nextDisabled,
  hasUnsavedChanges,
  onSaveChanges,
  saving,
}: {
  stepIndex: number;
  stepCount: number;
  onPrev: () => void;
  onNext: () => void;
  nextDisabled?: boolean;
  hasUnsavedChanges?: boolean;
  onSaveChanges?: () => void;
  saving?: boolean;
}) {
  const isFirst = stepIndex === 0;
  const isLast = stepIndex >= stepCount - 1;

  return (
    <div className="home-safety-wizard-topnav">
      <button type="button" className="secondary" onClick={onPrev} disabled={isFirst}>
        Back
      </button>
      <span className="home-safety-step-count" aria-live="polite">
        Step {Math.min(stepIndex + 1, stepCount)} of {stepCount}
      </span>
      {hasUnsavedChanges && onSaveChanges ? (
        <button type="button" className="primary" onClick={onSaveChanges} disabled={saving}>
          {saving ? "Saving…" : "Save changes"}
        </button>
      ) : null}
      <button
        type="button"
        className={hasUnsavedChanges ? "secondary" : "primary"}
        onClick={onNext}
        disabled={nextDisabled || isLast}
      >
        Next
      </button>
    </div>
  );
}
