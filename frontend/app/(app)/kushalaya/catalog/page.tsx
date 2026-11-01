"use client";

import { FormEvent, Fragment, useEffect, useState } from "react";
import { canonicalCategory, groupByCategory } from "@/lib/product-categories";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/PageHeader";
import { Flash } from "@/components/Flash";
import { api, } from "@/lib/api";
import {
  GST_RATE,
  listProducts,
  priceFor,
  productImageSrc,
  resetProductImage,
  rupees,
  saveProduct,
  uploadProductImage,
  type Product,
} from "@/lib/commerce";
import "@/components/ops/commerce.css";
import { OpsModal } from "@/components/ops/OpsModal";
import { isAdmin as isAdminUser } from "@/lib/roles";

type Sheet = {
  id: number | null;
  name: string;
  category: string;
  description: string;
  cost: string;
  margin: string;
  active: boolean;
  imageUrl: string | null;
  hasOwnImage: boolean;
};
const NEW_SHEET: Sheet = {
  id: null,
  name: "",
  category: "Bathroom",
  description: "",
  cost: "",
  margin: "30",
  active: true,
  imageUrl: null,
  hasOwnImage: false,
};
const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_IMAGE_BYTES = 5 * 1024 * 1024; // same limit as the backend
const CATEGORIES = ["Bathroom", "Bedroom", "Living room", "Kitchen", "Wearable", "Service", "Other"];
const GROUP_LIMIT = 8;
type Fixes = { questions: { id: string; label: string }[]; fixes: Record<string, { ids: string[]; custom: boolean }> };

/**
 * Products: what KushAlaya sells. Admin enters our cost and the margin; the price
 * before GST and the price with 18% GST follow. Cost and margin are staff-only:
 * the family endpoints only ever return the price.
 */
