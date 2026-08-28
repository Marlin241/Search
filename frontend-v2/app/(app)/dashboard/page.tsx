"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Send,
  CheckCircle2,
  Activity,
  Clock,
  Plus,
  Search,
  ArrowRight,
  Sparkles,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { listApplications, listDiagnostics, getCandidateProfile } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import {
  cn,
  formatDate,
  formatRelativeTime,
  getInitials,
  statusLabel,
  statusVariant,
} from "@/lib/utils";
import type { ApplicationOut, DiagnosticReport, CandidateProfileOut } from "@/lib/types";

export default function DashboardPage() {
  const { token } = useAuth();

  const [profile, setProfile] = useState<CandidateProfileOut | null>(null);
  const [applications, setApplications] = useState<ApplicationOut[]>([]);
  const [diagnostics, setDiagnostics] = useState<DiagnosticReport[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      if (!token) return;
      setIsLoading(true);
      try {
        const [profileRes, appsRes, diagRes] = await Promise.allSettled([
          getCandidateProfile(token),
          listApplications(token),
          listDiagnostics(token),
        ]);

        if (profileRes.status === "fulfilled") setProfile(profileRes.value);
        if (appsRes.status === "fulfilled") setApplications(appsRes.value || []);
        if (diagRes.status === "fulfilled") setDiagnostics(diagRes.value || []);
      } catch (err) {
        console.error("Dashboard fetch error:", err);
      } finally {
        setIsLoading(false);
      }
    }

    fetchData();
  }, [token]);

  const totalApps = applications.length;
  const sentApps = applications.filter((a) => a.status.includes("soumise")).length;
  const avgScore =
    diagnostics.length > 0
      ? Math.round(
          diagnostics.reduce((acc, curr) => acc + curr.overall_score, 0) /
            diagnostics.length
        )
      : 0;
  const pendingApps = applications.filter(
    (a) => a.status === "a_soumettre_manuellement"
  ).length;

  const recentApps = [...applications]
    .sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    )
    .slice(0, 5);

  const recentDiags = [...diagnostics]
    .sort(
      (a, b) =>
        new Date(b.created_at || "").getTime() -
        new Date(a.created_at || "").getTime()
    )
    .slice(0, 3);

  const stats = [
    {
      label: "Total candidatures",
      value: totalApps,
      icon: Send,
      color: "text-primary",
      bg: "bg-primary/10",
    },
    {
      label: "Candidatures envoyées",
      value: sentApps,
      icon: CheckCircle2,
      color: "text-success",
      bg: "bg-success/15",
    },
    {
      label: "Score ATS moyen",
      value: diagnostics.length > 0 ? `${avgScore}%` : "—",
      icon: Activity,
      color: "text-accent-foreground",
      bg: "bg-accent/20",
    },
    {
      label: "À envoyer manuellement",
      value: pendingApps,
      icon: Clock,
      color: "text-warning-dark",
      bg: "bg-warning/20",
    },
  ];

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Hero Greeting */}
      <section className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-display font-bold text-foreground">
            Bonjour {profile?.full_name ? `${profile.full_name.split(" ")[0]} !` : "!"}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Gérez vos recherches d'emploi, diagnostiquez vos CVs et suivez vos candidatures.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/offres">
            <Button variant="secondary" icon={<Search className="w-4 h-4" />}>
              Explorer les offres
            </Button>
          </Link>
          <Link href="/diagnostic">
            <Button variant="primary" icon={<Plus className="w-4 h-4" />}>
              Nouveau diagnostic
            </Button>
          </Link>
        </div>
      </section>

      {/* Stats Cards */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08, duration: 0.3 }}
          >
            <Card className="h-full">
              <CardContent className="p-5">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    {stat.label}
                  </span>
                  <div
                    className={cn(
                      "w-8 h-8 rounded-lg flex items-center justify-center",
                      stat.bg
                    )}
                  >
                    <stat.icon className={cn("w-4 h-4", stat.color)} />
                  </div>
                </div>
                <div className="text-2xl font-bold font-display text-foreground">
                  {isLoading ? <Skeleton className="h-7 w-12" /> : stat.value}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </section>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Recent Applications */}
        <section className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold font-display">
              Candidatures récentes
            </h2>
            <Link
              href="/candidatures"
              className="text-xs font-semibold text-primary hover:underline flex items-center gap-1"
            >
              Voir tout ({totalApps}) <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <Card className="overflow-hidden">
            <div className="divide-y divide-border/60">
              {isLoading ? (
                Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="p-4 flex items-center gap-4">
                    <Skeleton className="w-10 h-10 rounded-full" />
                    <div className="space-y-2 flex-1">
                      <Skeleton className="h-4 w-1/3" />
                      <Skeleton className="h-3 w-1/4" />
                    </div>
                  </div>
                ))
              ) : recentApps.length > 0 ? (
                recentApps.map((app) => (
                  <div
                    key={app.id}
                    className="p-4 hover:bg-muted/40 transition-colors flex items-center justify-between gap-4"
                  >
                    <div className="flex items-center gap-3.5 min-w-0">
                      <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary font-bold text-xs flex items-center justify-center shrink-0">
                        {getInitials(app.company_name)}
                      </div>
                      <div className="min-w-0">
                        <h4 className="text-sm font-semibold text-foreground truncate">
                          {app.job_title}
                        </h4>
                        <p className="text-xs text-muted-foreground truncate">
                          {app.company_name} • {formatRelativeTime(app.created_at)}
                        </p>
                      </div>
                    </div>
                    <Badge variant={statusVariant(app.status)}>
                      {statusLabel(app.status)}
                    </Badge>
                  </div>
                ))
              ) : (
                <div className="p-8">
                  <EmptyState
                    title="Aucune candidature pour le moment"
                    description="Cherchez des offres qui vous correspondent et postulez en quelques clics."
                    action={
                      <Link href="/offres">
                        <Button variant="secondary" size="sm">
                          Découvrir les offres
                        </Button>
                      </Link>
                    }
                  />
                </div>
              )}
            </div>
          </Card>
        </section>

        {/* Recent Diagnostics */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold font-display">
              Derniers diagnostics
            </h2>
            <Link
              href="/diagnostic"
              className="text-xs font-semibold text-primary hover:underline flex items-center gap-1"
            >
              Nouveau <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="space-y-3">
            {isLoading ? (
              Array.from({ length: 2 }).map((_, i) => (
                <Card key={i}>
                  <CardContent className="p-4 flex items-center gap-4">
                    <Skeleton className="w-12 h-12 rounded-full" />
                    <div className="space-y-2 flex-1">
                      <Skeleton className="h-4 w-full" />
                      <Skeleton className="h-3 w-2/3" />
                    </div>
                  </CardContent>
                </Card>
              ))
            ) : recentDiags.length > 0 ? (
              recentDiags.map((diag, index) => (
                <Card key={diag.id ?? index} className="hover:border-primary/40 transition-colors">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-4">
                      <ScoreRing score={diag.overall_score} size="sm" />
                      <div className="space-y-1 flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-foreground">
                            Score global
                          </span>
                          <span className="text-[10px] text-muted-foreground">
                            {formatDate(diag.created_at)}
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground line-clamp-1">
                          {diag.recommendations?.[0] || "Diagnostic complété"}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
            ) : (
              <Card>
                <CardContent className="p-6 text-center space-y-3">
                  <div className="mx-auto w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary">
                    <Sparkles className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-foreground">
                      Testez la compatibilité de votre CV
                    </p>
                    <p className="text-[11px] text-muted-foreground mt-1">
                      Analysez votre CV face à une offre pour obtenir des recommandations IA.
                    </p>
                  </div>
                  <Link href="/diagnostic" className="block">
                    <Button variant="outline" size="sm" fullWidth>
                      Lancer une analyse
                    </Button>
                  </Link>
                </CardContent>
              </Card>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
