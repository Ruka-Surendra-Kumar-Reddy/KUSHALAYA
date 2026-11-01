"use client";

import { useState } from "react";
import {
  formatInr,
  productsForPackage,
  type SafetyCatalog,
  type CatalogProduct,
} from "@/lib/livewell/catalog";
import { catalogProductImageUrls } from "@/lib/livewell/catalogImages";
import { publicBrandName } from "@/lib/public-brand";

function ProductPhotoPreview({
  product,
  tenantId,
  variant = "card",
}: {
  product: CatalogProduct;
  tenantId: number;
  variant?: "card" | "hero";
}) {
  const urls = catalogProductImageUrls(product, tenantId);
  if (urls.length === 0) {
    return (
      <div
        className={`home-safety-showcase-photo-placeholder home-safety-showcase-photo-placeholder--${variant}`}
        aria-hidden="true"
      >
        No photo
      </div>
    );
  }
  return (
    <div className={`home-safety-showcase-photo-preview home-safety-showcase-photo-preview--${variant}`}>
      <img src={urls[0]} alt="" className="home-safety-showcase-product-img" loading="lazy" />
      {urls.length > 1 ? (
        <span className="home-safety-showcase-photo-count">+{urls.length - 1}</span>
      ) : null}
    </div>
  );
}

function ProductPhotoGallery({
  product,
  tenantId,
}: {
  product: CatalogProduct;
  tenantId: number;
}) {
  const urls = catalogProductImageUrls(product, tenantId);
  const [active, setActive] = useState(0);

  if (urls.length === 0) return null;

  const safeActive = Math.min(active, urls.length - 1);

  return (
    <div className="home-safety-showcase-gallery">
      <img
        src={urls[safeActive]}
        alt=""
        className="home-safety-showcase-gallery-hero"
      />
      {urls.length > 1 ? (
        <div className="home-safety-showcase-gallery-thumbs" role="tablist" aria-label="Product photos">
          {urls.map((url, index) => (
            <button
              key={url}
              type="button"
              role="tab"
              aria-selected={index === safeActive}
              className={`home-safety-showcase-gallery-thumb${index === safeActive ? " active" : ""}`}
              onClick={() => setActive(index)}
            >
              <img src={url} alt="" />
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function ProductShowcase({
  catalog,
  tenantId,
}: {
  catalog: SafetyCatalog;
  tenantId: number;
}) {
  const [selectedPackageId, setSelectedPackageId] = useState<string | null>(
    catalog.packages.find((p) => p.highlight)?.id ?? catalog.packages[0]?.id ?? null,
  );
  const [selectedProduct, setSelectedProduct] = useState<CatalogProduct | null>(null);

  const selectedPackage = catalog.packages.find((p) => p.id === selectedPackageId) ?? null;
  const packageProducts = selectedPackage
    ? productsForPackage(catalog, selectedPackage)
    : [];

  const productsWithPhotos = catalog.products.filter(
    (p) => catalogProductImageUrls(p, tenantId).length > 0,
  ).length;

  return (
    <div className="home-safety-showcase">
      <header className="home-safety-showcase-hero">
        <p className="home-safety-showcase-eyebrow">{publicBrandName()}</p>
        <h2>Products &amp; packages</h2>
        <p className="muted">
          Tap any item to see photos and details. {productsWithPhotos > 0
            ? `${productsWithPhotos} product${productsWithPhotos === 1 ? "" : "s"} with photos.`
            : "Ask your assessor to add product photos in the catalog admin."}
        </p>
      </header>

      <div className="home-safety-showcase-packages">
        {catalog.packages.map((pkg) => (
          <button
            key={pkg.id}
            type="button"
            className={`home-safety-showcase-pkg${pkg.id === selectedPackageId ? " active" : ""}${pkg.highlight ? " popular" : ""}`}
            onClick={() => {
              setSelectedPackageId(pkg.id);
              setSelectedProduct(null);
            }}
          >
            {pkg.highlight && <span className="home-safety-showcase-popular">Popular</span>}
            <strong>{pkg.name}</strong>
            <span className="home-safety-showcase-tagline">{pkg.tagline}</span>
            <span className="home-safety-showcase-price">
              {formatInr(pkg.price_inr, pkg.price_label)}
            </span>
          </button>
        ))}
      </div>

      {selectedPackage && (
        <section className="card home-safety-showcase-detail">
          <h3>{selectedPackage.name}</h3>
          <p>{selectedPackage.description}</p>
          <p className="home-safety-showcase-price-lg">
            {formatInr(selectedPackage.price_inr, selectedPackage.price_label)}
          </p>
          <h4>What&apos;s included — tap for photos</h4>
          <div className="home-safety-showcase-includes-grid">
            {packageProducts.map((prod) => (
              <button
                key={prod.id}
                type="button"
                className="home-safety-showcase-product-card home-safety-showcase-include-card"
                onClick={() => setSelectedProduct(prod)}
              >
                <ProductPhotoPreview product={prod} tenantId={tenantId} />
                <span className="home-safety-showcase-cat">
                  {prod.product_code ? `${prod.product_code} · ` : ""}
                  {prod.category}
                </span>
                <strong>{prod.name}</strong>
                {prod.short_description ? (
                  <p className="muted">{prod.short_description}</p>
                ) : null}
                <span className="home-safety-showcase-product-price">
                  {formatInr(prod.price_inr, prod.price_label)}
                </span>
              </button>
            ))}
          </div>
        </section>
      )}

      <section className="card home-safety-showcase-all">
        <h3>All products &amp; services</h3>
        <p className="muted home-safety-showcase-all-hint">Tap a card to open photos and full description.</p>
        <div className="home-safety-showcase-product-grid">
          {catalog.products.map((prod) => (
            <button
              key={prod.id}
              type="button"
              className="home-safety-showcase-product-card"
              onClick={() => setSelectedProduct(prod)}
            >
              <ProductPhotoPreview product={prod} tenantId={tenantId} />
              <span className="home-safety-showcase-cat">
                {prod.product_code ? `${prod.product_code} · ` : ""}
                {prod.category}
              </span>
              <strong>{prod.name}</strong>
              <p className="muted">{prod.short_description}</p>
              <span className="home-safety-showcase-product-price">
                {formatInr(prod.price_inr, prod.price_label)}
              </span>
            </button>
          ))}
        </div>
      </section>

      {selectedProduct && (
        <div
          className="home-safety-showcase-modal-backdrop"
          role="presentation"
          onClick={() => setSelectedProduct(null)}
        >
          <div
            className="home-safety-showcase-modal card"
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className="home-safety-showcase-modal-close"
              onClick={() => setSelectedProduct(null)}
              aria-label="Close"
            >
              ×
            </button>
            <span className="home-safety-showcase-cat">
              {selectedProduct.product_code ? `${selectedProduct.product_code} · ` : ""}
              {selectedProduct.category}
            </span>
            <ProductPhotoGallery product={selectedProduct} tenantId={tenantId} />
            <h3>{selectedProduct.name}</h3>
            <p className="home-safety-showcase-price-lg">
              {formatInr(selectedProduct.price_inr, selectedProduct.price_label)}
            </p>
            <p>{selectedProduct.details || selectedProduct.short_description}</p>
          </div>
        </div>
      )}
    </div>
  );
}
