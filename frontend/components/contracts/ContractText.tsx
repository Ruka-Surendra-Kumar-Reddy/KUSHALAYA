import { contractBlocks } from "@/lib/contracts";

/** Contract text as shown to staff and signers: "# " lines are headings, blank lines split paragraphs. */
export function ContractText({ title, body }: { title: string; body: string }) {
  return (
    <article className="ct-text">
      <h2 className="ct-text-title">{title}</h2>
      {contractBlocks(body).map((b, i) =>
        b.heading ? (
          <h3 key={i}>{b.text}</h3>
        ) : (
          <p key={i} className={b.text.startsWith("[PLACEHOLDER") ? "ct-placeholder-note" : undefined}>
            {b.text}
          </p>
        ),
      )}
    </article>
  );
}