export default function ProductsPage() {
  const isAdmin = isAdminUser();
  const router = useRouter();
  useEffect(() => {
    // Admin-only page (business/global data); the API refuses non-admins too.
    if (!isAdmin) router.replace("/unauthorized");
  }, [isAdmin, router]);
  const [products, setProducts] = useState<Product[] | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [fixes, setFixes] = useState<Fixes | null>(null);
  const [editing, setEditing] = useState<number | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState("");
  const [search, setSearch] = useState("");
  const [catFilter, setCatFilter] = useState("");
  const [showOff, setShowOff] = useState(false);
  const [needsPrice, setNeedsPrice] = useState(false);
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set());
  const [sheet, setSheet] = useState<Sheet | null>(null);
  const [sheetError, setSheetError] = useState("");
  const [sheetBusy, setSheetBusy] = useState(false);
  const [sheetFile, setSheetFile] = useState<File | null>(null);
  const [sheetPreview, setSheetPreview] = useState("");

  useEffect(() => {
    if (!sheetFile) return setSheetPreview("");
    const url = URL.createObjectURL(sheetFile);
    setSheetPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [sheetFile]);

  function pickSheetFile(f: File | undefined) {
    if (!f) return;
    if (!IMAGE_TYPES.includes(f.type)) return setSheetError("Use a JPG, PNG or WebP photo");
    if (f.size > MAX_IMAGE_BYTES) return setSheetError("Photo must be 5 MB or smaller");
    setSheetError("");
    setSheetFile(f);
  }

  async function removeSheetImage() {
    if (!sheet?.id || !window.confirm("Remove this product's own image and go back to the default picture?")) return;
    setSheetBusy(true);
    setSheetError("");
    try {
      const np = await resetProductImage(sheet.id);
      setSheet({ ...sheet, imageUrl: np.image_url ?? null, hasOwnImage: !!np.has_own_image });
      setProducts((list) => (list || []).map((x) => (x.id === np.id ? { ...x, ...np } : x)));
    } catch (err) {
      setSheetError(err instanceof Error ? err.message : "Could not remove the image");
    } finally {
      setSheetBusy(false);
    }
  }

  function openSheet(p: Product | null) {
    setSheetError("");
    setSheetFile(null);
    setSheet(
      p
        ? {
            id: p.id,
            name: p.name,
            category: p.category || "",
            description: p.description || "",
            cost: String((p.cost_paise ?? 0) / 100),
            margin: String((p.margin_bp ?? 0) / 100),
            active: p.active,
            imageUrl: p.image_url ?? null,
            hasOwnImage: !!p.has_own_image,
          }
        : NEW_SHEET,
    );
  }

  async function saveSheet(e: FormEvent) {
    e.preventDefault();
    if (!sheet) return;
    if (!sheet.name.trim()) return setSheetError("Give the product a name");
    const cost = Number(sheet.cost || 0);
    const margin = Number(sheet.margin || 0);
    if (!Number.isFinite(cost) || cost < 0) return setSheetError("Our cost must be ₹0 or more");
    if (!Number.isFinite(margin) || margin < 0 || margin > 500) return setSheetError("Margin must be between 0% and 500%");
    setSheetBusy(true);
    setSheetError("");
    try {
      const saved = await saveProduct(sheet.id, {
        name: sheet.name.trim(),
        category: sheet.category.trim(),
        description: sheet.description.trim(),
        cost_paise: Math.round(cost * 100),
        margin_bp: Math.round(margin * 100),
        active: sheet.active,
      });
      if (sheetFile) {
        try {
          await uploadProductImage(saved.id, sheetFile);
        } catch (err) {
          // The product is saved; keep the drawer open (now in edit mode) so the image can be retried.
          setSheet({ ...sheet, id: saved.id, imageUrl: saved.image_url ?? null, hasOwnImage: !!saved.has_own_image });
          setSheetError(`${saved.name} saved, but the image didn’t upload: ${err instanceof Error ? err.message : "error"}`);
          await load();
          return;
        }
      }
      setMessage(sheet.id ? `${saved.name} saved.` : `${saved.name} added.`);
      setSheet(null);
      setSheetFile(null);
      await load();
    } catch (err) {
      setSheetError(err instanceof Error ? err.message : "Could not save the product");
    } finally {
      setSheetBusy(false);
    }
  }

  async function load() {
    api<Fixes>("/api/v1/products/fixes").then(setFixes).catch(() => undefined);
    const rows = await listProducts(true);
    setProducts(rows);
  }

  useEffect(() => {
    if (!isAdmin) return;
    load().catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [isAdmin]);


  function openFixes(p: Product) {
    setEditing(editing === p.id ? null : p.id);
    setPicked(new Set(fixes?.fixes[String(p.id)]?.ids ?? []));
    setFilter("");
  }

  async function saveFixes(p: Product) {
    try {
      await saveProduct(p.id, { fixes: [...picked] });
      setMessage(`${p.name}: fixes ${picked.size} assessment questions.`);
      setEditing(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    }
  }

  const q = search.trim().toLowerCase();
  const offCount = (products || []).filter((p) => !p.active).length;
  const shown = (products || []).filter(
    (p) =>
      (showOff || p.active) &&
      (!catFilter || canonicalCategory(p.category) === catFilter) &&
      (!needsPrice || (p.active && !p.cost_paise)) &&
      (!q || `${p.name} ${p.category || ""}`.toLowerCase().includes(q)),
  );
  const catOptions = Array.from(new Set([...CATEGORIES, ...(products || []).map((p) => canonicalCategory(p.category)).filter(Boolean)]));
  const needsPriceCount = (products || []).filter((p) => p.active && !p.cost_paise).length;
  const groups = groupByCategory(shown, (p) => p.category);
  const filtered = Boolean(q || catFilter || needsPrice);

  if (!isAdmin) return null;
  return (
    <>
      <div className="ks-head-row">
        <PageHeader title="Products" subtitle="What we sell — families never see cost or margin" />
        {isAdmin ? (
          <div className="ks-head-actions">
            <button type="button" onClick={() => openSheet(null)} aria-label="New product" title="New product">
              <span className="ks-ha-icon" aria-hidden="true">+</span>
              <span className="ks-ha-label">+ New product</span>
            </button>
          </div>
        ) : null}
      </div>
      <Flash error={error} message={message} onClear={() => { setError(""); setMessage(""); }} />
      <div className="card cm-pl-card">
        <div className="cm-pl-tools">
          <input
            type="search"
            className="cm-pl-search"
            placeholder="Search products"
            aria-label="Search products"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select aria-label="Category" value={catFilter} onChange={(e) => setCatFilter(e.target.value)}>
            <option value="">All categories</option>
            {catOptions.map((c) => (
              <option key={c} value={c}>
                {catWord(c)}
              </option>
            ))}
          </select>
          <label className="cm-pl-toggle">
            <input type="checkbox" checked={showOff} onChange={(e) => setShowOff(e.target.checked)} />
            Show off-sale{offCount ? ` (${offCount})` : ""}
          </label>
          {needsPriceCount ? (
            <button
              type="button"
              className={`cm-pl-chip${needsPrice ? " is-on" : ""}`}
              aria-pressed={needsPrice}
              onClick={() => setNeedsPrice((v) => !v)}
            >
              Needs price ({needsPriceCount})
            </button>
          ) : null}
        </div>
        {products === null ? (
          <p className="muted">Loading…</p>
        ) : products.length === 0 ? (
          <p className="muted">No products yet.{isAdmin ? " Add one with + New product." : ""}</p>
        ) : shown.length === 0 ? (
          <p className="muted">No products match.</p>
        ) : (
          <ul className="cm-pl">
            <li className="cm-pl-head" aria-hidden="true">
              <span>Product</span>
              <span>Price before GST</span>
              <span title="Staff only — never shown to families">Our margin</span>
              <span>Status</span>
              <span>Fixes</span>
              <span />
            </li>
            {groups.map((g) => (
              <Fragment key={g.category}>
                <li className="cm-pl-group">
                  {catWord(g.category)} <small>{g.items.length}</small>
                </li>
            {(filtered || openGroups.has(g.category) ? g.items : g.items.slice(0, GROUP_LIMIT)).map((p) => {
              const fx = fixes?.fixes[String(p.id)];
              const price = priceFor(p.cost_paise ?? 0, p.margin_bp ?? 0);
              return (
                <li key={p.id} className={`cm-pl-row${p.active ? "" : " is-off"}`}>
                  <div className="cm-pl-main">
                    <div className="cm-pl-prod">
                      <ProductThumb product={p} />
                      <span>
                        <strong>{p.name}</strong>
                        <small className="cm-cat">{p.category ? catWord(canonicalCategory(p.category)) : "No category"}</small>
                      </span>
                    </div>
                    <div className="cm-pl-price">
                      {p.cost_paise ? (
                        <>
                          <strong className="cm-nowrap">{rupees(price)} + GST</strong>
                          <small className="muted cm-nowrap">Family pays {rupees(price * (1 + GST_RATE))}</small>
                        </>
                      ) : (
                        <span className="cm-pl-unpriced">Price on request</span>
                      )}
                    </div>
                    <div className="cm-pl-margin" title="Staff only — never shown to families">
                      {p.cost_paise ? (
                        <>
                          <span className="cm-margin cm-nowrap">{rupees(price - p.cost_paise)}</span>
                          <small className="muted cm-nowrap">{(p.margin_bp ?? 0) / 100}% on {rupees(p.cost_paise)}</small>
                        </>
                      ) : (
                        <small className="muted">—</small>
                      )}
                    </div>
                    <div className="cm-pl-status">
                      {/* No price → never "On sale": families would see an item nobody can order. */}
                      {p.active && !p.cost_paise ? (
                        <span className="cm-pl-pill is-warn">Needs price</span>
                      ) : (
                        <span className={`cm-pl-pill${p.active ? " is-on" : ""}`}>{p.active ? "On sale" : "Off sale"}</span>
                      )}
                    </div>
                    <div className="cm-pl-fixes">
                      <button
                        type="button"
                        className="secondary cm-fix-btn"
                        aria-expanded={editing === p.id}
                        title="Assessment questions this product fixes"
                        onClick={() => openFixes(p)}
                      >
                        {fx && fx.ids.length ? `Fixes ${fx.ids.length} question${fx.ids.length === 1 ? "" : "s"}` : "Not linked"}
                        {fx && !fx.custom && fx.ids.length ? <span className="cm-auto">auto</span> : null}
                      </button>
                    </div>
                    <div className="cm-pl-act">
                      {isAdmin ? (
                        <button type="button" className="secondary" onClick={() => openSheet(p)} aria-label={`Edit ${p.name}`}>
                          Edit
                        </button>
                      ) : null}
                    </div>
                  </div>
                  {editing === p.id && fixes ? (
                    <div className="cm-fix">
                      <p className="cm-fix-lead">
                        <strong>{p.name}</strong> is suggested to the family when an assessment marks one of these
                        as <b>Risk</b> or <b>Needs attention</b>:
                      </p>
                      {fx && !fx.custom && fx.ids.length ? (
                        <p className="muted cm-fix-auto">
                          Picked automatically from the product name. Remove or add questions to make it exact.
                        </p>
                      ) : null}
                      {picked.size === 0 ? (
                        <p className="muted">No questions yet — {p.name} won’t be suggested automatically.</p>
                      ) : (
                        <ul className="cm-fix-chosen">
                          {fixes.questions
                            .filter((qq) => picked.has(qq.id))
                            .map((qq) => (
                              <li key={qq.id}>
                                <span>{qq.label}</span>
                                {isAdmin ? (
                                  <button
                                    type="button"
                                    className="cm-fix-x"
                                    aria-label={`Remove ${qq.label}`}
                                    onClick={() => {
                                      const next = new Set(picked);
                                      next.delete(qq.id);
                                      setPicked(next);
                                    }}
                                  >
                                    Remove
                                  </button>
                                ) : null}
                              </li>
                            ))}
                        </ul>
                      )}
                      {isAdmin ? (
                        <>
                          <input
                            className="cm-fix-filter"
                            placeholder="Add a question — type to search (e.g. grab bar, stairs, fall)"
                            value={filter}
                            onChange={(e) => setFilter(e.target.value)}
                          />
                          {filter.trim() ? (
                            <ul className="cm-fix-results">
                              {fixes.questions
                                .filter((qq) => !picked.has(qq.id) && qq.label.toLowerCase().includes(filter.trim().toLowerCase()))
                                .slice(0, 8)
                                .map((qq) => (
                                  <li key={qq.id}>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setPicked(new Set(picked).add(qq.id));
                                        setFilter("");
                                      }}
                                    >
                                      + {qq.label}
                                    </button>
                                  </li>
                                ))}
                              {!fixes.questions.some(
                                (qq) => !picked.has(qq.id) && qq.label.toLowerCase().includes(filter.trim().toLowerCase()),
                              ) ? (
                                <li className="muted">No matching question.</li>
                              ) : null}
                            </ul>
                          ) : null}
                          <div className="cm-fix-actions">
                            <button type="button" className="secondary" onClick={() => setEditing(null)}>
                              Cancel
                            </button>
                            <button type="button" onClick={() => void saveFixes(p)}>
                              Save
                            </button>
                          </div>
                        </>
                      ) : null}
                    </div>
                  ) : null}
                </li>
              );
            })}
                {!filtered && g.items.length > GROUP_LIMIT ? (
                  <li className="cm-pl-more">
                    <button
                      type="button"
                      className="secondary"
                      onClick={() =>
                        setOpenGroups((prev) => {
                          const next = new Set(prev);
                          if (next.has(g.category)) next.delete(g.category);
                          else next.add(g.category);
                          return next;
                        })
                      }
                    >
                      {openGroups.has(g.category) ? `Show fewer ${catWord(g.category)}` : `Show all ${g.items.length} in ${catWord(g.category)}`}
                    </button>
                  </li>
                ) : null}
              </Fragment>
            ))}
          </ul>
        )}
      </div>

      <OpsModal open={!!sheet} title={sheet?.id ? "Edit product" : "New product"} onClose={() => !sheetBusy && setSheet(null)}>
      {sheet ? (
          <form className="cm-drawer" onSubmit={saveSheet}>
            <label>
              Name
              <input value={sheet.name} onChange={(e) => setSheet({ ...sheet, name: e.target.value })} maxLength={160} required autoFocus />
            </label>
            <label>
              Category
              <select value={sheet.category} onChange={(e) => setSheet({ ...sheet, category: e.target.value })}>
                {(CATEGORIES.includes(sheet.category) || !sheet.category ? CATEGORIES : [sheet.category, ...CATEGORIES]).map((c) => (
                  <option key={c} value={c}>
                    {catWord(c)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Description
              <textarea
                rows={3}
                value={sheet.description}
                onChange={(e) => setSheet({ ...sheet, description: e.target.value })}
                placeholder="What it is and where it goes (staff see this)"
              />
            </label>
            <div className="cm-drawer-row">
              <label>
                Our cost (₹)
                <input type="number" min={0} step="1" value={sheet.cost} onChange={(e) => setSheet({ ...sheet, cost: e.target.value })} />
              </label>
              <label>
                Margin (%)
                <input type="number" min={0} max={500} step="0.5" value={sheet.margin} onChange={(e) => setSheet({ ...sheet, margin: e.target.value })} />
              </label>
            </div>
            {(() => {
              const c = Math.round(Number(sheet.cost || 0) * 100);
              const pr = priceFor(c, Math.round(Number(sheet.margin || 0) * 100));
              return c ? (
                <p className="cm-drawer-price">
                  Price before GST <strong>{rupees(pr)} + GST</strong> · family pays {rupees(pr * (1 + GST_RATE))} ·{" "}
                  <span className="cm-margin">our margin {rupees(pr - c)}</span>
                </p>
              ) : (
                <p className="muted cm-drawer-price">Enter our cost to see the price. Unpriced products can’t be ordered.</p>
              );
            })()}
            <div className="cm-drawer-image">
              <span className="cm-drawer-label">Image</span>
              <div className="cm-drawer-image-body">
                {sheetPreview || productImageSrc(sheet.imageUrl) ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={sheetPreview || productImageSrc(sheet.imageUrl)} alt={sheet.name || "Product image"} />
                ) : (
                  <span className="cm-drawer-image-empty" aria-hidden="true">📦</span>
                )}
                <div className="cm-drawer-image-side">
                  <small className="muted">
                    {sheetFile
                      ? `New: ${sheetFile.name} — saved with the product`
                      : sheet.hasOwnImage
                        ? "Own image"
                        : sheet.imageUrl
                          ? "Default picture"
                          : "No picture yet"}
                  </small>
                  <div className="cm-drawer-image-btns">
                    <label className={`cm-drawer-file${sheetBusy ? " is-busy" : ""}`}>
                      {sheetFile || sheet.hasOwnImage ? "Change image" : "Upload image"}
                      <input
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        disabled={sheetBusy}
                        onChange={(e) => {
                          const f = e.target.files?.[0];
                          e.target.value = "";
                          pickSheetFile(f);
                        }}
                      />
                    </label>
                    {sheetFile ? (
                      <button type="button" className="secondary" onClick={() => setSheetFile(null)} disabled={sheetBusy}>
                        Undo
                      </button>
                    ) : sheet.id && sheet.hasOwnImage ? (
                      <button type="button" className="secondary" onClick={() => void removeSheetImage()} disabled={sheetBusy}>
                        Remove image
                      </button>
                    ) : null}
                  </div>
                  <small className="muted">JPG, PNG or WebP, up to 5 MB.</small>
                </div>
              </div>
            </div>
            <label className="cm-drawer-check">
              <input type="checkbox" checked={sheet.active} onChange={(e) => setSheet({ ...sheet, active: e.target.checked })} />
              On sale (shown in orders and to families)
            </label>
            {sheetError ? <p className="cm-error">{sheetError}</p> : null}
            <div className="cm-drawer-actions">
              <button type="button" className="secondary" onClick={() => setSheet(null)} disabled={sheetBusy}>
                Cancel
              </button>
              <button type="submit" disabled={sheetBusy}>
                {sheetBusy ? "Saving…" : sheet.id ? "Save product" : "Add product"}
              </button>
            </div>
          </form>
      ) : null}
      </OpsModal>
    </>
  );
}

/** Read-only product thumbnail; the photo is changed in the Edit drawer. */
function ProductThumb({ product }: { product: Product }) {
  const src = productImageSrc(product.image_url);
  return (
    <div className="cm-photo">
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt="" loading="lazy" />
      ) : (
        <span className="cm-photo-empty" aria-hidden="true">📦</span>
      )}
    </div>
  );
}

/** Stored category keys stay as they are (families' catalog maps them); only the shown brand spelling changes. */
function catWord(c: string): string {
  return c.replace(/\bKushalaya\b/g, "KushAlaya");
}
