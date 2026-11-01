import Link from "next/link";

/** Access denied, inside the ops shell (menu still there), styled like the branded 404. */
export default function UnauthorizedPage() {
  return (
    <main className="not-found is-in-shell">
      <p className="not-found-code">403</p>
      <h1>You don’t have access to this page</h1>
      <p className="not-found-lede">
        It is for admins only. If you need it for your work, ask your admin to change your role.
      </p>
      <div className="not-found-actions">
        <Link className="not-found-btn primary" href="/dashboard">
          Back to dashboard
        </Link>
      </div>
    </main>
  );
}
