"use client";

import { publicBrandName } from "@/lib/public-brand";

export function RecommendationChatLaunchCard({ assessmentId }: { assessmentId: string }) {
  const href = `/kushalaya/assess/${assessmentId}/recommendations`;

  return (
    <section
      className="card home-safety-section home-safety-rec-chat-launch"
      aria-labelledby="rec-chat-launch-heading"
    >
      <h2 id="rec-chat-launch-heading">AI recommendation chat</h2>
      <p className="muted home-safety-section-hint" id="rec-chat-launch-hint">
        Ask for product and solution recommendations grounded in this assessment and your{" "}
        {publicBrandName()} catalog. Suggestions are validated against allowlisted IDs — verify on
        site before quoting.
      </p>
      <div className="home-safety-viz-launch-actions">
        <a
          href={href}
          className="primary home-safety-viz-launch-primary"
          aria-describedby="rec-chat-launch-hint"
        >
          Open recommendation chat
        </a>
      </div>
    </section>
  );
}
