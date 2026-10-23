/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useMemo, useSyncExternalStore } from "react";
import { SUPPORTED_LANGUAGES, LANGUAGE_STORAGE_KEY } from "../constants/language";
import { i18nInstance } from "../core";
import type { TLanguage, ILanguageOption } from "../types";

export type TTranslationStore = {
  t: (key: string, params?: Record<string, unknown>) => string;
  currentLocale: TLanguage;
  changeLanguage: (lng: TLanguage) => void;
  languages: ILanguageOption[];
};

// Crash guard: i18next-icu unconditionally returns raw objects when t() is called
// with a branch (namespace-node) key, regardless of returnObjects:false. Without
// this wrapper, React unmounts the subtree with "Objects are not valid as a React
// child". Strings pass through; numbers/booleans are stringified; objects/null/
// undefined fall back to the key itself plus a dev-mode warning. Can be removed
// once t() gains key-level type safety (Phase 2 of the i18n roadmap).
function coerceToString(key: string, value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (process.env.NODE_ENV !== "production") {
    // eslint-disable-next-line no-console
    console.warn(
      `[i18n] Translation for key "${key}" is not a string (got ${
        value === null ? "null" : typeof value
      }). This is likely a missing key or a namespace-node lookup. Returning the key as fallback.`
    );
  }
  return key;
}

// What the translations depend on changes rarely: the language, or translations added later. react-i18next's
// hook gave each component a copy of the i18n instance and its own subscription to it, which was a large part of
// the first render of a list of work items; here every user of the hook shares one subscription, and renders anew
// when the language or the translations change. The instance has every namespace loaded before the app hydrates
// (see core/instance.ts and entry.client).
let revision = 0;
const listeners = new Set<() => void>();
const notifyChange = () => {
  revision += 1;
  listeners.forEach((listener) => listener());
};
const subscribeToChanges = (listener: () => void) => {
  if (listeners.size === 0) {
    i18nInstance.on("languageChanged", notifyChange);
    i18nInstance.store.on("added", notifyChange);
  }
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) {
      i18nInstance.off("languageChanged", notifyChange);
      i18nInstance.store.off("added", notifyChange);
    }
  };
};
const getRevision = () => revision;

export function useTranslation(): TTranslationStore {
  // No namespace arg — fallbackNS in the i18next config ensures all namespaces
  // are searched for any key.
  const currentRevision = useSyncExternalStore(subscribeToChanges, getRevision, getRevision);
  const i18n = i18nInstance;

  const changeLanguage = useCallback(
    (lng: TLanguage) => {
      void (async () => {
        try {
          await i18n.changeLanguage(lng);
          if (typeof window === "undefined") return;
          localStorage.setItem(LANGUAGE_STORAGE_KEY, lng);
          document.documentElement.lang = lng;
        } catch (err) {
          console.error("Failed to change language:", err);
        }
      })();
    },
    [i18n]
  );

  const t = useMemo(
    () => (key: string, params?: Record<string, unknown>) =>
      coerceToString(key, params === undefined ? i18n.t(key) : i18n.t(key, params)),
    // a new t when the translations change, so that what a component memoized with it is translated anew
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [i18n, currentRevision]
  );

  return {
    t,
    currentLocale: i18n.language as TLanguage,
    changeLanguage,
    languages: SUPPORTED_LANGUAGES,
  };
}
