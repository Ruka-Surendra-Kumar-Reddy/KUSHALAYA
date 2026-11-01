"use client";

/**
 * Friendly error with a Retry button for every family page. The raw message is
 * kept out of the main text (families do not need "500 Internal Server Error").
 */
export function FamilyError({
  message,
  onRetry,
  what = "this page",
}: {
  message?: string | null;
  onRetry?: () => void;
  what?: string;
}) {
  if (!message) return null;
  return (
    <div className="fh-error" role="alert">
      <div>
        <strong>We couldn&apos;t load {what}.</strong>
        <p>Please check your connection and try again. If it keeps happening, call your care team.</p>
      </div>
      <button
        type="button"
        className="secondary"
        onClick={() => (onRetry ? onRetry() : window.location.reload())}
      >
        Retry
      </button>
    </div>
  );
}
