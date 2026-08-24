import {
  LayoutDashboard,
  Search,
  Send,
  FileCheck2,
  UserCheck,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  mobileLabel: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Tableau de bord", mobileLabel: "Accueil", icon: LayoutDashboard },
  { href: "/offres", label: "Offres d'emploi", mobileLabel: "Offres", icon: Search },
  { href: "/candidatures", label: "Mes candidatures", mobileLabel: "Suivi", icon: Send },
  { href: "/diagnostic", label: "Diagnostic ATS", mobileLabel: "ATS", icon: FileCheck2 },
  { href: "/profil", label: "Mon profil", mobileLabel: "Profil", icon: UserCheck },
];

export function isNavItemActive(pathname: string, href: string): boolean {
  return pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
}
