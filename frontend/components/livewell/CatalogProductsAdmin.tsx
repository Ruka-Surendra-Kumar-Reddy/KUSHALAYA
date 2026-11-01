"use client";

import { useEffect, useMemo, useState } from "react";
import {
  categoryLabelFromPrefix,
  catalogTypeOrder,
  formatInr,
  groupCatalogProductsByPrefix,
  nextProductCode,
  newProductId,
  resolveCatalogCategoryTypes,
  type CatalogProduct,
  type SafetyCatalog,
} from "@/lib/livewell/catalog";
import { DEFAULT_SOLUTION_LIBRARY } from "@/lib/livewell/solution-defaults";
import { fetchAdminSolutions } from "@/lib/livewell/solutionApi";
import type { SolutionLibrary } from "@/lib/livewell/solution-types";
import {
  catalogImageUrl,
  catalogProductImageSrc,
  removeCatalogProductImage,
  uploadCatalogProductImage,
} from "@/lib/livewell/catalogImages";
import { fetchAdminSuppliers, saveAdminSuppliers } from "@/lib/livewell/supplierApi";
import { offersForProduct, supplierById } from "@/lib/livewell/suppliers";
import { selectVendorOffer } from "@/lib/livewell/supplier-selection";
import type { SupplierDirectory } from "@/lib/livewell/supplier-types";

