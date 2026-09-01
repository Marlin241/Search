import Link from "next/link";
import { Logo } from "@/components/common/Logo";

export function MarketingHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
        <Logo />
        <nav className="flex items-center gap-2 sm:gap-3">
          <Link
            href="/login"
            className="rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground"
          >
            Se connecter
          </Link>
          <a
            href="#acces"
            className="rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground shadow-soft hover:bg-primary-600"
          >
            Demander un accès
          </a>
        </nav>
      </div>
    </header>
  );
}
