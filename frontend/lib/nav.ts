export type { NavGroup, NavItem } from "@workforceos/contracts/shell";
export {
  buildWorkforceTabs,
  workforceTabFromParam,
  WORKFORCE_TAB_IDS,
  type WorkforceTabId,
} from "@workforceos/contracts/shell";

/** @deprecated Static English nav — use buildAdminNavGroups() with i18n instead. */
export const ADMIN_NAV_GROUPS = [] as const;
