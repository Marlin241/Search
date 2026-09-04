import type { Metadata } from "next";
import { Inter, Outfit } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";
import { ThemeProvider } from "@/context/ThemeContext";
import { Providers } from "@/app/providers";
import { PRODUCT_NAME, TAGLINE, SITE_URL } from "@/lib/brand";

// Runs before hydration to apply the stored/system theme immediately -
// without it, the page would flash light before React mounts and syncs
// ThemeContext's state to whatever this script already set on <html>.
const THEME_INIT_SCRIPT = `
(function () {
  try {
    var stored = localStorage.getItem("search-theme");
    var isDark = stored === "dark" || (stored !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    if (isDark) document.documentElement.classList.add("dark");
  } catch (e) {}
})();
`;

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: `${PRODUCT_NAME} — recherche d'emploi assistée par IA`,
  description: TAGLINE,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="fr"
      className={`${inter.variable} ${outfit.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="min-h-screen bg-background font-sans antialiased">
        <ThemeProvider>
          <Providers>
            <AuthProvider>{children}</AuthProvider>
          </Providers>
        </ThemeProvider>
        {/* SVG gradients for score rings (global defs) */}
        <svg className="absolute h-0 w-0" aria-hidden="true">
          <defs>
            <linearGradient id="scoreGradientHigh" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#10b981" />
              <stop offset="100%" stopColor="#34d399" />
            </linearGradient>
            <linearGradient id="scoreGradientMedium" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#f59e0b" />
              <stop offset="100%" stopColor="#fbbf24" />
            </linearGradient>
            <linearGradient id="scoreGradientLow" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#ef4444" />
              <stop offset="100%" stopColor="#f87171" />
            </linearGradient>
          </defs>
        </svg>
      </body>
    </html>
  );
}
