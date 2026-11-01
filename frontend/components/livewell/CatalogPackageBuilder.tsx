"use client";

import { useMemo, useState } from "react";
import {
  catalogTypeOrder,
  formatInr,
  newPackageId,
  resolveCatalogCategoryTypes,
  type SafetyCatalog,
  type ServicePackage,
} from "@/lib/livewell/catalog";
import { catalogProductImageSrc } from "@/lib/livewell/catalogImages";
import { getStoredAuth } from "@/lib/api";

function productMatchesQuery(
  name: string,
  code: string | undefined,
  category: string,
  query: string,
): boolean {
  if (!query) return true;
  return [name, code ?? "", category].join(" ").toLowerCase().includes(query);
}

export function CatalogPackageBuilder({
  catalog,
  onChange,
}: {
  catalog: SafetyCatalog;
  onChange: (next: SafetyCatalog) => void;
}) {
  const tenantId = getStoredAuth()?.tenant_id ?? undefined;
  const types = resolveCatalogCategoryTypes(catalog);
  const typeOrder = catalogTypeOrder(catalog);
  const typeByPrefix = useMemo(
    () => new Map(types.map((t) => [t.prefix, t])),
    [types],
  );

  function persistPackages(packages: ServicePackage[]) {
    onChange({ ...catalog, packages });
  }

  function updatePackage(id: string, patch: Partial<ServicePackage>) {
    persistPackages(catalog.packages.map((p) => (p.id === id ? { ...p, ...patch } : p)));
  }

  function addPackage() {
    persistPackages([
      ...catalog.packages,
      {
        id: newPackageId("New package"),
        name: "New package",
        tagline: "",
        description: "",
        price_inr: null,
        price_label: "From",
        highlight: false,
        product_ids: [],
        sort_order: catalog.packages.length + 1,
      },
    ]);
  }

  function removePackage(id: string) {
    if (!window.confirm("Remove this package?")) return;
    persistPackages(catalog.packages.filter((p) => p.id !== id));
  }

  function setIncluded(pkgId: string, productId: string, included: boolean) {
    persistPackages(
      catalog.packages.map((pkg) => {
        if (pkg.id !== pkgId) return pkg;
        if (included) {
          if (pkg.product_ids.includes(productId)) return pkg;
          return { ...pkg, product_ids: [...pkg.product_ids, productId] };
        }
        return { ...pkg, product_ids: pkg.product_ids.filter((id) => id !== productId) };
      }),
    );
  }

  function movePackageProduct(pkgId: string, productId: string, direction: -1 | 1) {
    persistPackages(
      catalog.packages.map((pkg) => {
        if (pkg.id !== pkgId) return pkg;
        const index = pkg.product_ids.indexOf(productId);
        if (index < 0) return pkg;
        const next = index + direction;
        if (next < 0 || next >= pkg.product_ids.length) return pkg;
        const ids = [...pkg.product_ids];
        [ids[index], ids[next]] = [ids[next], ids[index]];
        return { ...pkg, product_ids: ids };
      }),
    );
  }

  return (
    <div className="home-safety-catalog-packages">
      <p className="muted" style={{ marginBottom: "1rem", fontSize: "0.9rem" }}>
        Each package needs a <strong>Price ₹</strong>. Filter by type, then tick services
        and products to include. Reorder the included list, then click{" "}
        <strong>Save catalog</strong>.
      </p>

      {catalog.packages.map((pkg) => (
        <PackageCard
          key={pkg.id}
          pkg={pkg}
          catalog={catalog}
          typeOrder={typeOrder}
          typeByPrefix={typeByPrefix}
          tenantId={tenantId}
          onUpdate={updatePackage}
          onRemove={removePackage}
          onSetIncluded={setIncluded}
          onMove={movePackageProduct}
        />
      ))}
      <button type="button" className="secondary" onClick={addPackage}>
        + Add package
      </button>
    </div>
  );
}

