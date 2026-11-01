import {
  RUBRIC_SOURCES,
  rubricSourceLabel,
  type RubricItemSource,
} from "@/lib/livewell/rubric-sources";

export function RubricSourceBadge({
  source = "safehome360",
  title,
}: {
  source?: RubricItemSource;
  title?: string;
}) {
  const meta = RUBRIC_SOURCES[source ?? "safehome360"];
  return (
    <span
      className={`home-safety-source-badge home-safety-source-${source ?? "safehome360"}`}
      title={title ?? `${meta.label} — ${meta.description}`}
    >
      {rubricSourceLabel(source)}
    </span>
  );
}
