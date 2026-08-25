"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Send, CheckCircle2, Activity, Clock, Plus, Search } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { listApplications, listDiagnostics, getCandidateProfile } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { KanbanBoard } from "@/components/dashboard/KanbanBoard";
import { InterviewCalendar } from "@/components/dashboard/InterviewCalendar";
import { cn } from "@/lib/utils";
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
            Suivez vos candidatures de la sauvegarde à la décision, et vos entretiens à venir.
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

      {/* Kanban board */}
      <section className="space-y-4">
        <h2 className="text-lg font-bold font-display">Suivi des candidatures</h2>
        {token && <KanbanBoard token={token} />}
      </section>

      {/* Interview calendar */}
      <section className="space-y-4">
        <h2 className="text-lg font-bold font-display">Calendrier des entretiens</h2>
        <Card className="p-4">{token && <InterviewCalendar token={token} />}</Card>
      </section>
    </div>
  );
}
