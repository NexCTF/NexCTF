import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { ExternalLink, Maximize2, Pencil, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { CustomFieldInput } from "@/components/custom-field-input";
import { CustomFieldValuesList } from "@/components/custom-field-values-list";
import { type Column, DataTable, useTableState } from "@/components/data-table";
import { DetailPageShell, DetailSection } from "@/components/detail-page";
import { IdCell } from "@/components/id-cell";
import { LinksFormSection } from "@/components/links-form-section";
import { StatCard } from "@/components/stat-card";
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
  getAdminCustomFields,
  getAdminTeamChallengeStats,
  getAdminTeamDetail,
  getAdminTeamSubmissions,
  type Link,
  setAdminCustomFieldValue,
  updateAdminTeam,
} from "@/lib/api";

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
  const [bracket, setBracket] = useState(team.bracket ?? "");
  const [links, setLinks] = useState<Link[]>(team.links);
  const [cfValues, setCfValues] = useState<Record<string, string>>(
    Object.fromEntries(team.custom_field_values.map((cfv) => [cfv.definition.id, cfv.value ?? ""])),
  );

  const { data: defsResponse } = useQuery({
    queryKey: ["admin", "custom-fields", "all"],
    queryFn: () => getAdminCustomFields("items_per_page=100"),
    enabled: open,
  });
  const teamDefs = (defsResponse?.data ?? []).filter((d) => d.target === "team");

  const existingDefIds = new Set(team.custom_field_values.map((cfv) => cfv.definition.id));

  const mutation = useMutation({
    mutationFn: async () => {
      await updateAdminTeam(teamId, {
        name,
        country: country.toUpperCase() || null,
        bracket: bracket.trim() || null,
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
            <Input
              value={bracket}
              onChange={(e) => setBracket(e.target.value)}
              placeholder="student"
              className="w-44"
            />
            <p className="text-xs text-muted-foreground">{t("admin.teams.bracket_hint")}</p>
          </div>

          <LinksFormSection links={links} onChange={setLinks} />

          {teamDefs.length > 0 && (
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {t("admin.custom_fields.values_title")}
              </p>
              {teamDefs.map((def) => (
                <div key={def.id} className="space-y-1.5">
                  <Label>
                    {def.label}
                    {def.is_required && <span className="text-destructive ml-0.5">*</span>}
                  </Label>
                  <CustomFieldInput
                    fieldType={def.field_type}
                    value={cfValues[def.id] ?? ""}
                    onChange={(v) => setCfValues((prev) => ({ ...prev, [def.id]: v }))}
                  />
                </div>
              ))}
            </div>
          )}

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

  const { data: challengeStats } = useQuery<AdminTeamChallengeStats[]>({
    queryKey: ["admin", "team", teamId, "challenge-stats"],
    queryFn: () => getAdminTeamChallengeStats(teamId),
  });

  const challengeSummary = useMemo(() => {
    if (!challengeStats) return null;
    return {
      solves: challengeStats.filter((cs) => cs.is_solved).length,
      points: challengeStats.reduce((acc, cs) => acc + cs.points_earned, 0),
      hintUnlocks: challengeStats.reduce((acc, cs) => acc + cs.hint_unlock_count, 0),
      hintCost: challengeStats.reduce((acc, cs) => acc + cs.hint_cost_spent, 0),
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

  const SUBMISSION_COLUMNS: Column<AdminSubmission>[] = [
    {
      key: "id",
      header: "ID",
      sortable: false,
      cell: (sub) => <IdCell id={sub.id} />,
      className: "w-32",
    },
    {
      key: "question_challenge_title",
      header: t("admin.teams.col_challenge"),
      cell: (sub) => (
        <span className="text-muted-foreground">{sub.question_challenge_title ?? "—"}</span>
      ),
    },
    {
      key: "question_label",
      header: t("admin.teams.col_question"),
      cell: (sub) => <span>{sub.question_label ?? "—"}</span>,
    },
    {
      key: "answer",
      header: t("admin.teams.col_answer"),
      cell: (sub) => (
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-xs text-primary underline-offset-2 hover:underline hover:bg-primary/10 transition-colors max-w-[140px] truncate"
          onClick={(e) => {
            e.stopPropagation();
            setAnswerDialog(sub);
          }}
        >
          <span className="truncate">{sub.answer}</span>
          <Maximize2 className="size-3 shrink-0 opacity-60" />
        </button>
      ),
    },
    {
      key: "is_correct",
      header: t("admin.teams.col_correct"),
      cell: (sub) => (
        <span className={sub.is_correct ? "text-green-500 font-semibold" : "text-muted-foreground"}>
          {sub.is_correct ? "✓" : "✗"}
        </span>
      ),
    },
    {
      key: "points_earned",
      header: t("admin.teams.col_points"),
      sortable: true,
      cell: (sub) => (
        <span className="tabular-nums">
          {sub.points_earned > 0 ? `+${sub.points_earned}` : sub.points_earned}
        </span>
      ),
    },
    {
      key: "created_at",
      header: t("admin.teams.col_date"),
      cell: (sub) => (
        <span className="text-muted-foreground text-xs whitespace-nowrap">
          {new Date(sub.created_at).toLocaleString()}
        </span>
      ),
    },
    {
      key: "actions",
      header: "",
      sortable: false,
      cell: (sub) => (
        <div className="flex justify-end">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-destructive hover:text-destructive"
            onClick={(e) => {
              e.stopPropagation();
              if (confirm(t("admin.teams.submission_delete_confirm"))) removeSubmission(sub.id);
            }}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      ),
      className: "w-12",
    },
  ];

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

            <DetailSection
              title={t("admin.teams.members_title", {
                count: team.users.length,
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
                          {t("admin.teams.col_username")}
                        </th>
                        <th className="px-4 py-2.5 text-left text-muted-foreground font-medium">
                          {t("admin.teams.col_email")}
                        </th>
                        <th className="px-4 py-2.5 text-left text-muted-foreground font-medium">
                          {t("admin.teams.col_role")}
                        </th>
                        <th className="px-4 py-2.5 text-left text-muted-foreground font-medium">
                          {t("admin.teams.col_active")}
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {team.users.map((member) => (
                        <tr key={member.id} className="transition-colors hover:bg-muted/30">
                          <td className="px-4 py-3 font-medium">{member.username}</td>
                          <td className="px-4 py-3 text-muted-foreground">{member.email ?? "—"}</td>
                          <td className="px-4 py-3">
                            <span className="capitalize">{member.role}</span>
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className={
                                member.is_active ? "text-green-500" : "text-muted-foreground"
                              }
                            >
                              {member.is_active ? "✓" : "✗"}
                            </span>
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
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
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
                      label={t("admin.teams.stat_points", { defaultValue: "Total Points" })}
                      value={challengeSummary.points}
                    />
                    <StatCard
                      label={t("admin.teams.stat_hint_unlocks", { defaultValue: "Hint Unlocks" })}
                      value={
                        <span className="text-amber-600 dark:text-amber-400">
                          {challengeSummary.hintUnlocks}
                        </span>
                      }
                    />
                    <StatCard
                      label={t("admin.teams.stat_hint_cost", { defaultValue: "Hint Cost Spent" })}
                      value={
                        <span className="text-amber-600 dark:text-amber-400">
                          {challengeSummary.hintCost > 0 ? `-${challengeSummary.hintCost}` : "0"}
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
                          {t("admin.teams.col_challenge")}
                        </th>
                        <th className="px-4 py-2.5 text-center text-muted-foreground font-medium w-24">
                          {t("admin.teams.col_progress", {
                            defaultValue: "Progress",
                          })}
                        </th>
                        <th className="px-4 py-2.5 text-center text-muted-foreground font-medium w-24">
                          {t("admin.teams.col_points")}
                        </th>
                        <th className="px-4 py-2.5 text-center text-muted-foreground font-medium w-28">
                          {t("admin.teams.col_hints", {
                            defaultValue: "Hints",
                          })}
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
                          <td className="px-4 py-3 font-medium">{cs.challenge_title}</td>
                          <td className="px-4 py-3 text-center">
                            {cs.question_count === 0 ? (
                              <span className="text-muted-foreground">—</span>
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
                              <span className="text-muted-foreground">—</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-center tabular-nums">
                            {cs.hint_unlock_count > 0 ? (
                              <span className="text-amber-600 dark:text-amber-400">
                                {cs.hint_unlock_count}
                              </span>
                            ) : (
                              <span className="text-muted-foreground">—</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-center tabular-nums">
                            {cs.hint_cost_spent > 0 ? (
                              <span className="text-amber-600 dark:text-amber-400">
                                -{cs.hint_cost_spent}
                              </span>
                            ) : (
                              <span className="text-muted-foreground">—</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
                            {cs.first_solve_at ? new Date(cs.first_solve_at).toLocaleString() : "—"}
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
                columns={SUBMISSION_COLUMNS}
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

      {answerDialog && (
        <Dialog open onOpenChange={(v) => !v && setAnswerDialog(null)}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>{t("admin.teams.answer_dialog_title")}</DialogTitle>
            </DialogHeader>
            <div className="space-y-3 text-sm">
              {answerDialog.question_challenge_title && (
                <div className="flex gap-2">
                  <span className="text-muted-foreground shrink-0">
                    {t("admin.teams.col_challenge")}:
                  </span>
                  <span>{answerDialog.question_challenge_title}</span>
                </div>
              )}
              <div className="flex gap-2">
                <span className="text-muted-foreground shrink-0">
                  {t("admin.teams.col_question")}:
                </span>
                <span>{answerDialog.question_label ?? "—"}</span>
              </div>
              <div className="rounded-md bg-muted p-3 font-mono text-sm break-all">
                {answerDialog.answer}
              </div>
              <div className="flex justify-end pt-2">
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => {
                    if (confirm(t("admin.teams.submission_delete_confirm"))) {
                      removeSubmission(answerDialog.id);
                      setAnswerDialog(null);
                    }
                  }}
                >
                  <Trash2 className="h-3.5 w-3.5 mr-1.5" />
                  {t("common.delete")}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </>
  );
}
