"use client";
import { useI18n } from "./provider";

export function LanguageToggle() {
  const { locale, t, setLocale } = useI18n();
  return <button type="button" className="language-toggle" onClick={() => setLocale(locale === "es" ? "en" : "es")} aria-label={t.language.switchTo} title={t.language.switchTo}>
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 5h9M8.5 3v2M11 5c-.8 4-3.3 7.3-7 9M6.5 9c1 2 2.7 3.8 5 5" />
      <path d="m13 21 4-9 4 9M14.4 18h5.2" />
    </svg>
    <span lang={t.language.targetLang}>{t.language.targetCode}</span>
  </button>;
}