function linesToList(text: string): string[] {
  return text
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

function listToLines(items: string[]): string {
  return items.join("\n");
}

function productMatchesQuery(product: CatalogProduct, query: string): boolean {
  if (!query) return true;
  const hay = [
    product.id,
    product.product_code ?? "",
    product.name,
    product.short_description,
    product.category,
    product.category_prefix ?? "",
  ]
    .join(" ")
    .toLowerCase();
  return hay.includes(query);
}

export function CatalogProductsAdmin({
  catalog,
  onChange,
  onMessage,
  onError,
  onRemove,
}: {
  catalog: SafetyCatalog;
  onChange: (next: SafetyCatalog) => void;
  onMessage: (msg: string) => void;
  onError: (msg: string) => void;
  onRemove?: (productId: string) => void;
}) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [uploadingProductId, setUploadingProductId] = useState<string | null>(null);
  const [photoUploadMode, setPhotoUploadMode] = useState<"generic" | "vendor">("generic");
  const [photoUploadSupplierId, setPhotoUploadSupplierId] = useState("");
  const [solutions, setSolutions] = useState<SolutionLibrary>(DEFAULT_SOLUTION_LIBRARY);
  const [suppliers, setSuppliers] = useState<SupplierDirectory | null>(null);
  const [savingVendorProductId, setSavingVendorProductId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [kindFilter, setKindFilter] = useState<"ALL" | "service" | "product">("ALL");
  const [categoryFilter, setCategoryFilter] = useState<string>("ALL");
  const [addPrefix, setAddPrefix] = useState("SVC");
  // Type sections start collapsed; 108 items open at once is unusable.
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [didInitCollapse, setDidInitCollapse] = useState(false);

  const q = query.trim().toLowerCase();
  const isFiltering = q.length > 0 || kindFilter !== "ALL" || categoryFilter !== "ALL";

  useEffect(() => {
    fetchAdminSolutions()
      .then(setSolutions)
      .catch(() => setSolutions(DEFAULT_SOLUTION_LIBRARY));
    fetchAdminSuppliers()
      .then(setSuppliers)
      .catch(() => setSuppliers({ suppliers: [], offers: [] }));
    const onSuppliers = () => {
      void fetchAdminSuppliers()
        .then(setSuppliers)
        .catch(() => undefined);
    };
    window.addEventListener("home-safety-suppliers-updated", onSuppliers);
    return () => window.removeEventListener("home-safety-suppliers-updated", onSuppliers);
  }, []);

  const types = useMemo(() => resolveCatalogCategoryTypes(catalog), [catalog]);
  const typeOrder = useMemo(() => catalogTypeOrder(catalog), [catalog]);
  const typeByPrefix = useMemo(
    () => new Map(types.map((t) => [t.prefix, t])),
    [types],
  );
  const activeTypes = useMemo(
    () => types.filter((t) => t.active !== false),
    [types],
  );

  const byPrefix = useMemo(
    () => groupCatalogProductsByPrefix(catalog.products, typeOrder),
    [catalog.products, typeOrder],
  );

  const chipPrefixes = useMemo(() => {
    const present = new Set(byPrefix.map((g) => g.prefix));
    const ordered = typeOrder.filter((p) => present.has(p));
    const extras = byPrefix
      .map((g) => g.prefix)
      .filter((p) => p !== "OTHER" && !typeOrder.includes(p));
    const chips = [...ordered, ...extras];
    if (present.has("OTHER")) chips.push("OTHER");
    return chips;
  }, [byPrefix, typeOrder]);

  const filteredGroups = useMemo(() => {
    return byPrefix
      .map((group) => ({
        ...group,
        products: group.products.filter((p) => {
          if (categoryFilter !== "ALL" && group.prefix !== categoryFilter) return false;
          const kind = typeByPrefix.get(group.prefix)?.kind ?? "product";
          if (kindFilter !== "ALL" && kind !== kindFilter) return false;
          return productMatchesQuery(p, q);
        }),
      }))
      .filter((g) => g.products.length > 0);
  }, [byPrefix, categoryFilter, kindFilter, q, typeByPrefix]);

  // Start every section closed once the catalog has loaded, so the page opens
  // as a short scannable index rather than ~9,000px of expanded rows.
  useEffect(() => {
    if (didInitCollapse || byPrefix.length === 0) return;
    setCollapsed(Object.fromEntries(byPrefix.map((g) => [g.prefix, true])));
    setDidInitCollapse(true);
  }, [byPrefix, didInitCollapse]);

  const visibleCount = filteredGroups.reduce((n, g) => n + g.products.length, 0);
  const addType = activeTypes.find((t) => t.prefix === addPrefix) ?? activeTypes[0];

  function updateProduct(id: string, patch: Partial<CatalogProduct>) {
    onChange({
      ...catalog,
      products: catalog.products.map((p) => (p.id === id ? { ...p, ...patch } : p)),
    });
  }

  function addCatalogItem() {
    const type = addType;
    if (!type) {
      onError("Add a catalog type first.");
      return;
    }
    const name = type.kind === "service" ? "New service" : "New product";
    const created: CatalogProduct = {
      id: newProductId(`${type.prefix} ${name}`),
      name,
      short_description: "",
      details: "",
      category: type.label,
      category_prefix: type.prefix,
      product_code: nextProductCode(type.prefix, catalog.products),
      price_inr: null,
      price_label: "Quote",
      sort_order: catalog.products.length + 1,
    };
    onChange({ ...catalog, products: [...catalog.products, created] });
    setExpandedId(created.id);
    setCategoryFilter(type.prefix);
    setKindFilter("ALL");
    onMessage(
      `${type.kind === "service" ? "Service" : "Product"} added as ${created.product_code}. Click Save catalog.`,
    );
  }

  function toggleSolution(productId: string, solutionId: string) {
    const product = catalog.products.find((p) => p.id === productId);
    if (!product) return;
    const has = (product.solution_ids ?? []).includes(solutionId);
    updateProduct(productId, {
      solution_ids: has
        ? (product.solution_ids ?? []).filter((x) => x !== solutionId)
        : [...(product.solution_ids ?? []), solutionId],
    });
  }

  async function handlePreferredVendor(productId: string, supplierId: string) {
    if (!suppliers || !supplierId) return;
    setSavingVendorProductId(productId);
    onError("");
    const optimisticOffers = suppliers.offers.map((offer) => {
      if (offer.product_id !== productId) return offer;
      return { ...offer, preferred: offer.supplier_id === supplierId };
    });
    const optimistic = { ...suppliers, offers: optimisticOffers };
    setSuppliers(optimistic);
    try {
      const saved = await saveAdminSuppliers(optimistic);
      setSuppliers(saved);
      onMessage("Preferred vendor updated.");
      window.dispatchEvent(new CustomEvent("home-safety-master-sync-updated"));
    } catch (e) {
      void fetchAdminSuppliers()
        .then(setSuppliers)
        .catch(() => undefined);
      onError(e instanceof Error ? e.message : "Could not update preferred vendor");
    } finally {
      setSavingVendorProductId(null);
    }
  }

  async function handleProductImage(productId: string, file: File | null) {
    if (!file) return;
    setUploadingProductId(productId);
    onError("");
    try {
      const supplierId =
        photoUploadMode === "vendor" && photoUploadSupplierId
          ? photoUploadSupplierId
          : null;
      const saved = await uploadCatalogProductImage(productId, file, {
        supplier_id: supplierId,
      });
      onChange(saved);
      onMessage(
        supplierId ? "Vendor product photo uploaded." : "Generic product photo uploaded.",
      );
    } catch (e) {
      onError(e instanceof Error ? e.message : "Photo upload failed");
    } finally {
      setUploadingProductId(null);
    }
  }

  async function handleRemoveProductImage(productId: string, documentId: number) {
    setUploadingProductId(productId);
    onError("");
    try {
      const saved = await removeCatalogProductImage(productId, documentId);
      onChange(saved);
      onMessage("Photo removed.");
    } catch (e) {
      onError(e instanceof Error ? e.message : "Could not remove photo");
    } finally {
      setUploadingProductId(null);
    }
  }

  function renderVendorCommerce(product: CatalogProduct) {
    const productOffers = suppliers ? offersForProduct(suppliers, product.id) : [];
    const selected =
      suppliers && productOffers.length
        ? selectVendorOffer(suppliers, product.id, { quantity: 1 })
        : null;
    const selectedSupplierId =
      selected?.offer.supplier_id ??
      productOffers.find((o) => o.preferred)?.supplier_id ??
      productOffers[0]?.supplier_id ??
      "";
    const selectedOffer =
      productOffers.find((o) => o.supplier_id === selectedSupplierId) ?? null;

    return (
      <div className="home-safety-catalog-section">
        <h4 className="home-safety-catalog-section-title">Commerce</h4>
        <div className="home-safety-field-row">
          <label className="home-safety-field">
            Vendor
            <select
              value={selectedSupplierId}
              disabled={!productOffers.length || savingVendorProductId === product.id}
              onChange={(e) => void handlePreferredVendor(product.id, e.target.value)}
            >
              {!productOffers.length ? <option value="">No vendor offers</option> : null}
              {productOffers.map((offer) => {
                const supplier = suppliers
                  ? supplierById(suppliers, offer.supplier_id)
                  : undefined;
                const label = supplier?.name ?? offer.supplier_id;
                return (
                  <option key={offer.id} value={offer.supplier_id}>
                    {label} — {formatInr(offer.supplier_cost_inr, "")}
                    {offer.preferred ? " · preferred" : ""}
                  </option>
                );
              })}
            </select>
          </label>
          <label className="home-safety-field">
            Vendor cost ₹
            <input
              type="text"
              readOnly
              value={selectedOffer ? formatInr(selectedOffer.supplier_cost_inr, "") : "—"}
            />
          </label>
        </div>
        <div className="home-safety-field-row">
          <label className="home-safety-field">
            Sell price ₹
            <input
              type="number"
              min={0}
              value={product.price_inr ?? ""}
              onChange={(e) =>
                updateProduct(product.id, {
                  price_inr: e.target.value ? Number(e.target.value) : null,
                })
              }
            />
          </label>
          <label className="home-safety-field">
            Price label
            <input
              value={product.price_label}
              onChange={(e) => updateProduct(product.id, { price_label: e.target.value })}
            />
          </label>
        </div>
      </div>
    );
  }

  return (
    <div className="home-safety-catalog-products">
      <div className="home-safety-catalog-browser-toolbar">
        <div className="home-safety-catalog-add-item">
          <label>
            Type
            <select
              value={addType?.prefix ?? ""}
              onChange={(e) => setAddPrefix(e.target.value)}
            >
              {activeTypes.map((type) => (
                <option key={type.prefix} value={type.prefix}>
                  {type.prefix} — {type.label}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="secondary" onClick={addCatalogItem}>
            + Add {addType?.kind === "product" ? "product" : "service"}
          </button>
          {addType ? (
            <span className="muted">Next SKU {nextProductCode(addType.prefix, catalog.products)}</span>
          ) : null}
        </div>
        <label className="home-safety-catalog-search">
          <span className="visually-hidden">Search products</span>
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
        <div className="home-safety-catalog-chips" role="tablist" aria-label="Product category">
          <button
            type="button"
            className={
              categoryFilter === "ALL"
                ? "home-safety-catalog-chip is-active"
                : "home-safety-catalog-chip"
            }
            onClick={() => setCategoryFilter("ALL")}
          >
            All types
          </button>
          {chipPrefixes.map((prefix) => {
            const type = typeByPrefix.get(prefix);
            const label =
              prefix === "OTHER" ? "Other" : type?.label ?? categoryLabelFromPrefix(prefix);
            return (
              <button
                key={prefix}
                type="button"
                className={
                  categoryFilter === prefix
                    ? "home-safety-catalog-chip is-active"
                    : "home-safety-catalog-chip"
                }
                onClick={() => setCategoryFilter(prefix)}
                title={label}
              >
                {prefix === "OTHER" ? "Other" : prefix}
              </button>
            );
          })}
        </div>
        <p className="muted home-safety-catalog-count">
          {visibleCount} of {catalog.products.length} items
        </p>
      </div>

      {visibleCount === 0 ? (
        <p className="muted">No products match this search or category.</p>
      ) : null}

      {filteredGroups.length > 1 ? (
        <div className="ks-cat-bulk">
          <button type="button" className="ks-cat-bulk-btn" onClick={() => setCollapsed({})}>
            Expand all
          </button>
          <button
            type="button"
            className="ks-cat-bulk-btn"
            onClick={() =>
              setCollapsed(Object.fromEntries(filteredGroups.map((g) => [g.prefix, true])))
            }
          >
            Collapse all
          </button>
        </div>
      ) : null}

      {filteredGroups.map(({ prefix, products }) => {
        const type = typeByPrefix.get(prefix);
        const label =
          prefix === "OTHER" ? "Other" : type?.label ?? categoryLabelFromPrefix(prefix);
        const kindLabel = type?.kind === "service" ? "services" : "products";
        // A search or filter means the user is hunting for something — show hits
        // open regardless of the collapsed state they left behind.
        const isOpen = isFiltering ? true : !collapsed[prefix];
        return (
          <section key={prefix} className="home-safety-catalog-group">
            <h3 className="home-safety-catalog-group-title">
              <button
                type="button"
                className="ks-cat-group-toggle"
                aria-expanded={isOpen}
                onClick={() =>
                  setCollapsed((c) => ({ ...c, [prefix]: !(c[prefix] ?? false) }))
                }
              >
                <span className={`ks-cat-caret${isOpen ? " is-open" : ""}`} aria-hidden="true">
                  ▸
                </span>
                {prefix === "OTHER" ? label : `${prefix} — ${label}`}
                <span className="muted">
                  {" "}
                  · {products.length} {prefix === "OTHER" ? "items" : kindLabel}
                </span>
              </button>
            </h3>
            <ul
              className="home-safety-catalog-product-list"
              hidden={!isOpen}
            >
              {products.map((product) => {
                const open = expandedId === product.id;
                const thumbSrc = catalogProductImageSrc(product);
                const picked =
                  suppliers != null
                    ? selectVendorOffer(suppliers, product.id, { quantity: 1 })
                    : null;
                return (
                  <li
                    key={product.id}
                    className={
                      open
                        ? "home-safety-catalog-product-row is-open"
                        : "home-safety-catalog-product-row"
                    }
                  >
                    <div className="home-safety-catalog-product-row-main">
                      <button
                        type="button"
                        className="home-safety-catalog-product-row-hit"
                        onClick={() => setExpandedId(open ? null : product.id)}
                        aria-expanded={open}
                      >
                        <span className="home-safety-catalog-row-thumb" aria-hidden>
                          {thumbSrc ? (
                            <img src={thumbSrc} alt="" />
                          ) : (
                            <span className="home-safety-catalog-row-thumb-empty" />
                          )}
                        </span>
                        <span className="home-safety-catalog-row-identity">
                          <strong>{product.product_code ?? product.id}</strong>
                          <span>{product.name}</span>
                        </span>
                        <span className="home-safety-catalog-row-sell">
                          <span className="home-safety-catalog-row-label">Sell</span>
                          {product.price_inr != null
                            ? formatInr(product.price_inr, "")
                            : product.price_label || "—"}
                        </span>
                        <span className="home-safety-catalog-row-vendor">
                          <span className="home-safety-catalog-row-label">Vendor cost</span>
                          {picked ? (
                            <>
                              <span className="home-safety-catalog-row-vendor-name">
                                {picked.supplier.name}
                              </span>
                              {formatInr(picked.offer.supplier_cost_inr, "")}
                            </>
                          ) : (
                            <span className="muted">No vendor</span>
                          )}
                        </span>
                        <span className="home-safety-catalog-row-meta muted">
                          {(product.solution_ids ?? []).length} sol.
                          {product.safety_improvement
                            ? ` · +${product.safety_improvement}`
                            : ""}
                        </span>
                        <span className="home-safety-catalog-row-chevron" aria-hidden>
                          {open ? "▾" : "▸"}
                        </span>
                      </button>
                      {onRemove ? (
                        <button
                          type="button"
                          className="secondary danger home-safety-catalog-row-remove"
                          onClick={() => onRemove(product.id)}
                        >
                          Remove
                        </button>
                      ) : null}
                    </div>

                    {open ? (
                      <div className="home-safety-catalog-product-expand">
                        {renderVendorCommerce(product)}

                        <div className="home-safety-catalog-section">
                          <h4 className="home-safety-catalog-section-title">Photos</h4>
                          <p className="muted" style={{ fontSize: "0.85rem", marginTop: 0 }}>
                            Photos can be generic (any vendor) or linked to a specific supplier.
                          </p>
                          <div className="home-safety-catalog-photo-grid">
                            {(product.images?.length
                              ? product.images
                              : (product.image_ids ?? []).map((document_id) => ({
                                  document_id,
                                  photo_kind: "generic" as const,
                                  supplier_id: null,
                                }))
                            ).map((image) => {
                              const kind =
                                image.photo_kind === "vendor" || image.supplier_id
                                  ? "vendor"
                                  : "generic";
                              const vendorName =
                                kind === "vendor" && image.supplier_id && suppliers
                                  ? supplierById(suppliers, image.supplier_id)?.name ??
                                    image.supplier_id
                                  : null;
                              return (
                                <div
                                  key={image.document_id}
                                  className="home-safety-catalog-photo-thumb-wrap"
                                >
                                  <img
                                    src={catalogImageUrl(image.document_id)}
                                    alt=""
                                    className="home-safety-catalog-product-thumb"
                                  />
                                  <span
                                    className={
                                      kind === "vendor"
                                        ? "home-safety-catalog-photo-badge vendor"
                                        : "home-safety-catalog-photo-badge"
                                    }
                                  >
                                    {kind === "vendor"
                                      ? `Vendor photo${vendorName ? ` · ${vendorName}` : ""}`
                                      : "Generic photo"}
                                  </span>
                                  <button
                                    type="button"
                                    className="home-safety-catalog-photo-thumb-remove"
                                    disabled={uploadingProductId === product.id}
                                    onClick={() =>
                                      void handleRemoveProductImage(
                                        product.id,
                                        image.document_id,
                                      )
                                    }
                                    aria-label="Remove photo"
                                  >
                                    ×
                                  </button>
                                </div>
                              );
                            })}
                          </div>
                          <div className="home-safety-field-row" style={{ marginBottom: "0.5rem" }}>
                            <label className="home-safety-field">
                              Photo type
                              <select
                                value={photoUploadMode}
                                onChange={(e) => {
                                  const mode = e.target.value as "generic" | "vendor";
                                  setPhotoUploadMode(mode);
                                  if (mode === "generic") setPhotoUploadSupplierId("");
                                }}
                              >
                                <option value="generic">Generic photo</option>
                                <option value="vendor">Vendor photo</option>
                              </select>
                            </label>
                            {photoUploadMode === "vendor" ? (
                              <label className="home-safety-field">
                                Vendor
                                <select
                                  value={photoUploadSupplierId}
                                  onChange={(e) => setPhotoUploadSupplierId(e.target.value)}
                                >
                                  <option value="">Select vendor…</option>
                                  {(suppliers
                                    ? offersForProduct(suppliers, product.id)
                                    : []
                                  ).map((offer) => {
                                    const supplier = suppliers
                                      ? supplierById(suppliers, offer.supplier_id)
                                      : null;
                                    return (
                                      <option key={offer.id} value={offer.supplier_id}>
                                        {supplier?.name ?? offer.supplier_id}
                                      </option>
                                    );
                                  })}
                                </select>
                              </label>
                            ) : null}
                          </div>
                          <label className="home-safety-catalog-photo-upload">
                            <input
                              type="file"
                              accept="image/jpeg,image/png"
                              disabled={
                                uploadingProductId === product.id ||
                                (photoUploadMode === "vendor" && !photoUploadSupplierId)
                              }
                              onChange={(e) => {
                                const file = e.target.files?.[0];
                                if (file) void handleProductImage(product.id, file);
                                e.target.value = "";
                              }}
                            />
                            {uploadingProductId === product.id
                              ? "Uploading…"
                              : photoUploadMode === "vendor"
                                ? "+ Add vendor photo"
                                : "+ Add generic photo"}
                          </label>
                        </div>

                        <div className="home-safety-catalog-section">
                          <h4 className="home-safety-catalog-section-title">Product</h4>
                          <div className="home-safety-field-row">
                            <label className="home-safety-field">
                              Product code
                              <input
                                value={product.product_code ?? ""}
                                onChange={(e) =>
                                  updateProduct(product.id, { product_code: e.target.value })
                                }
                              />
                            </label>
                            <label className="home-safety-field">
                              Name
                              <input
                                value={product.name}
                                onChange={(e) =>
                                  updateProduct(product.id, { name: e.target.value })
                                }
                              />
                            </label>
                          </div>
                          <label className="home-safety-field">
                            Purpose
                            <input
                              value={product.purpose ?? ""}
                              onChange={(e) =>
                                updateProduct(product.id, { purpose: e.target.value })
                              }
                            />
                          </label>
                          <label className="home-safety-field">
                            Short description (showcase)
                            <input
                              value={product.short_description}
                              onChange={(e) =>
                                updateProduct(product.id, {
                                  short_description: e.target.value,
                                })
                              }
                            />
                          </label>
                          <div className="home-safety-field-row">
                            <label className="home-safety-field">
                              Category prefix
                              <select
                                value={product.category_prefix ?? ""}
                                onChange={(e) => {
                                  const prefix = e.target.value;
                                  const type = typeByPrefix.get(prefix);
                                  updateProduct(product.id, {
                                    category_prefix: prefix || undefined,
                                    category: type?.label ?? prefix,
                                  });
                                }}
                              >
                                <option value="">—</option>
                                {types.map((type) => (
                                  <option key={type.prefix} value={type.prefix}>
                                    {type.prefix} — {type.label}
                                  </option>
                                ))}
                              </select>
                            </label>
                            <label className="home-safety-field">
                              Safety improvement (+)
                              <input
                                type="number"
                                min={0}
                                max={20}
                                value={product.safety_improvement ?? 0}
                                onChange={(e) =>
                                  updateProduct(product.id, {
                                    safety_improvement: Number(e.target.value) || 0,
                                  })
                                }
                              />
                            </label>
                          </div>
                        </div>

                        <div className="home-safety-catalog-section">
                          <h4 className="home-safety-catalog-section-title">Install &amp; notes</h4>
                          <div className="home-safety-field-row">
                            <label className="home-safety-field">
                              Product cost (text)
                              <input
                                value={product.product_cost ?? ""}
                                onChange={(e) =>
                                  updateProduct(product.id, { product_cost: e.target.value })
                                }
                              />
                            </label>
                            <label className="home-safety-field">
                              Installed price (text)
                              <input
                                value={product.installed_price ?? ""}
                                onChange={(e) =>
                                  updateProduct(product.id, {
                                    installed_price: e.target.value,
                                  })
                                }
                              />
                            </label>
                          </div>
                          <div className="home-safety-field-row">
                            <label className="home-safety-field">
                              Contractor
                              <input
                                value={product.contractor_type ?? ""}
                                onChange={(e) =>
                                  updateProduct(product.id, {
                                    contractor_type: e.target.value,
                                  })
                                }
                              />
                            </label>
                            <label className="home-safety-field">
                              Install time
                              <input
                                value={product.install_time ?? ""}
                                onChange={(e) =>
                                  updateProduct(product.id, { install_time: e.target.value })
                                }
                              />
                            </label>
                          </div>
                          <label className="home-safety-field">
                            Options (one per line)
                            <textarea
                              className="home-safety-notes"
                              rows={2}
                              value={listToLines(product.options ?? [])}
                              onChange={(e) =>
                                updateProduct(product.id, {
                                  options: linesToList(e.target.value),
                                })
                              }
                            />
                          </label>
                          <label className="home-safety-field">
                            Assessment findings (one per line)
                            <textarea
                              className="home-safety-notes"
                              rows={2}
                              value={listToLines(product.assessment_findings ?? [])}
                              onChange={(e) =>
                                updateProduct(product.id, {
                                  assessment_findings: linesToList(e.target.value),
                                })
                              }
                            />
                          </label>
                          <label className="home-safety-field">
                            Details (showcase / proposal)
                            <textarea
                              className="home-safety-notes"
                              rows={2}
                              value={product.details}
                              onChange={(e) =>
                                updateProduct(product.id, { details: e.target.value })
                              }
                            />
                          </label>
                        </div>

                        <div className="home-safety-catalog-section">
                          <h4 className="home-safety-catalog-section-title">Linked solutions</h4>
                          <p className="muted home-safety-catalog-section-hint">
                            When an assessment triggers a linked solution, this product can be
                            recommended.
                          </p>
                          <div className="home-safety-solution-rubric-links">
                            {solutions.solutions.map((sol) => (
                              <label key={sol.id} className="home-safety-solution-rubric-link">
                                <input
                                  type="checkbox"
                                  checked={(product.solution_ids ?? []).includes(sol.id)}
                                  onChange={() => toggleSolution(product.id, sol.id)}
                                />
                                <span>
                                  {sol.id} — {sol.finding}
                                </span>
                              </label>
                            ))}
                          </div>
                        </div>
                      </div>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
