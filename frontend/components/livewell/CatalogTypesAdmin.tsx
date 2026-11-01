"use client";

import { useMemo, useState } from "react";
import {
  resolveCatalogCategoryTypes,
  type CatalogCategoryType,
  type SafetyCatalog,
} from "@/lib/livewell/catalog";

const PREFIX_RE = /^[A-Z][A-Z0-9]{0,7}$/;

export function CatalogTypesAdmin({
  catalog,
  onChange,
}: {
  catalog: SafetyCatalog;
  onChange: (next: SafetyCatalog) => void;
}) {
  const types = resolveCatalogCategoryTypes(catalog);
  const usedPrefixes = useMemo(() => {
    const counts = new Map<string, number>();
    for (const product of catalog.products) {
      const prefix = (product.category_prefix || "").trim().toUpperCase();
      if (!prefix) continue;
      counts.set(prefix, (counts.get(prefix) ?? 0) + 1);
    }
    return counts;
  }, [catalog.products]);

  const [newPrefix, setNewPrefix] = useState("");
  const [newLabel, setNewLabel] = useState("");
  const [newKind, setNewKind] = useState<CatalogCategoryType["kind"]>("service");
  const [error, setError] = useState("");

  function persist(nextTypes: CatalogCategoryType[]) {
    onChange({ ...catalog, category_types: nextTypes });
  }

  function updateType(prefix: string, patch: Partial<CatalogCategoryType>) {
    persist(types.map((t) => (t.prefix === prefix ? { ...t, ...patch } : t)));
  }

  function addType() {
    const prefix = newPrefix.trim().toUpperCase();
    const label = newLabel.trim() || prefix;
    if (!PREFIX_RE.test(prefix)) {
      setError("Prefix must be 1–8 letters or digits, starting with a letter (e.g. SVC).");
      return;
    }
    if (types.some((t) => t.prefix === prefix)) {
      setError(`Type ${prefix} already exists.`);
      return;
    }
    setError("");
    persist([
      ...types,
      {
        prefix,
        label,
        kind: newKind,
        sort: types.reduce((max, t) => Math.max(max, t.sort), -1) + 1,
        active: true,
      },
    ]);
    setNewPrefix("");
    setNewLabel("");
    setNewKind("service");
  }

  function removeType(prefix: string) {
    const used = usedPrefixes.get(prefix) ?? 0;
    if (used > 0) {
      setError(`Cannot remove ${prefix} while ${used} catalog items use it. Deactivate instead.`);
      return;
    }
    persist(types.filter((t) => t.prefix !== prefix));
  }

  return (
    <div className="home-safety-catalog-types">
      <p className="muted" style={{ marginBottom: "0.85rem" }}>
        Types group the catalog (SVC, BTH, NUR…). Services are visit or membership SKUs;
        products are equipment. Packages pick existing items by type.
      </p>
      {error ? <p className="home-safety-catalog-inline-error">{error}</p> : null}

      <div className="home-safety-catalog-type-table-wrap">
        <table className="data-table home-safety-catalog-type-table">
          <thead>
            <tr>
              <th>Prefix</th>
              <th>Label</th>
              <th>Kind</th>
              <th>Sort</th>
              <th>Active</th>
              <th>Items</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {types.map((type) => {
              const used = usedPrefixes.get(type.prefix) ?? 0;
              return (
                <tr key={type.prefix}>
                  <td>
                    <code>{type.prefix}</code>
                  </td>
                  <td>
                    <input
                      value={type.label}
                      onChange={(e) => updateType(type.prefix, { label: e.target.value })}
                      aria-label={`${type.prefix} label`}
                    />
                  </td>
                  <td>
                    <select
                      value={type.kind}
                      onChange={(e) =>
                        updateType(type.prefix, {
                          kind: e.target.value as CatalogCategoryType["kind"],
                        })
                      }
                      aria-label={`${type.prefix} kind`}
                    >
                      <option value="service">Service</option>
                      <option value="product">Product</option>
                    </select>
                  </td>
                  <td>
                    <input
                      type="number"
                      min={0}
                      value={type.sort}
                      onChange={(e) =>
                        updateType(type.prefix, { sort: Number(e.target.value) || 0 })
                      }
                      aria-label={`${type.prefix} sort`}
                    />
                  </td>
                  <td>
                    <input
                      type="checkbox"
                      checked={type.active !== false}
                      onChange={(e) => updateType(type.prefix, { active: e.target.checked })}
                      aria-label={`${type.prefix} active`}
                    />
                  </td>
                  <td>{used}</td>
                  <td>
                    <button
                      type="button"
                      className="secondary danger"
                      onClick={() => removeType(type.prefix)}
                      disabled={used > 0}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="home-safety-catalog-add-type">
        <input
          value={newPrefix}
          onChange={(e) => setNewPrefix(e.target.value.toUpperCase())}
          placeholder="Prefix (e.g. NUT)"
          aria-label="New type prefix"
        />
        <input
          value={newLabel}
          onChange={(e) => setNewLabel(e.target.value)}
          placeholder="Label"
          aria-label="New type label"
        />
        <select
          value={newKind}
          onChange={(e) => setNewKind(e.target.value as CatalogCategoryType["kind"])}
          aria-label="New type kind"
        >
          <option value="service">Service</option>
          <option value="product">Product</option>
        </select>
        <button type="button" className="secondary" onClick={addType}>
          + Add type
        </button>
      </div>
    </div>
  );
}
