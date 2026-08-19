import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { ExternalLink, Pencil } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { CustomFieldValuesList } from "@/components/custom-field-values-list";
import { CustomFieldsSection, useCustomFieldDefs } from "@/components/custom-fields-section";
import { DataTable, useTableState } from "@/components/data-table";
import { DetailPageShell, DetailSection } from "@/components/detail-page";
import { LabelInput } from "@/components/label-input";
import { LinksFormSection } from "@/components/links-form-section";
import { StatCard } from "@/components/stat-card";
import { SubmissionAnswerDialog, useSubmissionColumns } from "@/components/submission-table";
import {
  ChallengeLink,
  DateCell,
  EmptyCell,
  SignedPoints,
  StatusCell,
  UserLink,
} from "@/components/table-cells";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  type AdminSubmission,
  type AdminTeamChallengeStats,
  apiErrorMessage,
  deleteAdminSubmission,
  getAdminScoreboard,
  getAdminTeamChallengeStats,
  getAdminTeamDetail,
  getAdminTeamSubmissions,
  type Link,
  setAdminCustomFieldValue,
  updateAdminTeam,
} from "@/lib/api";
import { useFacetValues } from "@/lib/use-facet-values";

export const Route = createFileRoute("/admin/_admin/teams_/$teamId")({
  component: TeamDetailPage,
});

