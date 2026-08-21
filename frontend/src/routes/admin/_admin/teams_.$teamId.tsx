import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ChevronRight, ExternalLink, Pencil } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { CustomFieldValuesList } from "@/components/custom-field-values-list";
import { CustomFieldsSection, useCustomFieldDefs } from "@/components/custom-fields-section";
import { DataTable, useTableState } from "@/components/data-table";
import { DetailPageShell, DetailSection, InfoRow } from "@/components/detail-page";
import { FeedbackDetailDialog, useFeedbackColumns } from "@/components/feedback-table";
import { LabelInput } from "@/components/label-input";
import { LinksFormSection } from "@/components/links-form-section";
import { useScoreAdjustmentColumns } from "@/components/score-adjustment-table";
import { StatCard } from "@/components/stat-card";
import { SubmissionAnswerDialog, useSubmissionColumns } from "@/components/submission-table";
import { DateCell, EmptyCell, StatusCell, UserLink } from "@/components/table-cells";
import { ChallengeProgressTable, progressPercent, ScoreBreakdown } from "@/components/team-details";
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
  type AdminFeedback,
  type AdminSubmission,
  apiErrorMessage,
  deleteAdminSubmission,
  getAdminScoreboard,
  getAdminTeamChallengeStats,
  getAdminTeamDetail,
  getAdminTeamFeedbacks,
  getAdminTeamScore,
  getAdminTeamScoreAdjustments,
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
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [answerDialog, setAnswerDialog] = useState<AdminSubmission | null>(null);
  const [feedbackDialog, setFeedbackDialog] = useState<AdminFeedback | null>(null);

  function invalidateTeam() {
    void queryClient.invalidateQueries({ queryKey: ["admin", "team", teamId], exact: true });
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

  const { data: score } = useQuery({
    queryKey: ["admin", "team", teamId, "score"],
    queryFn: () => getAdminTeamScore(teamId),
  });

  const { data: challengeStats } = useQuery({
    queryKey: ["admin", "team", teamId, "challenge-stats"],
    queryFn: () => getAdminTeamChallengeStats(teamId),
  });

  const progress = challengeStats ? `${progressPercent(challengeStats)}%` : "—";

  const { mutate: removeSubmission } = useMutation({
    mutationFn: (id: string) => deleteAdminSubmission(id),
    onSuccess: () => {
      toast.success(t("admin.teams.submission_deleted"));
      void queryClient.invalidateQueries({ queryKey: ["admin", "team", teamId] });
      void queryClient.invalidateQueries({ queryKey: ["admin", "scoreboard"] });
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.teams.submission_delete_error"))),
  });

  const adjustmentsTable = useTableState();
  const {
    data: adjustmentsResponse,
    isLoading: adjustmentsLoading,
    isFetching: adjustmentsFetching,
    refetch: refetchAdjustments,
  } = useQuery({
    queryKey: ["admin", "team", teamId, "score-adjustments", adjustmentsTable.queryString],
    queryFn: () => getAdminTeamScoreAdjustments(teamId, adjustmentsTable.queryString),
    placeholderData: (prev) => prev,
  });

  const feedbackTable = useTableState();
  const {
    data: feedbackResponse,
    isLoading: feedbackLoading,
    isFetching: feedbackFetching,
    refetch: refetchFeedback,
  } = useQuery({
    queryKey: ["admin", "team", teamId, "feedback", feedbackTable.queryString],
    queryFn: () => getAdminTeamFeedbacks(teamId, feedbackTable.queryString),
    placeholderData: (prev) => prev,
  });

  const adjustmentColumns = useScoreAdjustmentColumns({ showTeam: false });
  const feedbackColumns = useFeedbackColumns({ showTeam: false });

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
                <InfoRow
                  label={t("admin.teams.field_id")}
                  value={<span className="font-mono text-xs break-all">{team.id}</span>}
                />
                <InfoRow
                  label={t("admin.teams.field_name")}
                  value={<span className="font-medium">{team.name}</span>}
                />
                <InfoRow
                  label={t("admin.teams.field_country")}
                  value={
                    team.country ? (
                      <span className="font-mono font-medium">{team.country}</span>
                    ) : (
                      <EmptyCell />
                    )
                  }
                />
                <InfoRow
                  label={t("admin.teams.field_bracket")}
                  value={
                    team.bracket ? (
                      <span className="font-medium capitalize">{team.bracket}</span>
                    ) : (
                      <EmptyCell />
                    )
                  }
                />
                <InfoRow
                  label={t("admin.teams.field_invite_code", { defaultValue: "Invite code" })}
                  value={<span className="font-mono text-xs">{team.invite_code}</span>}
                />
                <InfoRow
                  label={t("admin.teams.field_created", { defaultValue: "Created" })}
                  value={<DateCell value={team.created_at} />}
                />
                <InfoRow
                  label={t("admin.teams.field_updated", { defaultValue: "Updated" })}
                  value={<DateCell value={team.updated_at} />}
                />
                {team.links.length > 0 && (
                  <InfoRow
                    label={t("admin.teams.field_links")}
                    value={
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
                    }
                  />
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
                        <th className="w-8" />
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {team.users.map((member) => (
                        <tr
                          key={member.id}
                          className="group cursor-pointer border-l-2 border-l-transparent transition-colors hover:bg-accent/60 hover:border-l-primary"
                          onClick={() =>
                            void navigate({
                              to: "/admin/users/$userId",
                              params: { userId: member.id },
                            })
                          }
                        >
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
                          <td className="px-3 py-3 w-8 text-muted-foreground/30 group-hover:text-primary transition-colors">
                            <ChevronRight className="size-4 transition-transform group-hover:translate-x-0.5" />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </DetailSection>

            <DetailSection title={t("admin.teams.progress_title", { defaultValue: "Progress" })}>
              <div className="grid grid-cols-3 gap-3">
                <StatCard
                  label={t("team.rank_label")}
                  value={
                    boardEntry ? (
                      <span>
                        #{boardEntry.rank}
                        <span className="text-sm font-normal text-muted-foreground ml-1">
                          / {scoreboard?.entries.length}
                        </span>
                      </span>
                    ) : (
                      "—"
                    )
                  }
                />
                <StatCard label={t("team.progress_col_progress")} value={progress} />
                <StatCard label={t("team.progress_col_points")} value={score?.total ?? "—"} />
              </div>

              {challengeStats && <ChallengeProgressTable stats={challengeStats} detailed />}

              {score && <ScoreBreakdown score={score} />}
            </DetailSection>

            <DetailSection
              title={t("admin.scoreboard.adjustments_title", {
                defaultValue: "Score Adjustments",
              })}
            >
              <DataTable
                columns={adjustmentColumns}
                response={adjustmentsResponse}
                table={adjustmentsTable}
                isLoading={adjustmentsLoading}
                isFetching={adjustmentsFetching}
                rowKey={(adj) => adj.id}
                onRefresh={() => void refetchAdjustments()}
              />
            </DetailSection>

            <DetailSection title={t("admin.nav.feedback")}>
              <DataTable
                columns={feedbackColumns}
                response={feedbackResponse}
                table={feedbackTable}
                isLoading={feedbackLoading}
                isFetching={feedbackFetching}
                rowKey={(fb) => fb.id}
                onRefresh={() => void refetchFeedback()}
                onRowClick={(fb) => setFeedbackDialog(fb)}
              />
            </DetailSection>

            <DetailSection title={t("admin.teams.submissions_title")}>
              <DataTable
                columns={submissionColumns}
                response={submissionsResponse}
                table={submissionsTable}
                isLoading={submissionsLoading}
                isFetching={submissionsFetching}
                rowKey={(sub) => sub.id}
                onRefresh={() => void refetch()}
                onRowClick={(sub) => setAnswerDialog(sub)}
              />
            </DetailSection>
          </>
        )}
      </DetailPageShell>

      <FeedbackDetailDialog
        feedback={feedbackDialog}
        showTeam={false}
        onClose={() => setFeedbackDialog(null)}
      />

      <SubmissionAnswerDialog
        sub={answerDialog}
        showTeam={false}
        onClose={() => setAnswerDialog(null)}
        onDelete={removeSubmission}
      />
    </>
  );
}
