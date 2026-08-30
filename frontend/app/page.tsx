import type { Metadata } from "next";
import { PRODUCT_NAME, TAGLINE } from "@/lib/brand";
import { MarketingHeader } from "@/components/marketing/MarketingHeader";
import { Hero } from "@/components/marketing/Hero";
import { ProblemSection } from "@/components/marketing/ProblemSection";
import { FeatureGrid } from "@/components/marketing/FeatureGrid";
import { HowItWorks } from "@/components/marketing/HowItWorks";
import { AccessSection } from "@/components/marketing/AccessSection";
import { MarketingFooter } from "@/components/marketing/MarketingFooter";

export const metadata: Metadata = {
  title: `${PRODUCT_NAME} — recherche d'emploi assistée par IA`,
  description: TAGLINE,
  robots: { index: false, follow: false },
  openGraph: {
    title: `${PRODUCT_NAME} — recherche d'emploi assistée par IA`,
    description: TAGLINE,
    type: "website",
    locale: "fr_FR",
  },
};

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      <MarketingHeader />
      <main>
        <Hero />
        <ProblemSection />
        <FeatureGrid />
        <HowItWorks />
        <AccessSection />
      </main>
      <MarketingFooter />
    </div>
  );
}
