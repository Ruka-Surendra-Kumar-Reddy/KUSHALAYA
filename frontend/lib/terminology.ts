export {
  demandEntityLabel,
  demandEntityPluralLabel,
  isHousekeepingVertical,
  shiftLabel,
  supplyEntityLabel,
  supplyEntityPluralLabel,
} from "@workforceos/contracts/shell";

import { formatMoney, marketMeta } from "@workforceos/contracts/client";

export { formatMoney, marketMeta };

export function marketCurrency(market?: string | null): string {
  return marketMeta(market).currency;
}
