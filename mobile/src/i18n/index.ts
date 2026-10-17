import AsyncStorage from "@react-native-async-storage/async-storage";

import { en } from "./en";
import { sw } from "./sw";

export type Locale = "en" | "sw";
export type Dict = typeof en;

const KEY = "bti_locale";
const catalogs: Record<Locale, Dict> = { en, sw };

let locale: Locale = "en";
let ready = false;

export async function initLocale(): Promise<Locale> {
  if (ready) return locale;
  try {
    const saved = await AsyncStorage.getItem(KEY);
    if (saved === "en" || saved === "sw") locale = saved;
  } catch {
    // keep default
  }
  ready = true;
  return locale;
}

export function getLocale(): Locale {
  return locale;
}

export async function setLocale(next: Locale): Promise<void> {
  locale = next;
  await AsyncStorage.setItem(KEY, next);
}

export function t(key: keyof Dict, vars?: Record<string, string | number>): string {
  const raw = catalogs[locale][key] ?? catalogs.en[key] ?? String(key);
  if (!vars) return raw;
  return Object.entries(vars).reduce(
    (s, [k, v]) => s.replace(new RegExp(`\\{${k}\\}`, "g"), String(v)),
    raw,
  );
}
