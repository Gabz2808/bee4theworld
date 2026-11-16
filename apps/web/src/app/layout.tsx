import type { Metadata } from "next";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";
import { I18nProvider } from "./i18n/provider";
import { SiteHeader } from "./ui/site-header";
import { SiteFooter } from "./ui/site-footer";

export const metadata: Metadata = { title: "Iyök | Explore Earth's changes", description: "Explore Earth system trends, backed by evidence." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" data-scroll-behavior="smooth"><body><I18nProvider><SiteHeader />{children}<SiteFooter /></I18nProvider></body></html>;
}
