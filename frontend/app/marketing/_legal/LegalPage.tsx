import { Children, Fragment, cloneElement, isValidElement, type ReactElement, type ReactNode } from "react";
import { MarketingShell } from "@/components/marketing/MarketingShell";
import { LEGAL_ENTITY_NAME, publicBrandName } from "@/lib/public-brand";
import "../legal.css";

export const LEGAL_UPDATED = "11 October 2026";
export const LEGAL_EMAIL = "contact@kushalaya.com";

/** A fact the owner still has to fill in; shown highlighted so it is never mistaken for real. */
export function Todo({ children }: { children: ReactNode }) {
  return <span className="lg-todo">[{children} — to be added]</span>;
}

export function Mail() {
  return <a href={`mailto:${LEGAL_EMAIL}`}>{LEGAL_EMAIL}</a>;
}

export function brand() {
  return publicBrandName();
}

export { LEGAL_ENTITY_NAME };

function headingText(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(headingText).join("");
  if (isValidElement(node)) return headingText((node.props as { children?: ReactNode }).children);
  return "";
}

/** Gives every top-level <h2> an id and returns the list for the contents box. */
function withSectionIds(children: ReactNode): { body: ReactNode[]; toc: { id: string; label: string }[] } {
  const toc: { id: string; label: string }[] = [];
  const flat = Children.toArray(children).flatMap((c) =>
    isValidElement(c) && c.type === Fragment
      ? Children.toArray((c.props as { children?: ReactNode }).children)
      : [c],
  );
  const body = flat.map((c) => {
    if (!isValidElement(c) || c.type !== "h2") return c;
    const el = c as ReactElement<{ id?: string; children?: ReactNode }>;
    const label = headingText(el.props.children).trim();
    const id = el.props.id || `s-${toc.length + 1}`;
    toc.push({ id, label });
    return cloneElement(el, { id });
  });
  return { body, toc };
}

export function LegalPage({ title, children }: { title: string; children: ReactNode }) {
  const { body, toc } = withSectionIds(children);
  return (
    <MarketingShell>
      <div className="lg-page">
        <article className="lg-doc">
          <p className="mk-eyebrow">Legal</p>
          <h1>{title}</h1>
          <p className="lg-updated">Last updated: {LEGAL_UPDATED}</p>
          {toc.length > 3 ? (
            <nav className="lg-toc" aria-label="Contents">
              <p>Contents</p>
              <ol>
                {toc.map((t) => (
                  <li key={t.id}>
                    <a href={`#${t.id}`}>{t.label.replace(/^\d+\.\s*/, "")}</a>
                  </li>
                ))}
              </ol>
            </nav>
          ) : null}
          {body}
        </article>
      </div>
    </MarketingShell>
  );
}
