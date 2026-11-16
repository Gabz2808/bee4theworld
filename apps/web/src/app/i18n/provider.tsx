"use client";
import { createContext, useCallback, useContext, useEffect, useSyncExternalStore } from "react";
import { dictionaries, type Dictionary, type Locale } from "./dictionaries";

const storageKey = "iyok-locale";
const changeEvent = "iyok-locale-change";

// Respaldo en memoria cuando el navegador bloquea localStorage.
let memoryLocale: Locale | null = null;

function readLocale(): Locale {
  if (memoryLocale) return memoryLocale;
  try {
    const stored = window.localStorage.getItem(storageKey);
    if (stored === "es" || stored === "en") return stored;
  } catch { /* almacenamiento bloqueado */ }
  // Inglés por defecto; el español se activa con el interruptor y se recuerda.
  return "en";
}
function subscribe(callback: () => void) {
  window.addEventListener(changeEvent, callback);
  window.addEventListener("storage", callback);
  return () => { window.removeEventListener(changeEvent, callback); window.removeEventListener("storage", callback); };
}

type I18n = { locale: Locale; t: Dictionary; setLocale: (locale: Locale) => void };
const I18nContext = createContext<I18n | null>(null);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  // El servidor siempre genera inglés; el cliente aplica la preferencia guardada al hidratar.
  const locale = useSyncExternalStore(subscribe, readLocale, () => "en" as Locale);
  const setLocale = useCallback((next: Locale) => {
    try { window.localStorage.setItem(storageKey, next); memoryLocale = null; } catch { memoryLocale = next; }
    window.dispatchEvent(new Event(changeEvent));
  }, []);
  useEffect(() => {
    document.documentElement.lang = locale;
    document.title = dictionaries[locale].meta.title;
  }, [locale]);
  return <I18nContext.Provider value={{ locale, t: dictionaries[locale], setLocale }}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) throw new Error("useI18n debe usarse dentro de I18nProvider");
  return context;
}
