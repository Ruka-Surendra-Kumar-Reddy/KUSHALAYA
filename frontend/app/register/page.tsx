"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { AdminLocaleProvider } from "@/components/AdminLocaleProvider";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { registerTenant } from "@/lib/api";
import { PublicBrandMark } from "@/components/BrandLogo";
import { useTranslation } from "@/lib/i18n/context";

function RegisterForm() {
  const router = useRouter();
  const { t } = useTranslation();
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    email: "",
    password: "",
    first_name: "",
    last_name: "",
    tenant_name: "",
    tenant_email: "",
    phone: "",
    address: "",
    city: "",
    state: "",
  });

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await registerTenant(form);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("auth.registerFailed"));
    }
  }

  return (
    <main className="auth-page">
      <div className="card auth-card">
        <div style={{ marginBottom: "1rem" }}>
          <LocaleSwitcher />
        </div>
        <PublicBrandMark variant="lockup" className="auth-brand-lockup" />
        <h1>{t("auth.registerTitle")}</h1>
        <p className="muted" style={{ marginBottom: "1rem" }}>
          {t("auth.registerSubtitle")}
        </p>
        <form onSubmit={onSubmit}>
          <h3>{t("auth.adminUser")}</h3>
          <div className="grid-2" style={{ marginBottom: "1rem" }}>
            <div>
              <label>{t("auth.yourEmail")}</label>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                required
              />
            </div>
            <div>
              <label>{t("common.password")}</label>
              <input
                type="password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                required
                minLength={8}
              />
            </div>
            <div>
              <label>{t("auth.firstName")}</label>
              <input
                value={form.first_name}
                onChange={(e) => setForm({ ...form, first_name: e.target.value })}
                required
              />
            </div>
            <div>
              <label>{t("auth.lastName")}</label>
              <input
                value={form.last_name}
                onChange={(e) => setForm({ ...form, last_name: e.target.value })}
                required
              />
            </div>
          </div>
          <h3>{t("auth.agencyDetails")}</h3>
          <div className="grid-2">
            <div>
              <label>{t("auth.agencyName")}</label>
              <input
                value={form.tenant_name}
                onChange={(e) => setForm({ ...form, tenant_name: e.target.value })}
                required
              />
            </div>
            <div>
              <label>{t("auth.agencyEmail")}</label>
              <input
                type="email"
                value={form.tenant_email}
                onChange={(e) =>
                  setForm({ ...form, tenant_email: e.target.value })
                }
                required
              />
            </div>
            <div>
              <label>{t("auth.phone")}</label>
              <input
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                required
              />
            </div>
            <div>
              <label>{t("auth.city")}</label>
              <input
                value={form.city}
                onChange={(e) => setForm({ ...form, city: e.target.value })}
                required
              />
            </div>
            <div>
              <label>{t("auth.state")}</label>
              <input
                value={form.state}
                onChange={(e) => setForm({ ...form, state: e.target.value })}
                required
              />
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <label>{t("auth.address")}</label>
              <input
                value={form.address}
                onChange={(e) => setForm({ ...form, address: e.target.value })}
                required
              />
            </div>
          </div>
          {error && <p className="error" style={{ marginTop: "1rem" }}>{error}</p>}
          <button type="submit" style={{ width: "100%", marginTop: "1rem" }}>
            {t("auth.createAccount")}
          </button>
        </form>
        <p style={{ marginTop: "1rem", fontSize: "0.9rem" }}>
          {t("auth.haveAccount")}{" "}
          <Link href="/login">{t("auth.signIn")}</Link>
        </p>
      </div>
    </main>
  );
}

export default function RegisterPage() {
  return (
    <AdminLocaleProvider>
      <RegisterForm />
    </AdminLocaleProvider>
  );
}
