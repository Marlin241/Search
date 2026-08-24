"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { NAV_ITEMS, isNavItemActive } from "@/lib/navConfig";

export function MobileNav() {
  const pathname = usePathname();

  return (
    <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-40 flex h-16 items-center justify-around border-t border-border/80 bg-card/90 px-2 backdrop-blur-xl">
      {NAV_ITEMS.map((item) => {
        const isActive = isNavItemActive(pathname, item.href);
        const Icon = item.icon;

        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex flex-col items-center justify-center gap-1 px-3 py-1 text-[11px] font-medium transition-colors",
              isActive ? "text-primary font-bold" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Icon className="h-5 w-5" />
            <span>{item.mobileLabel}</span>
          </Link>
        );
      })}
    </nav>
  );
}
