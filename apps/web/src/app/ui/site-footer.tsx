"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useI18n } from "../i18n/provider";

export function SiteFooter() {
  const { t } = useI18n();
  const pathname = usePathname();
  const top = pathname?.startsWith("/explorar") ? "#graficos" : pathname?.startsWith("/investigacion") ? "#investigacion-contenido" : "#inicio";
  return <footer id="acerca">
    <div className="wrap footer-inner">
      <div>
        <Link className="footer-brand" href="/">iyök<span>.</span></Link>
        <p>{t.footer.tagline1}<br />{t.footer.tagline2}</p>
      </div>
      <div>
        <strong>{t.footer.madeFor}</strong>
        <p>{t.footer.project1}<br />{t.footer.project2}</p>
      </div>
      <a href={top}>{t.footer.top} ↑</a>
    </div>
  </footer>;
}
