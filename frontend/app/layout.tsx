import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Diagnostic ATS",
  description: "Comprendre pourquoi votre CV est mal traité par les ATS.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="min-h-screen bg-slate-50 text-slate-900">{children}</body>
    </html>
  );
}
