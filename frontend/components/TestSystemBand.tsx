/**
 * Yellow strip on every page of the TEST instance so nobody mistakes it for
 * production. Driven by NEXT_PUBLIC_ENVIRONMENT, which is baked in at build
 * time, so production (unset) renders nothing at all.
 */
export function isTestEnvironment(): boolean {
  return process.env.NEXT_PUBLIC_ENVIRONMENT === "test";
}

export function TestSystemBand() {
  if (!isTestEnvironment()) return null;
  return (
    <div
      role="status"
      style={{
        background: "#facc15",
        color: "#1c1917",
        textAlign: "center",
        fontSize: "0.8rem",
        fontWeight: 700,
        letterSpacing: "0.06em",
        padding: "0.3rem 1rem",
        textTransform: "uppercase",
      }}
    >
      Test system · not production · data here is not real
    </div>
  );
}
