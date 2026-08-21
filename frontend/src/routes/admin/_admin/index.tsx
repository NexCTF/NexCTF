import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { LayoutDashboard, Trophy } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { type Column, DataTable, type TableState, useTableState } from "@/components/data-table";
import { InfoRow } from "@/components/detail-page";
import { PageHeader } from "@/components/page-header";
import { RankBadge } from "@/components/scoreboard";
import { StatCard } from "@/components/stat-card";
import { ChallengeLink, DateCell, EmptyCell, TeamLink } from "@/components/table-cells";
import { TagBadge } from "@/components/tag-badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  type AdminScoreboard,
  type AdminStats,
  type ChallengeStats,
  getAdminAllChallengeStats,
  getAdminScoreboard,
  getAdminStats,
  type PaginatedResponse,
  type QuestionStats,
} from "@/lib/api";

export const Route = createFileRoute("/admin/_admin/")({
  component: Dashboard,
});

function percent(part: number, total: number) {
  return total > 0 ? Math.round((part / total) * 100) : 0;
}

function ProgressBar({ value }: { value: number }) {
  return (
    <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden min-w-8">
      <div
        className="h-full rounded-full bg-primary transition-all"
        style={{ width: `${value}%` }}
      />
    </div>
  );
}

/** Share of all teams that solved, as a bar plus its two raw numbers. */
function SolvedByTeams({ solved, teams }: { solved: number; teams: number }) {
  const pct = percent(solved, teams);
  return (
    <div className="flex items-center gap-2">
      <span className="tabular-nums text-xs w-14 shrink-0">
        {solved > 0 ? (
          <span className="text-green-600 dark:text-green-400 font-medium">{solved}</span>
        ) : (
          <span className="text-muted-foreground">0</span>
        )}
        <span className="text-muted-foreground"> / {teams}</span>
      </span>
      <ProgressBar value={pct} />
      <span className="text-xs tabular-nums text-muted-foreground w-8 text-right">{pct}%</span>
    </div>
  );
}

/** Submission count with the share of them that were correct. */
function SubmissionCount({ total, correct }: { total: number; correct: number }) {
  if (total === 0) return <EmptyCell />;
  return (
    <span className="tabular-nums text-xs">
      {total}
      <span className="text-muted-foreground ml-1.5">{percent(correct, total)}%</span>
    </span>
  );
}

function HintCount({ unlocks }: { unlocks: number }) {
  if (unlocks === 0) return <EmptyCell />;
  return <span className="tabular-nums text-xs text-amber-600 dark:text-amber-400">{unlocks}</span>;
}

function FirstBlood({
  teamId,
  teamName,
  at,
}: {
  teamId?: string | null;
  teamName: string | null;
  at: string | null;
}) {
  if (!teamName) return <EmptyCell />;
  return (
    <div className="flex items-center gap-1.5">
      <Trophy className="size-3 text-amber-500 shrink-0" />
      {teamId ? <TeamLink id={teamId} name={teamName} /> : <span>{teamName}</span>}
      <DateCell value={at} />
    </div>
  );
}

// ── Challenge drill-down ──────────────────────────────────────────────────────

