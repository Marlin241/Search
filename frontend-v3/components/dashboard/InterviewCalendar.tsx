"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, MapPin } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { Dialog } from "@/components/ui/Dialog";
import { CalendarLegend, INTERVIEW_TYPE_COLORS, INTERVIEW_TYPE_LABELS } from "@/components/dashboard/CalendarLegend";
import { getDashboardCalendar } from "@/lib/api";
import { isSafeHttpUrl } from "@/lib/utils";
import type { InterviewCalendarEntryOut } from "@/lib/types";

const WEEKDAY_LABELS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];

function monthLabel(year: number, month: number): string {
  return new Date(year, month - 1, 1).toLocaleDateString("fr-FR", {
    month: "long",
    year: "numeric",
  });
}

/** Days shown in the grid, including the leading/trailing days from
 * adjacent months needed to fill full weeks (Monday-first). */
function buildGridDays(year: number, month: number): { date: Date; inMonth: boolean }[] {
  const firstOfMonth = new Date(year, month - 1, 1);
  const firstWeekday = (firstOfMonth.getDay() + 6) % 7; // 0 = Monday
  const daysInMonth = new Date(year, month, 0).getDate();

  const days: { date: Date; inMonth: boolean }[] = [];
  for (let i = firstWeekday; i > 0; i--) {
    days.push({ date: new Date(year, month - 1, 1 - i), inMonth: false });
  }
  for (let d = 1; d <= daysInMonth; d++) {
    days.push({ date: new Date(year, month - 1, d), inMonth: true });
  }
  while (days.length % 7 !== 0) {
    const last = days[days.length - 1].date;
    days.push({ date: new Date(last.getFullYear(), last.getMonth(), last.getDate() + 1), inMonth: false });
  }
  return days;
}

function dateKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function InterviewCalendar({ token }: { token: string }) {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [entries, setEntries] = useState<InterviewCalendarEntryOut[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selected, setSelected] = useState<InterviewCalendarEntryOut | null>(null);

  useEffect(() => {
    setIsLoading(true);
    const monthParam = `${year}-${String(month).padStart(2, "0")}`;
    getDashboardCalendar(token, monthParam)
      .then(setEntries)
      .catch(() => setEntries([]))
      .finally(() => setIsLoading(false));
  }, [token, year, month]);

  const days = useMemo(() => buildGridDays(year, month), [year, month]);
  const entriesByDay = useMemo(() => {
    const map = new Map<string, InterviewCalendarEntryOut[]>();
    for (const entry of entries) {
      const key = dateKey(new Date(entry.scheduled_at));
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(entry);
    }
    return map;
  }, [entries]);

  const goToPrevMonth = () => {
    if (month === 1) {
      setYear((y) => y - 1);
      setMonth(12);
    } else {
      setMonth((m) => m - 1);
    }
  };
  const goToNextMonth = () => {
    if (month === 12) {
      setYear((y) => y + 1);
      setMonth(1);
    } else {
      setMonth((m) => m + 1);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-foreground capitalize">{monthLabel(year, month)}</h3>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" onClick={goToPrevMonth} aria-label="Mois précédent">
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="sm" onClick={goToNextMonth} aria-label="Mois suivant">
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </div>

      <CalendarLegend />

      {isLoading ? (
        <Skeleton className="h-80 w-full rounded-xl" />
      ) : (
        <div className="rounded-xl border border-border overflow-hidden">
          <div className="grid grid-cols-7 bg-muted/40 text-xs font-semibold text-muted-foreground">
            {WEEKDAY_LABELS.map((label) => (
              <div key={label} className="p-2 text-center">
                {label}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-7">
            {days.map(({ date, inMonth }) => {
              const key = dateKey(date);
              const dayEntries = entriesByDay.get(key) ?? [];
              return (
                <div
                  key={key}
                  className={`min-h-[80px] border-t border-l border-border p-1.5 space-y-1 ${
                    inMonth ? "" : "bg-muted/10 text-muted-foreground/50"
                  }`}
                >
                  <span className="text-xs font-medium">{date.getDate()}</span>
                  {dayEntries.map((entry) => (
                    <button
                      key={entry.id}
                      type="button"
                      onClick={() => setSelected(entry)}
                      className={`w-full text-left rounded-md border px-1.5 py-0.5 text-[10px] font-medium truncate block ${INTERVIEW_TYPE_COLORS[entry.interview_type]}`}
                      title={`${entry.company_name} — ${entry.job_title}`}
                    >
                      {entry.company_name}
                    </button>
                  ))}
                </div>
              );
            })}
          </div>
        </div>
      )}

      <Dialog
        isOpen={!!selected}
        onClose={() => setSelected(null)}
        title={selected ? `Entretien ${INTERVIEW_TYPE_LABELS[selected.interview_type]}` : undefined}
        description={selected ? `${selected.job_title} chez ${selected.company_name}` : undefined}
      >
        {selected && (
          <div className="space-y-2 mt-2 text-sm">
            <p className="text-muted-foreground">
              {new Date(selected.scheduled_at).toLocaleString("fr-FR", {
                dateStyle: "full",
                timeStyle: "short",
              })}
            </p>
            {selected.location_or_link && (
              <p className="flex items-center gap-1.5 text-foreground">
                <MapPin className="w-4 h-4 shrink-0 text-muted-foreground" />
                {isSafeHttpUrl(selected.location_or_link) ? (
                  <a
                    href={selected.location_or_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline break-all"
                  >
                    {selected.location_or_link}
                  </a>
                ) : (
                  <span className="break-all">{selected.location_or_link}</span>
                )}
              </p>
            )}
            {selected.notes && (
              <p className="text-muted-foreground whitespace-pre-wrap">{selected.notes}</p>
            )}
          </div>
        )}
      </Dialog>
    </div>
  );
}
