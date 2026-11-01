"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Flash } from "@/components/Flash";
import {
  normalizeCatalog,
  resetCatalogPreserveImages,
  resolveCatalogCategoryTypes,
  type SafetyCatalog,
} from "@/lib/livewell/catalog";
import { fetchAdminCatalog, saveAdminCatalog } from "@/lib/livewell/catalogApi";
import { removeAllCatalogProductImages } from "@/lib/livewell/catalogImages";
import { CatalogProductsAdmin } from "@/components/livewell/CatalogProductsAdmin";
import { CatalogTypesAdmin } from "@/components/livewell/CatalogTypesAdmin";
import { CatalogPackageBuilder } from "@/components/livewell/CatalogPackageBuilder";

type CatalogTab = "items" | "packages" | "types";

export function CatalogAdminEditor() {
  const [catalog, setCatalog] = useState<SafetyCatalog>({ products: [], packages: [] });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<CatalogTab>("items");

  useEffect(() => {
    fetchAdminCatalog()
      .then((loaded) => setCatalog(normalizeCatalog(loaded)))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load catalog"))
      .finally(() => setLoading(false));
  }, []);

  const persist = useCallback((next: SafetyCatalog) => {
    setCatalog(normalizeCatalog(next));
  }, []);

  const stats = useMemo(() => {
    const types = resolveCatalogCategoryTypes(catalog);
    const servicePrefixes = new Set(
      types.filter((t) => t.kind === "service").map((t) => t.prefix),
    );
    const services = catalog.products.filter((p) =>
      servicePrefixes.has((p.category_prefix || "").trim()),
    ).length;
    return {
      types: types.length,
      items: catalog.products.length,
      services,
      products: catalog.products.length - services,
      packages: catalog.packages.length,
    };
  }, [catalog]);

  async function saveCatalog() {
    setError("");
    try {
      const saved = await saveAdminCatalog(catalog);
      setCatalog(normalizeCatalog(saved));
      setMessage("Catalog saved.");
      window.dispatchEvent(new CustomEvent("home-safety-master-sync-updated"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    }
  }

  function resetCatalog() {
    if (
      !window.confirm(
        "Reset catalog text and pricing to factory defaults? Product photos will be kept.",
      )
    ) {
      return;
    }
    const defaults = resetCatalogPreserveImages(catalog);
    setCatalog(defaults);
    setMessage("Reset to defaults (photos kept) — click Save to push to server.");
  }

  function removeProduct(id: string) {
    if (!window.confirm("Remove this item from all packages?")) return;
    void (async () => {
      const product = catalog.products.find((p) => p.id === id);
      if (product?.image_ids?.length) {
        try {
          const updated = await removeAllCatalogProductImages(id);
          setCatalog(updated);
        } catch {
          /* continue with local removal */
        }
      }
      persist({
        ...catalog,
        products: catalog.products.filter((p) => p.id !== id),
        packages: catalog.packages.map((pkg) => ({
          ...pkg,
          product_ids: pkg.product_ids.filter((pid) => pid !== id),
        })),
      });
    })();
  }

  if (loading) return <p>Loading catalog…</p>;

  return (
    <div className="home-safety-catalog-admin home-safety-rubric-admin">
      <Flash message={message} error={error} onClear={() => { setMessage(""); setError(""); }} />

      {catalog.products.length === 0 ? (
        <div className="card home-safety-empty" style={{ marginBottom: "1rem" }}>
          <p>No catalog items yet.</p>
          <p className="muted">
            Use <strong>Reset defaults</strong> to load factory SKUs, or add types and items
            here, then Save.
          </p>
        </div>
      ) : null}

      <div className="home-safety-catalog-stats" aria-label="Catalog totals">
        <span>
          <strong>{stats.types}</strong> types
        </span>
        <span>
          <strong>{stats.items}</strong> items
        </span>
        <span>
          <strong>{stats.services}</strong> services
        </span>
        <span>
          <strong>{stats.products}</strong> products
        </span>
        <span>
          <strong>{stats.packages}</strong> packages
        </span>
      </div>

      <div className="ks-cat-actions">
        <button type="button" className="primary" onClick={() => void saveCatalog()}>
          Save catalog
        </button>
        <button type="button" className="secondary" onClick={resetCatalog}>
          Reset defaults
        </button>
      </div>

      <div className="home-safety-catalog-tabs" role="tablist" aria-label="Catalog sections">
        {(
          [
            ["items", "Services & products"],
            ["packages", "Packages"],
            ["types", "Types"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            className={
              tab === id
                ? "home-safety-catalog-tab is-active"
                : "home-safety-catalog-tab"
            }
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "items" ? (
        <CatalogProductsAdmin
          catalog={catalog}
          onChange={persist}
          onMessage={setMessage}
          onError={setError}
          onRemove={removeProduct}
        />
      ) : null}
      {tab === "packages" ? (
        <CatalogPackageBuilder catalog={catalog} onChange={persist} />
      ) : null}
      {tab === "types" ? (
        <CatalogTypesAdmin catalog={catalog} onChange={persist} />
      ) : null}
    </div>
  );
}
