import {
  LayoutDashboard,
  Search,
  FileCheck2,
  UserCheck,
  Shield,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  mobileLabel: string;
  icon: LucideIcon;
}

// "Mes candidatures" (flat list) was retired in favor of the dashboard's
// Kanban board (Phase 7) - /candidatures now just redirects to /dashboard
// for old links/bookmarks, so it no longer needs its own nav entry.
export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Tableau de bord", mobileLabel: "Accueil", icon: LayoutDashboard },
  { href: "/offres", label: "Offres d'emploi", mobileLabel: "Offres", icon: Search },
  { href: "/diagnostic", label: "Diagnostic ATS", mobileLabel: "ATS", icon: FileCheck2 },
  { href: "/profil", label: "Mon profil", mobileLabel: "Profil", icon: UserCheck },
];

// Shown in the sidebar/mobile nav only when the current user has `is_admin`.
export const ADMIN_NAV_ITEM: NavItem = {
  href: "/admin",
  label: "Admin",
  mobileLabel: "Admin",
  icon: Shield,
};

export function isNavItemActive(pathname: string, href: string): boolean {
  return pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
}
