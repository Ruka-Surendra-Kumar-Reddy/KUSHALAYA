export default function AdminRouteLoading() {
  return (
    <div className="admin-route-loading" role="status" aria-live="polite">
      <span className="admin-route-loading-bar" />
      <p className="muted">Loading…</p>
    </div>
  );
}
