"use client";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LanguageToggle } from "../i18n/language-toggle";
import { useI18n } from "../i18n/provider";

// Encabezado compartido por la landing (/), la investigación (/investigacion) y gráficos y series (/explorar).
export function SiteHeader() {
  const { t } = useI18n();
  const pathname = usePathname();
  const onCharts = pathname?.startsWith("/explorar");
  const onResearch = pathname?.startsWith("/investigacion");
  return <>
    <a className="skip-link" href={onCharts ? "#graficos" : onResearch ? "#investigacion-contenido" : "#inicio"}>{t.header.skip}</a>
    <header className="topbar">
      <Link className="brand" href="/" aria-label={t.header.home}><span className="brand-symbol iyok-symbol" aria-hidden="true"><Image src="/iyok-logo.jpg" alt="" width={160} height={100} priority /></span><span>Iyök</span></Link>
      <nav aria-label={t.header.nav}>
        <Link href="/" aria-current={!onCharts && !onResearch ? "page" : undefined}>{t.header.home_link}</Link>
        <Link href="/investigacion" aria-current={onResearch ? "page" : undefined}>{t.header.research}</Link>
        <Link href="/explorar" aria-current={onCharts ? "page" : undefined}>{t.header.charts}</Link>
        <a href="#acerca">{t.header.about}</a>
      </nav>
      <LanguageToggle />
      <a className="header-team" href="https://github.com/Gabz2808/bee4theworld" target="_blank" rel="noopener noreferrer" aria-label={t.header.teamLabel}><span className="brand-symbol team-symbol" aria-hidden="true"><Image src="/bee4theworld-logo.jpg" alt="" width={100} height={75} priority /></span><span><small>{t.header.teamBy}</small><strong>Bee4TheWorld</strong></span></a>
    </header>
  </>;
}
