import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "Iyök | Explora el cambio", description: "Explora tendencias del sistema terrestre con evidencia." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="es"><body>{children}</body></html>;
}