function EditTeamDialog({
  teamId,
  team,
  onSaved,
}: {
  teamId: string;
  team: Awaited<ReturnType<typeof getAdminTeamDetail>>;
  onSaved: () => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(team.name);
  const [country, setCountry] = useState(team.country ?? "");
  const brackets = useFacetValues("/admin/team", "bracket");
  const [bracket, setBracket] = useState(team.bracket ?? "");
  const [links, setLinks] = useState<Link[]>(team.links);
  const [cfValues, setCfValues] = useState<Record<string, string>>(
    Object.fromEntries(team.custom_field_values.map((cfv) => [cfv.definition.id, cfv.value ?? ""])),
  );

  const teamDefs = useCustomFieldDefs("team", open);

  const existingDefIds = new Set(team.custom_field_values.map((cfv) => cfv.definition.id));

  const mutation = useMutation({
    mutationFn: async () => {
      await updateAdminTeam(teamId, {
        name,
        country: country.toUpperCase() || null,
        bracket: bracket || null,
        links,
      });
      await Promise.all(
        teamDefs
          .filter((def) => cfValues[def.id] || existingDefIds.has(def.id))
          .map((def) =>
            setAdminCustomFieldValue({
              definition_id: def.id,
              team_id: teamId,
              value: cfValues[def.id] || null,
            }),
          ),
      );
    },
    onSuccess: () => {
      toast.success(t("admin.teams.info_saved"));
      setOpen(false);
      onSaved();
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.teams.info_save_error"))),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button variant="outline" size="sm">
            <Pencil className="size-3.5 mr-1.5" />
            {t("common.edit")}
          </Button>
        }
      />
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("admin.teams.edit_info_title")}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
          className="space-y-4 mt-2 max-h-[70vh] overflow-y-auto pr-1"
        >
          <div className="space-y-1.5">
            <Label>{t("admin.teams.field_name")} *</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} required />
          </div>

          <div className="space-y-1.5">
            <Label>{t("admin.teams.field_country")}</Label>
            <Input
              value={country}
              onChange={(e) => setCountry(e.target.value.toUpperCase().slice(0, 2))}
              placeholder="FR"
              maxLength={2}
              className="font-mono uppercase w-24"
            />
            <p className="text-xs text-muted-foreground">{t("admin.teams.country_hint")}</p>
          </div>

          <div className="space-y-1.5">
            <Label>{t("admin.teams.field_bracket")}</Label>
            <LabelInput
              suggestions={brackets}
              value={bracket}
              onValueChange={setBracket}
              placeholder="student"
              noun={t("admin.labels.noun_bracket")}
              className="w-44"
            />
            <p className="text-xs text-muted-foreground">{t("admin.teams.bracket_hint")}</p>
          </div>

          <LinksFormSection links={links} onChange={setLinks} />

          <CustomFieldsSection defs={teamDefs} values={cfValues} onChange={setCfValues} />

          <DialogFooter className="pt-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? t("common.saving") : t("common.save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function TeamDetailPage() {
  const { t } = useTranslation();
  const { teamId } = Route.useParams();
  const queryClient = useQueryClient();
  const [answerDialog, setAnswerDialog] = useState<AdminSubmission | null>(null);

  function invalidateTeam() {
    void queryClient.invalidateQueries({ queryKey: ["admin", "team", teamId] });
    void queryClient.invalidateQueries({ queryKey: ["admin", "teams"] });
  }

  const { data: team, isLoading } = useQuery({
    queryKey: ["admin", "team", teamId],
    queryFn: () => getAdminTeamDetail(teamId),
  });

  const submissionsTable = useTableState();

  const {
    data: submissionsResponse,
    isLoading: submissionsLoading,
    isFetching: submissionsFetching,
    refetch,
  } = useQuery({
    queryKey: ["admin", "team", teamId, "submissions", submissionsTable.queryString],
    queryFn: () => getAdminTeamSubmissions(teamId, submissionsTable.queryString),
    placeholderData: (prev) => prev,
  });

  const { data: scoreboard } = useQuery({
    queryKey: ["admin", "scoreboard", undefined],
    queryFn: () => getAdminScoreboard(),
  });
  const boardEntry = scoreboard?.entries.find((e) => e.team_id === teamId);

  const { data: challengeStats } = useQuery<AdminTeamChallengeStats[]>({
    queryKey: ["admin", "team", teamId, "challenge-stats"],
    queryFn: () => getAdminTeamChallengeStats(teamId),
  });

  const challengeSummary = useMemo(() => {
    if (!challengeStats) return null;
    return {
      solves: challengeStats.filter((cs) => cs.is_solved).length,
      hintUnlocks: challengeStats.reduce((acc, cs) => acc + cs.hint_unlock_count, 0),
    };
  }, [challengeStats]);

  const { mutate: removeSubmission } = useMutation({
    mutationFn: (id: string) => deleteAdminSubmission(id),
    onSuccess: () => {
      toast.success(t("admin.teams.submission_deleted"));
      void queryClient.invalidateQueries({
        queryKey: ["admin", "team", teamId, "submissions"],
      });
      void queryClient.invalidateQueries({ queryKey: ["admin", "scoreboard"] });
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.teams.submission_delete_error"))),
  });

  const submissionColumns = useSubmissionColumns({
    showTeam: false,
    onAnswerClick: setAnswerDialog,
    onDelete: removeSubmission,
  });

  return (
    <>
      <DetailPageShell
        backTo="/admin/teams"
        backLabel={t("admin.teams.detail_back")}
        title={team?.name}
        isLoading={isLoading}
      >
        {team && (
          <>
            <DetailSection
              title={t("admin.teams.info_title")}
              actions={<EditTeamDialog teamId={teamId} team={team} onSaved={invalidateTeam} />}
            >
              <div className="rounded-lg border divide-y text-sm">
                <div className="flex gap-2 px-4 py-3">
                  <span className="text-muted-foreground w-24 shrink-0">
                    {t("admin.teams.field_id")}
                  </span>
                  <span className="font-mono text-xs break-all">{team.id}</span>
                </div>
                <div className="flex gap-2 px-4 py-3">
                  <span className="text-muted-foreground w-24 shrink-0">
                    {t("admin.teams.field_name")}
                  </span>
                  <span className="font-medium">{team.name}</span>
                </div>
                <div className="flex gap-2 px-4 py-3">
                  <span className="text-muted-foreground w-24 shrink-0">
                    {t("admin.teams.field_country")}
                  </span>
                  <span
                    className={team.country ? "font-mono font-medium" : "text-muted-foreground"}
                  >
                    {team.country ?? "—"}
                  </span>
                </div>
                <div className="flex gap-2 px-4 py-3">
                  <span className="text-muted-foreground w-24 shrink-0">
                    {t("admin.teams.field_bracket")}
                  </span>
                  <span
                    className={team.bracket ? "font-medium capitalize" : "text-muted-foreground"}
                  >
                    {team.bracket ?? "—"}
                  </span>
                </div>
                {team.links.length > 0 && (
                  <div className="flex gap-2 px-4 py-3">
                    <span className="text-muted-foreground w-24 shrink-0">
                      {t("admin.teams.field_links")}
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {team.links.map((lnk, i) => (
                        <a
                          // biome-ignore lint/suspicious/noArrayIndexKey: display-only, never reorders
                          key={i}
                          href={lnk.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-primary hover:underline underline-offset-2 text-xs"
                        >
                          {lnk.label || lnk.url}
                          <ExternalLink className="size-3 opacity-60" />
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </DetailSection>

            <CustomFieldValuesList
              entityId={teamId}
              entityType="team"
              values={team.custom_field_values}
              onSaved={invalidateTeam}
              readOnly
            />

            {boardEntry && (
              <DetailSection title={t("admin.teams.score_title", { defaultValue: "Score" })}>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                  <StatCard
                    label={t("scoreboard.col_rank")}
                    value={
                      <span>
                        #{boardEntry.rank}
                        <span className="text-sm font-normal text-muted-foreground ml-1">
                          / {scoreboard?.entries.length}
                        </span>
                      </span>
                    }
                  />
                  <StatCard label={t("scoreboard.col_total")} value={boardEntry.total} />
                  <StatCard
                    label={t("scoreboard.col_solve_points")}
                    value={boardEntry.solve_points}
                  />
                  <StatCard
                    label={t("scoreboard.col_adjustments")}
                    value={<SignedPoints amount={boardEntry.adjustment_points} />}
                  />
                  <StatCard
                    label={t("scoreboard.col_hints")}
                    value={
                      <span
                        className={
                          boardEntry.hint_points !== 0
                            ? "text-amber-600 dark:text-amber-400"
                            : undefined
                        }
                      >
                        {boardEntry.hint_points}
                      </span>
                    }
                  />
                  <StatCard label={t("scoreboard.col_solves")} value={boardEntry.solve_count} />
                  <StatCard
                    label={t("admin.scoreboard.col_last_solve", { defaultValue: "Last solve" })}
                    value={
                      <span className="text-base font-medium">
                        <DateCell value={boardEntry.last_solve_at} />
                      </span>
                    }
                  />
                </div>
              </DetailSection>
            )}

            <DetailSection
              title={t("admin.teams.members_title", {
                n: team.users.length,
              })}
            >
              {team.users.length === 0 ? (
                <p className="text-muted-foreground text-sm">{t("admin.teams.members_empty")}</p>
              ) : (
                <div className="rounded-lg border overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="border-b bg-muted/40">
                      <tr>
                        <th className="px-4 py-2.5 text-left text-muted-foreground font-medium">
                          {t("table.col_username", { defaultValue: "Username" })}
                        </th>
                        <th className="px-4 py-2.5 text-left text-muted-foreground font-medium">
                          {t("table.col_email", { defaultValue: "Email" })}
                        </th>
                        <th className="px-4 py-2.5 text-left text-muted-foreground font-medium">
                          {t("table.col_role", { defaultValue: "Role" })}
                        </th>
                        <th className="px-4 py-2.5 text-left text-muted-foreground font-medium">
                          {t("table.col_status", { defaultValue: "Status" })}
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {team.users.map((member) => (
                        <tr key={member.id} className="transition-colors hover:bg-muted/30">
                          <td className="px-4 py-3 font-medium">
                            <UserLink id={member.id} name={member.username} />
                          </td>
                          <td className="px-4 py-3 text-muted-foreground">{member.email ?? "—"}</td>
                          <td className="px-4 py-3">
                            <span className="capitalize">{member.role}</span>
                          </td>
                          <td className="px-4 py-3">
                            <StatusCell active={member.is_active} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </DetailSection>

            {challengeStats && challengeStats.length > 0 && (
              <DetailSection
                title={t("admin.teams.challenge_progress_title", {
                  defaultValue: "Challenge Progress",
                })}
              >
                {challengeSummary && (
                  <div className="grid grid-cols-2 gap-3 mb-4">
                    <StatCard
                      label={t("admin.teams.stat_solves", { defaultValue: "Challenges Solved" })}
                      value={
                        <span>
                          <span className="text-green-600 dark:text-green-400">
                            {challengeSummary.solves}
                          </span>
                          <span className="text-sm font-normal text-muted-foreground ml-1">
                            / {challengeStats?.length}
                          </span>
                        </span>
                      }
                    />
                    <StatCard
                      label={t("admin.teams.stat_hint_unlocks", { defaultValue: "Hint Unlocks" })}
                      value={
                        <span className="text-amber-600 dark:text-amber-400">
                          {challengeSummary.hintUnlocks}
                        </span>
                      }
                    />
                  </div>
                )}

                <div className="rounded-lg border overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="border-b bg-muted/40">
                      <tr>
                        <th className="px-4 py-2.5 text-left text-muted-foreground font-medium">
                          {t("table.col_challenge", { defaultValue: "Challenge" })}
                        </th>
                        <th className="px-4 py-2.5 text-center text-muted-foreground font-medium w-24">
                          {t("admin.teams.col_progress", {
                            defaultValue: "Progress",
                          })}
                        </th>
                        <th className="px-4 py-2.5 text-center text-muted-foreground font-medium w-24">
                          {t("table.col_points", { defaultValue: "Points" })}
                        </th>
                        <th className="px-4 py-2.5 text-center text-muted-foreground font-medium w-28">
                          {t("table.col_hints", { defaultValue: "Hints" })}
                        </th>
                        <th className="px-4 py-2.5 text-center text-muted-foreground font-medium w-32">
                          {t("admin.teams.col_hint_cost", {
                            defaultValue: "Hint Cost",
                          })}
                        </th>
                        <th className="px-4 py-2.5 text-left text-muted-foreground font-medium w-44">
                          {t("admin.teams.col_first_solve", {
                            defaultValue: "First Solve",
                          })}
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {challengeStats.map((cs) => (
                        <tr key={cs.challenge_id} className="transition-colors hover:bg-muted/30">
                          <td className="px-4 py-3 font-medium">
                            <ChallengeLink id={cs.challenge_id} name={cs.challenge_title} />
                          </td>
                          <td className="px-4 py-3 text-center">
                            {cs.question_count === 0 ? (
                              <EmptyCell />
                            ) : cs.is_solved ? (
                              <span className="text-green-500 font-semibold">
                                ✓ {cs.solved_question_count}/{cs.question_count}
                              </span>
                            ) : cs.solved_question_count > 0 ? (
                              <span className="text-amber-500">
                                {cs.solved_question_count}/{cs.question_count}
                              </span>
                            ) : (
                              <span className="text-muted-foreground">0/{cs.question_count}</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-center tabular-nums">
                            {cs.points_earned > 0 ? (
                              <span className="text-green-600 dark:text-green-400 font-medium">
                                +{cs.points_earned}
                              </span>
                            ) : (
                              <EmptyCell />
                            )}
                          </td>
                          <td className="px-4 py-3 text-center tabular-nums">
                            {cs.hint_unlock_count > 0 ? (
                              <span className="text-amber-600 dark:text-amber-400">
                                {cs.hint_unlock_count}
                              </span>
                            ) : (
                              <EmptyCell />
                            )}
                          </td>
                          <td className="px-4 py-3 text-center tabular-nums">
                            {cs.hint_cost_spent > 0 ? (
                              <span className="text-amber-600 dark:text-amber-400">
                                -{cs.hint_cost_spent}
                              </span>
                            ) : (
                              <EmptyCell />
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <DateCell value={cs.first_solve_at} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </DetailSection>
            )}

            <DetailSection title={t("admin.teams.submissions_title")}>
              <DataTable
                columns={submissionColumns}
                response={submissionsResponse}
                table={submissionsTable}
                isLoading={submissionsLoading}
                isFetching={submissionsFetching}
                rowKey={(sub) => sub.id}
                onRefresh={() => void refetch()}
              />
            </DetailSection>
          </>
        )}
      </DetailPageShell>

      <SubmissionAnswerDialog
        sub={answerDialog}
        showTeam={false}
        onClose={() => setAnswerDialog(null)}
        onDelete={removeSubmission}
      />
    </>
  );
}
