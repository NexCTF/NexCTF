import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ChevronRight, RefreshCw, Trophy } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { BracketSelect } from "@/components/bracket-select";
import { PageHeader } from "@/components/page-header";
import { RankBadge, ScoreboardBanners } from "@/components/scoreboard";
import { EmptyCell } from "@/components/table-cells";
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
                    {t("scoreboard.col_total")}
                  </th>
                  <th className="w-8" />
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.entries.length === 0 ? (
                  <tr>
                    <td
                      colSpan={4 + (data.brackets.length > 0 ? 1 : 0) + data.custom_fields.length}
                      className="px-4 py-8 text-center text-muted-foreground"
                    >
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
                      <td className="px-4 py-3 text-right font-semibold tabular-nums">
                        {entry.total}
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
    <div className="p-8 space-y-6">
      <PageHeader icon={Trophy} title={t("admin.nav.scoreboard", { defaultValue: "Scoreboard" })} />

      <ScoreboardBanners />

      <ScoreboardSection />
    </div>
  );
}
