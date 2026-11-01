import {
  mergeMessageCatalogs,
  PLATFORM_MESSAGES,
  type Locale,
  type MessageCatalogs,
} from "@workforceos/contracts/i18n";

import { brandifyDeep } from "@/lib/brandify";
import en from "@/messages/en.json";
import te from "@/messages/te.json";

export type { Locale, MessageCatalogs };

export const LOCALE_STORAGE_KEY = "sho_admin_locale";

export const MESSAGE_CATALOGS: MessageCatalogs = {
  en: brandifyDeep(mergeMessageCatalogs(PLATFORM_MESSAGES.en, en)),
  te: brandifyDeep(mergeMessageCatalogs(PLATFORM_MESSAGES.te, te)),
};

export {
  LOCALES,
  detectInitialLocale,
  formatDateTime,
  localesForMarket,
  teluguLocaleEnabled,
  translate,
} from "@workforceos/contracts/i18n";

export type Messages = typeof en;
