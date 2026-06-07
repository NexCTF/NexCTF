import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { BarChart2, ChevronRight, Trophy } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { StatCard } from "@/components/stat-card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  type AdminStats,
  type ChallengeStats,
  getAdminAllChallengeStats,
  getAdminStats,
  type QuestionStats,
} from "@/lib/api";

export const Route = createFileRoute("/admin/_admin/")({
  component: Dashboard,
});

function SolveRateBar({ solved, attempted }: { solved: number; attempted: number }) {
  const pct = attempted > 0 ? Math.round((solved / attempted) * 100) : 0;
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full bg-primary transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs tabular-nums text-muted-foreground w-8 text-right">{pct}%</span>
    </div>
  );
}

// ── Question detail dialog ────────────────────────────────────────────────────

function QuestionDetailDialog({
  challenge,
  open,
  onClose,
}: {
  challenge: ChallengeStats;
  open: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation();

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{challenge.challenge_title}</DialogTitle>
        </DialogHeader>

        {challenge.first_blood_team_name && (
          <div className="rounded-lg border px-4 py-2.5 flex items-center gap-2 text-sm">
            <Trophy className="size-3.5 text-amber-500 shrink-0" />
            <span className="text-muted-foreground">
              {t("admin.dashboard.col_first_blood", {
                defaultValue: "First Blood",
              })}
              :
            </span>
            <span className="font-medium">{challenge.first_blood_team_name}</span>
            {challenge.first_blood_at && (
              <span className="text-muted-foreground text-xs ml-auto">
                {new Date(challenge.first_blood_at).toLocaleString()}
              </span>
            )}
          </div>
        )}

        {/* Per-question table */}
        {challenge.questions.length > 0 && (
          <div className="rounded-lg border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-4 py-2.5 text-left text-muted-foreground font-medium">
                    {t("admin.dashboard.col_question", {
                      defaultValue: "Question",
                    })}
                  </th>
                  <th className="px-4 py-2.5 text-center text-muted-foreground font-medium w-24">
                    {t("admin.dashboard.col_attempted", {
                      defaultValue: "Attempted",
                    })}
                  </th>
                  <th className="px-4 py-2.5 text-center text-muted-foreground font-medium w-24">
                    {t("admin.dashboard.col_solved", {
                      defaultValue: "Solved",
                    })}
                  </th>
                  <th className="px-4 py-2.5 text-left text-muted-foreground font-medium w-32">
                    {t("admin.dashboard.col_solve_rate", {
                      defaultValue: "Solve Rate",
                    })}
                  </th>
                  <th className="px-4 py-2.5 text-center text-muted-foreground font-medium w-28">
                    {t("admin.dashboard.col_hints", {
                      defaultValue: "Hints",
                    })}
                  </th>
                  <th className="px-4 py-2.5 text-left text-muted-foreground font-medium">
                    {t("admin.dashboard.col_first_blood", {
                      defaultValue: "First Blood",
                    })}
                  </th>
                </tr>
              </thead>
              <tbody>
                {challenge.questions.map((q: QuestionStats) => (
                  <tr key={q.question_id} className="border-b last:border-0">
                    <td className="px-4 py-3 font-medium">{q.question_label}</td>
                    <td className="px-4 py-3 text-center tabular-nums">
                      {q.teams_attempted > 0 ? (
                        q.teams_attempted
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center tabular-nums">
                      {q.teams_solved > 0 ? (
                        <span className="text-green-600 dark:text-green-400 font-medium">
                          {q.teams_solved}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <SolveRateBar solved={q.teams_solved} attempted={q.teams_attempted} />
                    </td>
                    <td className="px-4 py-3 text-center tabular-nums">
                      {q.hint_unlock_count > 0 ? (
                        <span className="text-amber-600 dark:text-amber-400">
                          {q.hint_unlock_count}
                          {q.hint_cost_spent > 0 && (
                            <span className="text-muted-foreground text-xs ml-1">
                              (-{q.hint_cost_spent}pt)
                            </span>
                          )}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {q.first_blood_team_name ? (
                        <div className="flex items-center gap-1.5">
                          <Trophy className="size-3 text-amber-500 shrink-0" />
                          <span className="font-medium truncate">{q.first_blood_team_name}</span>
                          {q.first_blood_at && (
                            <span className="text-muted-foreground text-xs whitespace-nowrap">
                              {new Date(q.first_blood_at).toLocaleString()}
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ── Per-challenge stats table ─────────────────────────────────────────────────

function ChallengeStatsTable({
  data,
  onRowClick,
}: {
  data: ChallengeStats[];
  onRowClick: (cs: ChallengeStats) => void;
}) {
  const { t } = useTranslation();
  const sorted = [...data].sort((a, b) => b.teams_attempted - a.teams_attempted);

  return (
    <div className="rounded-lg border overflow-hidden">
      <table className="w-full text-sm">
        <thead className="border-b bg-muted/40">
          <tr>
            <th className="px-4 py-2.5 text-left text-muted-foreground font-medium">
              {t("admin.dashboard.col_challenge", {
                defaultValue: "Challenge",
              })}
            </th>
            <th className="px-4 py-2.5 text-center text-muted-foreground font-medium w-28">
              {t("admin.dashboard.col_attempted", {
                defaultValue: "Attempted",
              })}
            </th>
            <th className="px-4 py-2.5 text-center text-muted-foreground font-medium w-28">
              {t("admin.dashboard.col_solved", { defaultValue: "Solved" })}
            </th>
            <th className="px-4 py-2.5 text-left text-muted-foreground font-medium w-36">
              {t("admin.dashboard.col_solve_rate", {
                defaultValue: "Solve Rate",
              })}
            </th>
            <th className="px-4 py-2.5 text-center text-muted-foreground font-medium w-28">
              {t("admin.dashboard.col_attempts", { defaultValue: "Attempts" })}
            </th>
            <th className="px-4 py-2.5 text-center text-muted-foreground font-medium w-28">
              {t("admin.dashboard.col_hints", { defaultValue: "Hints" })}
            </th>
            <th className="px-4 py-2.5 text-left text-muted-foreground font-medium">
              {t("admin.dashboard.col_first_blood", {
                defaultValue: "First Blood",
              })}
            </th>
            <th className="w-8" />
          </tr>
        </thead>
        <tbody className="divide-y">
          {sorted.map((cs) => (
            <tr
              key={cs.challenge_id}
              className="group transition-colors cursor-pointer hover:bg-accent/60 border-l-2 border-l-transparent hover:border-l-primary"
              onClick={() => onRowClick(cs)}
            >
              <td className="px-4 py-3 font-medium">{cs.challenge_title}</td>
              <td className="px-4 py-3 text-center tabular-nums">
                {cs.teams_attempted > 0 ? (
                  cs.teams_attempted
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </td>
              <td className="px-4 py-3 text-center tabular-nums">
                {cs.teams_solved > 0 ? (
                  <span className="text-green-600 dark:text-green-400 font-medium">
                    {cs.teams_solved}
                  </span>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </td>
              <td className="px-4 py-3">
                <SolveRateBar solved={cs.teams_solved} attempted={cs.teams_attempted} />
              </td>
              <td className="px-4 py-3 text-center tabular-nums text-muted-foreground">
                {cs.attempt_count > 0 ? cs.attempt_count : <span>—</span>}
              </td>
              <td className="px-4 py-3 text-center tabular-nums">
                {cs.hint_unlock_count > 0 ? (
                  <span className="text-amber-600 dark:text-amber-400">{cs.hint_unlock_count}</span>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </td>
              <td className="px-4 py-3">
                {cs.first_blood_team_name ? (
                  <div className="flex items-center gap-1.5">
                    <Trophy className="size-3 text-amber-500 shrink-0" />
                    <span className="font-medium truncate">{cs.first_blood_team_name}</span>
                    {cs.first_blood_at && (
                      <span className="text-muted-foreground text-xs whitespace-nowrap ml-1">
                        {new Date(cs.first_blood_at).toLocaleString()}
                      </span>
                    )}
                  </div>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </td>
              <td className="px-3 py-3 w-8 text-muted-foreground/30 group-hover:text-primary transition-colors">
                <ChevronRight className="size-4 transition-transform group-hover:translate-x-0.5" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Global counters ───────────────────────────────────────────────────────────

function GlobalStats({ stats }: { stats: AdminStats }) {
  const { t } = useTranslation();
  const successRate =
    stats.submissions > 0
      ? `${Math.round((stats.correct_submissions / stats.submissions) * 100)}%`
      : "—";
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      <StatCard
        label={t("admin.dashboard.stat_users", { defaultValue: "Users" })}
        value={stats.users}
      />
      <StatCard
        label={t("admin.dashboard.stat_teams", { defaultValue: "Teams" })}
        value={stats.teams}
      />
      <StatCard
        label={t("admin.dashboard.stat_challenges", { defaultValue: "Challenges" })}
        value={stats.challenges}
      />
      <StatCard
        label={t("admin.dashboard.stat_submissions", { defaultValue: "Submissions" })}
        value={
          <span>
            {stats.submissions}
            <span className="text-sm font-normal text-muted-foreground ml-2">{successRate}</span>
          </span>
        }
      />
      <StatCard
        label={t("admin.dashboard.stat_hint_unlocks", { defaultValue: "Hint Unlocks" })}
        value={stats.hint_unlocks}
      />
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function Dashboard() {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<ChallengeStats | null>(null);

  const { data: globalStats, isLoading: globalLoading } = useQuery<AdminStats>({
    queryKey: ["admin", "stats", "global"],
    queryFn: getAdminStats,
  });

  const { data: challengeStats, isLoading: challengeLoading } = useQuery<ChallengeStats[]>({
    queryKey: ["admin", "stats", "challenges"],
    queryFn: getAdminAllChallengeStats,
  });

  return (
    <div className="p-8 space-y-8">
      <h1 className="text-2xl font-bold">
        {t("admin.nav.dashboard", { defaultValue: "Dashboard" })}
      </h1>

      {/* Global counters */}
      {globalLoading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {[...Array(5)].map((_, i) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton placeholders
            <div key={i} className="rounded-lg border p-4 h-20 bg-muted/30 animate-pulse" />
          ))}
        </div>
      ) : globalStats ? (
        <GlobalStats stats={globalStats} />
      ) : null}

      {/* Per-challenge stats */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <BarChart2 className="size-5 text-muted-foreground" />
          <h2 className="text-base font-semibold">
            {t("admin.dashboard.challenges_section", {
              defaultValue: "Challenge Stats",
            })}
          </h2>
        </div>

        {challengeLoading ? (
          <div className="rounded-lg border h-48 bg-muted/30 animate-pulse" />
        ) : challengeStats && challengeStats.length > 0 ? (
          <ChallengeStatsTable data={challengeStats} onRowClick={setSelected} />
        ) : (
          <p className="text-sm text-muted-foreground">
            {t("admin.dashboard.no_challenges", {
              defaultValue: "No challenges yet.",
            })}
          </p>
        )}
      </div>

      {/* Question drill-down dialog */}
      {selected && (
        <QuestionDetailDialog
          challenge={selected}
          open={selected !== null}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