function ChallengeDetailDialog({
  challenge,
  teams,
  onClose,
}: {
  challenge: ChallengeStats;
  teams: number;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const solveRate = percent(challenge.teams_solved, teams);

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-4xl max-h-[85vh] overflow-y-auto space-y-4">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {challenge.challenge_title}
            {challenge.category && <TagBadge tag={challenge.category} />}
          </DialogTitle>
        </DialogHeader>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <StatCard
            label={t("admin.dashboard.col_teams_solved")}
            value={
              <span>
                {challenge.teams_solved}
                <span className="text-sm font-normal text-muted-foreground ml-1">
                  / {teams} ({solveRate}%)
                </span>
              </span>
            }
          />
          <StatCard
            label={t("admin.dashboard.col_submissions")}
            value={
              <span>
                {challenge.attempt_count}
                <span className="text-sm font-normal text-muted-foreground ml-2">
                  {challenge.attempt_count > 0
                    ? `${percent(challenge.correct_count, challenge.attempt_count)}%`
                    : "—"}
                </span>
              </span>
            }
          />
          <StatCard label={t("admin.dashboard.col_hints")} value={challenge.hint_unlock_count} />
        </div>

        <div className="rounded-lg border divide-y text-sm">
          <InfoRow
            label={t("admin.dashboard.col_first_blood")}
            value={
              <FirstBlood
                teamId={challenge.first_blood_team_id}
                teamName={challenge.first_blood_team_name}
                at={challenge.first_blood_at}
              />
            }
          />
          <InfoRow
            label={t("admin.dashboard.col_teams_tried")}
            value={
              <span className="tabular-nums">
                {challenge.teams_attempted}
                <span className="text-muted-foreground"> / {teams}</span>
              </span>
            }
          />
        </div>

        {challenge.questions.length > 0 && (
          <div className="rounded-lg border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/40">
                <tr>
                  <th className="px-4 py-2.5 text-left text-muted-foreground font-medium">
                    {t("table.col_question")}
                  </th>
                  <th className="px-4 py-2.5 text-right text-muted-foreground font-medium w-20">
                    {t("table.col_points")}
                  </th>
                  <th className="px-4 py-2.5 text-center text-muted-foreground font-medium w-24">
                    {t("admin.dashboard.col_teams_tried")}
                  </th>
                  <th className="px-4 py-2.5 text-left text-muted-foreground font-medium w-52">
                    {t("admin.dashboard.col_teams_solved")}
                  </th>
                  <th className="px-4 py-2.5 text-center text-muted-foreground font-medium w-28">
                    {t("admin.dashboard.col_submissions")}
                  </th>
                  <th className="px-4 py-2.5 text-center text-muted-foreground font-medium w-24">
                    {t("admin.dashboard.col_hints")}
                  </th>
                  <th className="px-4 py-2.5 text-left text-muted-foreground font-medium">
                    {t("admin.dashboard.col_first_blood")}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {challenge.questions.map((q: QuestionStats) => (
                  <tr key={q.question_id}>
                    <td className="px-4 py-3 font-medium">{q.question_label}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{q.points}</td>
                    <td className="px-4 py-3 text-center tabular-nums">
                      {q.teams_attempted > 0 ? q.teams_attempted : <EmptyCell />}
                    </td>
                    <td className="px-4 py-3">
                      <SolvedByTeams solved={q.teams_solved} teams={teams} />
                    </td>
                    <td className="px-4 py-3 text-center">
                      <SubmissionCount total={q.attempt_count} correct={q.correct_count} />
                    </td>
                    <td className="px-4 py-3 text-center">
                      <HintCount unlocks={q.hint_unlock_count} />
                    </td>
                    <td className="px-4 py-3">
                      <FirstBlood teamName={q.first_blood_team_name} at={q.first_blood_at} />
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

// ── Per-challenge stats ───────────────────────────────────────────────────────

const SORTERS: Record<string, (cs: ChallengeStats) => string | number> = {
  challenge_title: (cs) => cs.challenge_title.toLowerCase(),
  category: (cs) => cs.category ?? "",
  teams_solved: (cs) => cs.teams_solved,
  attempt_count: (cs) => cs.attempt_count,
};

/** Feed DataTable from an unpaginated endpoint: search, filter, sort and slice here. */
export function clientPage(
  rows: ChallengeStats[],
  state: TableState,
): PaginatedResponse<ChallengeStats> {
  const needle = state.search.trim().toLowerCase();
  const categories = state.filters.category ?? [];
  const matched = rows.filter(
    (cs) =>
      (categories.length === 0 || categories.includes(cs.category ?? "")) &&
      (needle === "" ||
        cs.challenge_title.toLowerCase().includes(needle) ||
        (cs.category?.toLowerCase().includes(needle) ?? false)),
  );

  const sorter = state.sortColumn ? SORTERS[state.sortColumn] : undefined;
  const dir = state.sortDirection === "asc" ? 1 : -1;
  const sorted = sorter
    ? [...matched].sort((a, b) => {
        const av = sorter(a);
        const bv = sorter(b);
        return av > bv ? dir : av < bv ? -dir : 0;
      })
    : [...matched].sort((a, b) => b.teams_solved - a.teams_solved);

  const start = (state.page - 1) * state.perPage;
  return {
    status: "SUCCESS",
    message: "",
    error_code: null,
    data: sorted.slice(start, start + state.perPage),
    pagination: {
      total_count: sorted.length,
      items_per_page: state.perPage,
      page: state.page,
      has_more: start + state.perPage < sorted.length,
      pages: Math.max(1, Math.ceil(sorted.length / state.perPage)),
    },
    pagination_type: "offset",
    filter_attributes: {
      category: [...new Set(rows.map((cs) => cs.category).filter(Boolean))].sort(),
    },
    search_columns: [],
    order_columns: Object.keys(SORTERS),
  };
}

function useChallengeColumns(teams: number): Column<ChallengeStats>[] {
  const { t } = useTranslation();

  return [
    {
      key: "challenge_title",
      header: t("table.col_challenge"),
      cell: (cs) => <ChallengeLink id={cs.challenge_id} name={cs.challenge_title} />,
      className: "w-1/4",
    },
    {
      key: "category",
      header: t("table.col_category"),
      cell: (cs) =>
        cs.category ? <span className="capitalize">{cs.category}</span> : <EmptyCell />,
      className: "w-32",
    },
    {
      key: "teams_solved",
      header: t("admin.dashboard.col_teams_solved"),
      cell: (cs) => <SolvedByTeams solved={cs.teams_solved} teams={teams} />,
    },
    {
      key: "attempt_count",
      header: t("admin.dashboard.col_submissions"),
      cell: (cs) => <SubmissionCount total={cs.attempt_count} correct={cs.correct_count} />,
      className: "w-28",
    },
  ];
}

// ── Category breakdown ────────────────────────────────────────────────────────

/** Challenge and point totals per category, richest first. */
export function byCategory(rows: ChallengeStats[]) {
  const totals = new Map<string, { challenges: number; points: number }>();
  for (const cs of rows) {
    const key = cs.category ?? "—";
    const row = totals.get(key) ?? { challenges: 0, points: 0 };
    row.challenges += 1;
    row.points += cs.points;
    totals.set(key, row);
  }
  return [...totals.entries()]
    .map(([category, row]) => ({ category, ...row }))
    .sort((a, b) => b.points - a.points);
}

function CategoryBreakdown({ data }: { data: ChallengeStats[] }) {
  const { t } = useTranslation();
  const rows = byCategory(data);
  const maxPoints = Math.max(...rows.map((r) => r.points), 1);

  return (
    <div className="rounded-lg border overflow-hidden">
      <table className="w-full text-sm">
        <thead className="border-b bg-muted/40">
          <tr>
            <th className="px-4 py-2.5 text-left text-muted-foreground font-medium">
              {t("table.col_category")}
            </th>
            <th className="px-4 py-2.5 text-right text-muted-foreground font-medium w-28">
              {t("admin.dashboard.stat_challenges")}
            </th>
            <th className="px-4 py-2.5 text-right text-muted-foreground font-medium w-20">
              {t("table.col_points")}
            </th>
            <th className="px-4 py-2.5 w-1/3" />
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map((row) => (
            <tr key={row.category}>
              <td className="px-4 py-2.5 capitalize font-medium">{row.category}</td>
              <td className="px-4 py-2.5 text-right tabular-nums">{row.challenges}</td>
              <td className="px-4 py-2.5 text-right tabular-nums">{row.points}</td>
              <td className="px-4 py-2.5">
                <div className="flex">
                  <ProgressBar value={percent(row.points, maxPoints)} />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Score distribution ────────────────────────────────────────────────────────

/** Group team totals into equal-width score brackets; empty when nobody scored. */
export function scoreBuckets(totals: number[]) {
  const bucketCount = 8;
  const max = Math.max(0, ...totals);
  if (totals.length === 0 || max <= 0) return [];

  const width = Math.max(1, Math.ceil(max / bucketCount));
  const buckets = Array.from({ length: Math.floor(max / width) + 1 }, (_, i) => ({
    label: `${i * width}–${(i + 1) * width - 1}`,
    teams: 0,
  }));
  for (const total of totals) {
    const index = Math.min(buckets.length - 1, Math.max(0, Math.floor(total / width)));
    buckets[index].teams += 1;
  }
  return buckets;
}

function ScoreDistribution({ scoreboard }: { scoreboard: AdminScoreboard }) {
  const { t } = useTranslation();
  const buckets = scoreBuckets(scoreboard.entries.map((e) => e.total));

  if (buckets.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">{t("admin.dashboard.distribution_empty")}</p>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={buckets} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-border" vertical={false} />
        <XAxis dataKey="label" tick={{ fontSize: 11 }} className="text-muted-foreground" />
        <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={32} />
        <Tooltip
          cursor={{ className: "fill-muted/40" }}
          formatter={(value) => [value, t("admin.dashboard.stat_teams")]}
          contentStyle={{ fontSize: "0.75rem", borderRadius: "0.5rem" }}
        />
        <Bar dataKey="teams" fill="#6366f1" radius={[2, 2, 0, 0]} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Top teams ─────────────────────────────────────────────────────────────────

function TopTeams({ scoreboard }: { scoreboard: AdminScoreboard }) {
  const top = scoreboard.entries.slice(0, 5);

  return (
    <div className="flex-1 rounded-lg border divide-y">
      {top.map((entry) => (
        <div key={entry.team_id} className="flex items-center gap-3 px-3 py-2">
          <RankBadge rank={entry.rank} />
          <TeamLink id={entry.team_id} name={entry.team_name} />
          <span className="ml-auto flex items-center gap-3">
            <DateCell value={entry.last_solve_at} />
            <span className="font-semibold tabular-nums">{entry.total}</span>
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Global counters ───────────────────────────────────────────────────────────

function GlobalStats({ stats }: { stats: AdminStats }) {
  const { t } = useTranslation();
  const successRate =
    stats.submissions > 0 ? `${percent(stats.correct_submissions, stats.submissions)}%` : "—";
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      <StatCard label={t("admin.dashboard.stat_users")} value={stats.users} />
      <StatCard label={t("admin.dashboard.stat_teams")} value={stats.teams} />
      <StatCard label={t("admin.dashboard.stat_challenges")} value={stats.challenges} />
      <StatCard
        label={t("admin.dashboard.stat_submissions")}
        value={
          <span>
            {stats.submissions}
            <span className="text-sm font-normal text-muted-foreground ml-2">{successRate}</span>
          </span>
        }
      />
      <StatCard label={t("admin.dashboard.stat_hint_unlocks")} value={stats.hint_unlocks} />
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function Dashboard() {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<ChallengeStats | null>(null);

  const { data: globalStats, isLoading: globalLoading } = useQuery({
    queryKey: ["admin", "stats", "global"],
    queryFn: getAdminStats,
  });

  const {
    data: challengeStats,
    isLoading: challengeLoading,
    isFetching: challengeFetching,
    refetch: refetchChallenges,
  } = useQuery({
    queryKey: ["admin", "stats", "challenges"],
    queryFn: getAdminAllChallengeStats,
  });

  const { data: scoreboard } = useQuery({
    queryKey: ["admin", "scoreboard", undefined],
    queryFn: () => getAdminScoreboard(),
  });

  const teams = globalStats?.teams ?? 0;
  const challengeTable = useTableState({ perPage: 10 });
  const challengeColumns = useChallengeColumns(teams);
  const challengeResponse = useMemo(
    () => challengeStats && clientPage(challengeStats, challengeTable.state),
    [challengeStats, challengeTable.state],
  );

  return (
    <div className="p-8 space-y-8">
      <PageHeader
        icon={LayoutDashboard}
        title={t("admin.nav.dashboard", { defaultValue: "Dashboard" })}
      />

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

      {scoreboard?.entries.length ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="flex flex-col gap-3">
            <h2 className="text-base font-semibold">{t("admin.dashboard.top_teams_section")}</h2>
            <TopTeams scoreboard={scoreboard} />
          </div>
          <div className="flex flex-col gap-3">
            <h2 className="text-base font-semibold">{t("admin.dashboard.distribution_section")}</h2>
            <div className="flex-1 min-h-56 rounded-lg border p-3">
              <ScoreDistribution scoreboard={scoreboard} />
            </div>
          </div>
        </div>
      ) : null}

      <div className="space-y-3">
        <h2 className="text-base font-semibold">{t("admin.dashboard.challenges_section")}</h2>

        <DataTable
          columns={challengeColumns}
          response={challengeResponse}
          table={challengeTable}
          isLoading={challengeLoading}
          isFetching={challengeFetching}
          rowKey={(cs) => cs.challenge_id}
          onRefresh={() => void refetchChallenges()}
          onRowClick={setSelected}
        />
      </div>

      {challengeStats?.length ? (
        <div className="space-y-3">
          <h2 className="text-base font-semibold">{t("admin.dashboard.categories_section")}</h2>
          <CategoryBreakdown data={challengeStats} />
        </div>
      ) : null}

      {selected && (
        <ChallengeDetailDialog
          challenge={selected}
          teams={teams}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
