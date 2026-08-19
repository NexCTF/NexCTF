import { Maximize2, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { ConfirmDialog, DeleteButton } from "@/components/confirm-dialog";
import type { Column } from "@/components/data-table";
import {
  ActionsCell,
  BoolCell,
  ChallengeLink,
  DateCell,
  EmptyCell,
  idColumn,
  stopRowClick,
  TeamLink,
} from "@/components/table-cells";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { AdminSubmission } from "@/lib/api";

/**
 * Submission columns, shared with the team detail page.
 *
 * `showTeam` is off there since every row belongs to the same team.
 */
export function useSubmissionColumns({
  showTeam = true,
  onAnswerClick,
  onDelete,
}: {
  showTeam?: boolean;
  onAnswerClick: (sub: AdminSubmission) => void;
  onDelete: (id: string) => void;
}): Column<AdminSubmission>[] {
  const { t } = useTranslation();

  return [
    idColumn<AdminSubmission>(t),
    ...(showTeam
      ? [
          {
            key: "team_name",
            header: t("table.col_team", { defaultValue: "Team" }),
            cell: (sub: AdminSubmission) => <TeamLink id={sub.team_id} name={sub.team_name} />,
          },
        ]
      : []),
    {
      key: "question_challenge_title",
      header: t("table.col_challenge", { defaultValue: "Challenge" }),
      cell: (sub) => (
        <ChallengeLink id={sub.question_challenge_id} name={sub.question_challenge_title} />
      ),
    },
    {
      key: "question_label",
      header: t("table.col_question", { defaultValue: "Question" }),
      cell: (sub) =>
        sub.question_label ? (
          <span className="text-muted-foreground text-xs">{sub.question_label}</span>
        ) : (
          <EmptyCell />
        ),
    },
    {
      key: "answer",
      header: t("table.col_answer", { defaultValue: "Answer" }),
      cell: (sub) => (
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-xs text-primary underline-offset-2 hover:underline hover:bg-primary/10 transition-colors max-w-[140px] truncate"
          onClick={(e) => {
            stopRowClick(e);
            onAnswerClick(sub);
          }}
        >
          <span className="truncate">{sub.answer}</span>
          <Maximize2 className="size-3 shrink-0 opacity-60" />
        </button>
      ),
    },
    {
      key: "is_correct",
      header: t("table.col_correct", { defaultValue: "Correct" }),
      cell: (sub) => <BoolCell value={sub.is_correct} />,
      className: "w-20",
    },
    {
      key: "points_earned",
      header: t("table.col_points", { defaultValue: "Points" }),
      sortable: true,
      cell: (sub) => (
        <span className="tabular-nums">
          {sub.points_earned > 0 ? `+${sub.points_earned}` : sub.points_earned}
        </span>
      ),
      className: "w-20",
    },
    {
      key: "created_at",
      header: t("table.col_date", { defaultValue: "Date" }),
      sortable: true,
      cell: (sub) => <DateCell value={sub.created_at} />,
      className: "w-40",
    },
    {
      key: "actions",
      header: "",
      sortable: false,
      cell: (sub) => (
        <ActionsCell>
          <DeleteButton
            description={t("admin.submissions.delete_confirm")}
            onConfirm={() => onDelete(sub.id)}
          />
        </ActionsCell>
      ),
      className: "w-12",
    },
  ];
}

/** Full answer plus its relations, with the delete action. */
export function SubmissionAnswerDialog({
  sub,
  showTeam = true,
  onClose,
  onDelete,
}: {
  sub: AdminSubmission | null;
  showTeam?: boolean;
  onClose: () => void;
  onDelete: (id: string) => void;
}) {
  const { t } = useTranslation();

  return (
    <Dialog open={!!sub} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("admin.submissions.dialog_title")}</DialogTitle>
        </DialogHeader>
        {sub && (
          <div className="space-y-3 text-sm">
            {showTeam && (
              <DialogRow label={t("table.col_team", { defaultValue: "Team" })}>
                <TeamLink id={sub.team_id} name={sub.team_name} />
              </DialogRow>
            )}
            <DialogRow label={t("table.col_challenge", { defaultValue: "Challenge" })}>
              <ChallengeLink id={sub.question_challenge_id} name={sub.question_challenge_title} />
            </DialogRow>
            <DialogRow label={t("table.col_question", { defaultValue: "Question" })}>
              {sub.question_label ?? <EmptyCell />}
            </DialogRow>
            <div className="rounded-md bg-muted p-3 font-mono text-sm break-all">{sub.answer}</div>
            <div className="flex justify-end pt-2">
              <ConfirmDialog
                description={t("admin.submissions.delete_confirm")}
                confirmLabel={t("common.delete")}
                onConfirm={() => {
                  onDelete(sub.id);
                  onClose();
                }}
                trigger={
                  <Button variant="destructive" size="sm">
                    <Trash2 />
                    {t("common.delete")}
                  </Button>
                }
              />
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function DialogRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2">
      <span className="text-muted-foreground shrink-0">{label}:</span>
      {children}
    </div>
  );
}
