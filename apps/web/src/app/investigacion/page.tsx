import type { Metadata } from "next";
import { Research } from "../ui/research";

export const metadata: Metadata = { title: "Iyök | Open research", description: "How the Iyök series is built, what has been checked and what remains under scientific review." };
export default function ResearchPage() { return <main id="investigacion-contenido"><Research /></main>; }
