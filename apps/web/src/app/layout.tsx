import type { Metadata } from "next";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";
import { I18nProvider } from "./i18n/provider";

export const metadata: Metadata = { title: "Iyök | Explore Earth's changes", description: "Explore Earth system trends, backed by evidence." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><I18nProvider>{children}</I18nProvider></body></html>;
}
