import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ChevronRight, RefreshCw, Trophy } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { apiErrorMessage, getAdminScoreboard, invalidateScoreboardCache } from "@/lib/api";

export const Route = createFileRoute("/admin/_admin/scoreboard")({
  component: AdminScoreboardPage,
});

// ---------------------------------------------------------------------------
// Scoreboard table
// ---------------------------------------------------------------------------

function RankCell({ rank }: { rank: number }) {
  const color =
    rank === 1
      ? "text-yellow-500 font-bold"
      : rank === 2
        ? "text-zinc-400 font-bold"
        : rank === 3
          ? "text-amber-600 font-bold"
          : "text-muted-foreground";
  return <span className={color}>#{rank}</span>;
}

function ScoreboardSection() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["admin", "scoreboard"],
    queryFn: getAdminScoreboard,
    refetchInterval: 30_000,
  });

  const { mutate: invalidate, isPending: isInvalidating } = useMutation({
    mutationFn: () => invalidateScoreboardCache(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "scoreboard"] });
      toast.success(t("admin.scoreboard.cache_invalidated"));
    },
    onError: (err) =>
      toast.error(apiErrorMessage(err, t("admin.scoreboard.cache_invalidate_error"))),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">{t("admin.scoreboard.rankings_title")}</h2>
        <Button variant="outline" size="sm" onClick={() => invalidate()} disabled={isInvalidating}>
          <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${isInvalidating ? "animate-spin" : ""}`} />
          {t("admin.scoreboard.invalidate_cache")}
        </Button>
      </div>

      {isLoading && <p className="text-muted-foreground text-sm">{t("common.loading")}</p>}

      {data && (
        <>
          <div className="rounded-lg border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/40">
                <tr>
                  <th className="px-4 py-2.5 text-left text-muted-foreground font-medium w-12">
                    {t("scoreboard.col_rank")}
                  </th>
                  <th className="px-4 py-2.5 text-left text-muted-foreground font-medium">
                    {t("scoreboard.col_team")}
                  </th>
                  <th className="px-4 py-2.5 text-right text-muted-foreground font-medium">
                    {t("scoreboard.col_total")}
                  </th>
                  <th className="px-4 py-2.5 text-right text-muted-foreground font-medium">
                    {t("scoreboard.col_solve_points")}
                  </th>
                  <th className="px-4 py-2.5 text-right text-muted-foreground font-medium">
                    {t("scoreboard.col_adjustments")}
                  </th>
                  <th className="px-4 py-2.5 text-right text-muted-foreground font-medium">
                    {t("scoreboard.col_solves")}
                  </th>
                  <th className="w-8" />
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.entries.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                      {t("scoreboard.empty")}
                    </td>
                  </tr>
                ) : (
                  data.entries.map((entry) => (
                    <tr
                      key={entry.team_id}
                      className="group transition-colors cursor-pointer hover:bg-accent/60 border-l-2 border-l-transparent hover:border-l-primary"
                      onClick={() =>
                        void navigate({
                          to: "/admin/teams/$teamId",
                          params: { teamId: entry.team_id },
                        })
                      }
                    >
                      <td className="px-4 py-3">
                        <RankCell rank={entry.rank} />
                      </td>
                      <td className="px-4 py-3 font-medium">{entry.team_name}</td>
                      <td className="px-4 py-3 text-right font-semibold tabular-nums">
                        {entry.total}
                      </td>
                      <td className="px-4 py-3 text-right text-muted-foreground tabular-nums">
                        {entry.solve_points}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        <span
                          className={
                            entry.adjustment_points !== 0
                              ? entry.adjustment_points > 0
                                ? "text-green-500"
                                : "text-red-500"
                              : "text-muted-foreground"
                          }
                        >
                          {entry.adjustment_points > 0 ? "+" : ""}
                          {entry.adjustment_points}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right text-muted-foreground tabular-nums">
                        {entry.solve_count}
                      </td>
                      <td className="px-3 py-3 w-8 text-muted-foreground/30 group-hover:text-primary transition-colors">
                        <ChevronRight className="size-4 transition-transform group-hover:translate-x-0.5" />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          {data.computed_at && (
            <p className="text-xs text-muted-foreground text-right">
              {t("scoreboard.computed_at", {
                date: new Date(data.computed_at).toLocaleString(),
              })}
            </p>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function AdminScoreboardPage() {
  const { t } = useTranslation();

  return (
    <div className="p-8 space-y-10">
      <div className="flex items-center gap-3">
        <Trophy className="h-6 w-6 text-primary" />
        <h1 className="text-2xl font-bold">
          {t("admin.nav.scoreboard", { defaultValue: "Scoreboard" })}
        </h1>
      </div>

      <ScoreboardSection />
    </div>
  );
}
