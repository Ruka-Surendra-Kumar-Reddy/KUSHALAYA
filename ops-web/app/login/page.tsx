"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { clearAuth, getStoredAuth, isStaffRole, login } from "@/lib/api";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next");
  const [email, setEmail] = useState("admin@sunrise-care.example");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState("");

  useEffect(() => {
    const auth = getStoredAuth();
    if (auth && isStaffRole(auth.role)) {
      router.replace(next && next.startsWith("/") ? next : "/dashboard");
    }
  }, [next, router]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const auth = await login(email, password);
      if (!isStaffRole(auth.role)) {
        clearAuth();
        setError("Use the family or assessor app for this login.");
        return;
      }
      router.replace(next && next.startsWith("/") ? next : "/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-card">
        <p className="muted" style={{ marginTop: 0 }}>LiveWell ops</p>
        <h1>Sign in</h1>
        <p className="muted">Same accounts as the current app. This is the new daily workspace.</p>
        <form onSubmit={onSubmit} className="stack" style={{ marginTop: "1.25rem", gap: "0.85rem" }}>
          <label>
            Email
            <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
          </label>
          <label>
            Password
            <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required />
          </label>
          {error && <p className="error">{error}</p>}
          <button type="submit">Continue</button>
        </form>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<main className="auth-page"><p className="muted">Loading…</p></main>}>
      <LoginForm />
    </Suspense>
  );
}
