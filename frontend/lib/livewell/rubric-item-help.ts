/**
 * Assessor-facing short help for KAA checklist items (shown behind a “?”).
 * Prefers full training entries from assessor-item-training.ts.
 */

import { formatTrainingHelp, trainingForItem } from "./assessor-item-training";

export function helpForRubricItem(item: {
  id: string;
  label: string;
  help?: string;
}): string | undefined {
  const existing = item.help?.trim();
  if (existing) return existing;
  const training = trainingForItem(item.id) || trainingForItem(item.label);
  if (training) return formatTrainingHelp(training);
  return undefined;
}