function PackageCard({
  pkg,
  catalog,
  typeOrder,
  typeByPrefix,
  tenantId,
  onUpdate,
  onRemove,
  onSetIncluded,
  onMove,
}: {
  pkg: ServicePackage;
  catalog: SafetyCatalog;
  typeOrder: string[];
  typeByPrefix: Map<string, ReturnType<typeof resolveCatalogCategoryTypes>[number]>;
  tenantId: number | undefined;
  onUpdate: (id: string, patch: Partial<ServicePackage>) => void;
  onRemove: (id: string) => void;
  onSetIncluded: (pkgId: string, productId: string, included: boolean) => void;
  onMove: (pkgId: string, productId: string, direction: -1 | 1) => void;
}) {
  const [query, setQuery] = useState("");
  const [kindFilter, setKindFilter] = useState<"ALL" | "service" | "product">("ALL");
  const [typeFilter, setTypeFilter] = useState("ALL");
  const q = query.trim().toLowerCase();

  const pickerItems = useMemo(() => {
    return catalog.products.filter((product) => {
      const prefix = (product.category_prefix || "").trim();
      const kind = typeByPrefix.get(prefix)?.kind ?? "product";
      if (kindFilter !== "ALL" && kind !== kindFilter) return false;
      if (typeFilter !== "ALL" && prefix !== typeFilter) return false;
      return productMatchesQuery(
        product.name,
        product.product_code,
        product.category,
        q,
      );
    });
  }, [catalog.products, kindFilter, typeFilter, q, typeByPrefix]);

  const typeChips = useMemo(() => {
    const present = new Set(
      catalog.products
        .map((p) => (p.category_prefix || "").trim())
        .filter(Boolean),
    );
    return typeOrder.filter((prefix) => present.has(prefix));
  }, [catalog.products, typeOrder]);

  return (
    <div className="card home-safety-catalog-package" style={{ marginBottom: "1rem" }}>
      <div className="home-safety-catalog-package-head">
        <input
          className="home-safety-catalog-title-input"
          value={pkg.name}
          onChange={(e) => onUpdate(pkg.id, { name: e.target.value })}
          placeholder="Package name"
        />
        <label className="home-safety-catalog-highlight">
          <input
            type="checkbox"
            checked={pkg.highlight}
            onChange={(e) => onUpdate(pkg.id, { highlight: e.target.checked })}
          />
          Popular
        </label>
        <button type="button" className="secondary danger" onClick={() => onRemove(pkg.id)}>
          Remove package
        </button>
      </div>
      <input
        value={pkg.tagline}
        onChange={(e) => onUpdate(pkg.id, { tagline: e.target.value })}
        placeholder="Tagline"
        style={{ width: "100%", marginBottom: "0.5rem" }}
      />
      <textarea
        rows={2}
        value={pkg.description}
        onChange={(e) => onUpdate(pkg.id, { description: e.target.value })}
        placeholder="Description for families"
        style={{ width: "100%", marginBottom: "0.5rem" }}
      />
      <div className="home-safety-catalog-package-pricing">
        <label>
          Price ₹{pkg.price_inr == null ? " (required for savings)" : ""}
          <input
            type="number"
            min={0}
            value={pkg.price_inr ?? ""}
            onChange={(e) =>
              onUpdate(pkg.id, {
                price_inr: e.target.value ? Number(e.target.value) : null,
              })
            }
            placeholder="Package sell price"
          />
        </label>
        <label>
          Label
          <input
            value={pkg.price_label}
            onChange={(e) => onUpdate(pkg.id, { price_label: e.target.value })}
          />
        </label>
      </div>

      <p className="home-safety-catalog-picks-label">
        Included in this package ({pkg.product_ids.length})
      </p>
      {pkg.product_ids.length === 0 ? (
        <p className="muted home-safety-catalog-included-empty">
          No items yet — filter by type below and tick services or products to include.
        </p>
      ) : (
        <ol className="home-safety-catalog-included-list">
          {pkg.product_ids.map((productId, index) => {
            const prod = catalog.products.find((p) => p.id === productId);
            if (!prod) return null;
            const thumb = catalogProductImageSrc(prod, tenantId);
            return (
              <li key={productId} className="home-safety-catalog-included-item">
                <span className="home-safety-catalog-included-name">
                  <span className="home-safety-catalog-included-num">{index + 1}</span>
                  {thumb ? (
                    <img src={thumb} alt="" className="home-safety-catalog-included-thumb" />
                  ) : null}
                  <span>
                    <strong>{prod.name}</strong>
                    {prod.product_code ? (
                      <span className="muted home-safety-catalog-included-cat">
                        {prod.product_code}
                      </span>
                    ) : null}
                    <span className="muted home-safety-catalog-included-cat">
                      {prod.category}
                    </span>
                  </span>
                </span>
                <span className="home-safety-catalog-included-actions">
                  <button
                    type="button"
                    className="secondary home-safety-catalog-move-btn"
                    disabled={index === 0}
                    onClick={() => onMove(pkg.id, productId, -1)}
                    aria-label="Move up"
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    className="secondary home-safety-catalog-move-btn"
                    disabled={index === pkg.product_ids.length - 1}
                    onClick={() => onMove(pkg.id, productId, 1)}
                    aria-label="Move down"
                  >
                    ↓
                  </button>
                  <button
                    type="button"
                    className="secondary danger home-safety-catalog-remove-from-pkg"
                    onClick={() => onSetIncluded(pkg.id, productId, false)}
                  >
                    Remove
                  </button>
                </span>
              </li>
            );
          })}
        </ol>
      )}

      <p className="home-safety-catalog-picks-label home-safety-catalog-add-label">
        Add from catalog
      </p>
      <div className="home-safety-catalog-picker-toolbar">
        <label className="home-safety-catalog-search">
          <span className="visually-hidden">Search catalog items</span>
          <input aria-label="Search SKU or name"
            type="search"
            placeholder="Search SKU or name…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <div className="home-safety-catalog-chips" role="group" aria-label="Kind">
          {(
            [
              ["ALL", "All"],
              ["service", "Services"],
              ["product", "Products"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={
                kindFilter === id
                  ? "home-safety-catalog-chip is-active"
                  : "home-safety-catalog-chip"
              }
              onClick={() => setKindFilter(id)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="home-safety-catalog-chips" role="group" aria-label="Type">
          <button
            type="button"
            className={
              typeFilter === "ALL"
                ? "home-safety-catalog-chip is-active"
                : "home-safety-catalog-chip"
            }
            onClick={() => setTypeFilter("ALL")}
          >
            All types
          </button>
          {typeChips.map((prefix) => (
            <button
              key={prefix}
              type="button"
              className={
                typeFilter === prefix
                  ? "home-safety-catalog-chip is-active"
                  : "home-safety-catalog-chip"
              }
              onClick={() => setTypeFilter(prefix)}
              title={typeByPrefix.get(prefix)?.label ?? prefix}
            >
              {prefix}
            </button>
          ))}
        </div>
      </div>
      {pickerItems.length === 0 ? (
        <p className="muted" style={{ fontSize: "0.85rem" }}>
          No catalog items match this filter.
        </p>
      ) : (
        <ul className="home-safety-catalog-picker-list">
          {pickerItems.map((prod) => {
            const included = pkg.product_ids.includes(prod.id);
            const prefix = (prod.category_prefix || "").trim();
            const type = typeByPrefix.get(prefix);
            return (
              <li key={prod.id}>
                <label className="home-safety-catalog-picker-row">
                  <input
                    type="checkbox"
                    checked={included}
                    onChange={(e) => onSetIncluded(pkg.id, prod.id, e.target.checked)}
                  />
                  <span>
                    <strong>{prod.name}</strong>
                    <span className="muted">
                      {" "}
                      {prod.product_code || prefix} · {type?.label ?? prod.category} ·{" "}
                      {type?.kind === "service" ? "service" : "product"}
                    </span>
                  </span>
                  <span className="muted">{formatInr(prod.price_inr, prod.price_label)}</span>
                </label>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
