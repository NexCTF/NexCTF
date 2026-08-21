import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { RefreshCw, Trophy } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { BracketSelect } from "@/components/bracket-select";
import { CLICKABLE_ROW_CLS, RowChevron } from "@/components/data-table";
import { PageHeader } from "@/components/page-header";
import { RankBadge, ScoreboardBanners } from "@/components/scoreboard";
import { DateCell, EmptyCell, SignedPoints } from "@/components/table-cells";
import { Button } from "@/components/ui/button";
import { apiErrorMessage, getAdminScoreboard, invalidateScoreboardCache } from "@/lib/api";

export const Route = createFileRoute("/admin/_admin/scoreboard")({
  component: AdminScoreboardPage,
});

// ---------------------------------------------------------------------------
// Scoreboard table
// ---------------------------------------------------------------------------

function ScoreboardSection() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [bracket, setBracket] = useState<string | undefined>(undefined);

  const { data, isLoading } = useQuery({
    queryKey: ["admin", "scoreboard", bracket],
    queryFn: () => getAdminScoreboard(bracket),
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
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">{t("admin.scoreboard.rankings_title")}</h2>
        <div className="flex items-center gap-2">
          {data && <BracketSelect brackets={data.brackets} value={bracket} onChange={setBracket} />}
          <Button
            variant="outline"
            size="sm"
            onClick={() => invalidate()}
            disabled={isInvalidating}
          >
            <RefreshCw className={isInvalidating ? "animate-spin" : ""} />
            {t("admin.scoreboard.invalidate_cache")}
          </Button>
        </div>
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
                  {data.brackets.length > 0 && (
                    <th className="px-4 py-2.5 text-left text-muted-foreground font-medium">
                      {t("scoreboard.bracket_label")}
                    </th>
                  )}
                  {data.custom_fields.map((f) => (
                    <th
                      key={f.name}
                      className="px-4 py-2.5 text-left text-muted-foreground font-medium"
                    >
                      {f.label}
                    </th>
                  ))}
                  <th className="px-4 py-2.5 text-right text-muted-foreground font-medium">
                    {t("scoreboard.col_solve_points", { defaultValue: "Solve points" })}
                  </th>
                  <th className="px-4 py-2.5 text-right text-muted-foreground font-medium">
                    {t("scoreboard.col_hints", { defaultValue: "Hints" })}
                  </th>
                  <th className="px-4 py-2.5 text-right text-muted-foreground font-medium">
                    {t("scoreboard.col_adjustments", { defaultValue: "Adjustments" })}
                  </th>
                  <th className="px-4 py-2.5 text-right text-muted-foreground font-medium">
                    {t("scoreboard.col_solves", { defaultValue: "Solves" })}
                  </th>
                  <th className="px-4 py-2.5 text-left text-muted-foreground font-medium w-40">
                    {t("admin.scoreboard.col_last_solve", { defaultValue: "Last solve" })}
                  </th>
                  <th className="px-4 py-2.5 text-right text-muted-foreground font-medium">
                    {t("scoreboard.col_total")}
                  </th>
                  <th className="w-8" />
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.entries.length === 0 ? (
                  <tr>
                    <td
                      colSpan={9 + (data.brackets.length > 0 ? 1 : 0) + data.custom_fields.length}
                      className="px-4 py-8 text-center text-muted-foreground"
                    >
                      {t("scoreboard.empty")}
                    </td>
                  </tr>
                ) : (
                  data.entries.map((entry) => (
                    <tr
                      key={entry.team_id}
                      className={CLICKABLE_ROW_CLS}
                      onClick={() =>
                        void navigate({
                          to: "/admin/teams/$teamId",
                          params: { teamId: entry.team_id },
                        })
                      }
                    >
                      <td className="px-4 py-3">
                        <RankBadge rank={entry.rank} />
                      </td>
                      <td className="px-4 py-3 font-medium">{entry.team_name}</td>
                      {data.brackets.length > 0 && (
                        <td className="px-4 py-3 text-muted-foreground capitalize">
                          {entry.team_bracket ?? <EmptyCell />}
                        </td>
                      )}
                      {data.custom_fields.map((f) => (
                        <td key={f.name} className="px-4 py-3 text-muted-foreground">
                          {entry.custom_fields[f.name] ?? <EmptyCell />}
                        </td>
                      ))}
                      <td className="px-4 py-3 text-right tabular-nums">{entry.solve_points}</td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {entry.hint_points !== 0 ? (
                          <span className="text-amber-600 dark:text-amber-400">
                            {entry.hint_points}
                          </span>
                        ) : (
                          <EmptyCell />
                        )}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {entry.adjustment_points !== 0 ? (
                          <SignedPoints amount={entry.adjustment_points} />
                        ) : (
                          <EmptyCell />
                        )}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">{entry.solve_count}</td>
                      <td className="px-4 py-3">
                        <DateCell value={entry.last_solve_at} />
                      </td>
                      <td className="px-4 py-3 text-right font-semibold tabular-nums">
                        {entry.total}
                      </td>
                      <RowChevron />
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
    <div className="p-8 space-y-6">
      <PageHeader icon={Trophy} title={t("admin.nav.scoreboard", { defaultValue: "Scoreboard" })} />

      <ScoreboardBanners />

      <ScoreboardSection />
    </div>
  );
}
