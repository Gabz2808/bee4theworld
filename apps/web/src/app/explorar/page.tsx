import type { Metadata } from "next";
import { Explorer } from "../ui/explorer";

export const metadata: Metadata = { title: "Iyök | Charts & series", description: "Monthly IMERG precipitation series for mainland Costa Rica, with maps, coverage and provenance." };
export default function ChartsPage() { return <Explorer />; }
