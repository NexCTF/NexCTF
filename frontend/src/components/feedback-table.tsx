import { Star } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { Column } from "@/components/data-table";
import { ChallengeLink, DateCell, EmptyCell, idColumn, TeamLink } from "@/components/table-cells";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { AdminFeedback } from "@/lib/api";

export function Stars({ rating }: { rating: number }) {
  return (
    <span className="flex gap-0.5" role="img" aria-label={`${rating}/5`}>
      {[1, 2, 3, 4, 5].map((value) => (
        <Star
          key={value}
          className={`size-3.5 ${
            value <= rating ? "fill-yellow-400 text-yellow-400" : "text-muted-foreground/40"
          }`}
        />
      ))}
    </span>
  );
}

/**
 * Feedback columns, shared with the team detail page.
 *
 * `showTeam` is off there since every row belongs to the same team.
 */
export function useFeedbackColumns({
  showTeam = true,
}: {
  showTeam?: boolean;
} = {}): Column<AdminFeedback>[] {
  const { t } = useTranslation();

  return [
    idColumn<AdminFeedback>(t),
    {
      key: "challenge_title",
      header: t("table.col_challenge", { defaultValue: "Challenge" }),
      cell: (fb) => <ChallengeLink id={fb.challenge_id} name={fb.challenge_title} />,
    },
    ...(showTeam
      ? [
          {
            key: "team_name",
            header: t("table.col_team", { defaultValue: "Team" }),
            cell: (fb: AdminFeedback) => <TeamLink id={fb.team_id} name={fb.team_name} />,
          },
        ]
      : []),
    {
      key: "rating",
      header: t("admin.feedback.col_rating"),
      sortable: true,
      cell: (fb) => <Stars rating={fb.rating} />,
      className: "w-32",
    },
    {
      key: "comment",
      header: t("admin.feedback.col_comment"),
      sortable: false,
      cell: (fb) =>
        fb.comment ? (
          <span className="block max-w-[320px] truncate text-muted-foreground text-xs">
            {fb.comment}
          </span>
        ) : (
          <EmptyCell />
        ),
    },
    {
      key: "created_at",
      header: t("table.col_date", { defaultValue: "Date" }),
      sortable: true,
      cell: (fb) => <DateCell value={fb.created_at} />,
      className: "w-40",
    },
  ];
}

/** The full comment plus its relations. */
export function FeedbackDetailDialog({
  feedback,
  showTeam = true,
  onClose,
}: {
  feedback: AdminFeedback | null;
  showTeam?: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation();

  return (
    <Dialog open={!!feedback} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("admin.feedback.dialog_title")}</DialogTitle>
        </DialogHeader>
        {feedback && (
          <div className="space-y-3 text-sm">
            <DialogRow label={t("table.col_challenge", { defaultValue: "Challenge" })}>
              <ChallengeLink id={feedback.challenge_id} name={feedback.challenge_title} />
            </DialogRow>
            {showTeam && (
              <DialogRow label={t("table.col_team", { defaultValue: "Team" })}>
                <TeamLink id={feedback.team_id} name={feedback.team_name} />
              </DialogRow>
            )}
            <DialogRow label={t("admin.feedback.col_rating")}>
              <Stars rating={feedback.rating} />
            </DialogRow>
            <div className="rounded-md bg-muted p-3 text-sm whitespace-pre-wrap">
              {feedback.comment ?? t("admin.feedback.no_comment")}
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
