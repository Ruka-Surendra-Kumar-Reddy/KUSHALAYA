"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getStoredAuth, logout, roleLabel, type AuthUser } from "@/lib/api";

const NAV = [
  { href: "/dashboard", label: "Today" },
  { href: "/clients", label: "Clients" },
  { href: "/assessments", label: "Assessments" },
  { href: "/visits", label: "Visits" },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [auth, setAuth] = useState<AuthUser | null>(null);

  useEffect(() => {
    setAuth(getStoredAuth());
  }, []);

  async function onLogout() {
    await logout();
    router.replace("/login");
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">LW</span>
          <div>
            <strong>LiveWell ops</strong>
            <small>Daily work</small>
          </div>
        </div>
        <nav>
          {NAV.map((item) => {
            const active =
              pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link key={item.href} href={item.href} className={active ? "active" : ""}>
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-foot">
          <span>{auth?.email}</span>
          <span>{auth ? roleLabel(auth.role) : ""}</span>
          <button type="button" className="linkish" onClick={onLogout}>
            Sign out
          </button>
        </div>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
