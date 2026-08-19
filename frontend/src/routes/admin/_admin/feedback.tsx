import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { MessageSquareHeart, Star } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { type Column, DataTable, useTableState } from "@/components/data-table";
import { PageHeader } from "@/components/page-header";
import { ChallengeLink, DateCell, EmptyCell, idColumn, TeamLink } from "@/components/table-cells";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { type AdminFeedback, getAdminFeedbacks } from "@/lib/api";

export const Route = createFileRoute("/admin/_admin/feedback")({
  component: FeedbackPage,
});

function Stars({ rating }: { rating: number }) {
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

function FeedbackPage() {
  const { t } = useTranslation();
  const [detail, setDetail] = useState<AdminFeedback | null>(null);

  const table = useTableState();

  const {
    data: response,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["admin", "feedback", table.queryString],
    queryFn: () => getAdminFeedbacks(table.queryString),
    placeholderData: (prev) => prev,
  });

  const columns: Column<AdminFeedback>[] = [
    idColumn<AdminFeedback>(t),
    {
      key: "challenge_title",
      header: t("table.col_challenge", { defaultValue: "Challenge" }),
      cell: (fb) => <ChallengeLink id={fb.challenge_id} name={fb.challenge_title} />,
    },
    {
      key: "team_name",
      header: t("table.col_team", { defaultValue: "Team" }),
      cell: (fb) => <TeamLink id={fb.team_id} name={fb.team_name} />,
    },
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

  return (
    <>
      <div className="p-8 space-y-6">
        <PageHeader icon={MessageSquareHeart} title={t("admin.nav.feedback")} />

        <DataTable
          columns={columns}
          response={response}
          table={table}
          isLoading={isLoading}
          isFetching={isFetching}
          rowKey={(fb) => fb.id}
          onRefresh={() => void refetch()}
          onRowClick={(fb) => setDetail(fb)}
        />
      </div>

      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("admin.feedback.dialog_title")}</DialogTitle>
          </DialogHeader>
          {detail && (
            <div className="space-y-3 text-sm">
              <div className="flex gap-2">
                <span className="text-muted-foreground shrink-0">
                  {t("table.col_challenge", { defaultValue: "Challenge" })}:
                </span>
                <ChallengeLink id={detail.challenge_id} name={detail.challenge_title} />
              </div>
              <div className="flex gap-2">
                <span className="text-muted-foreground shrink-0">
                  {t("table.col_team", { defaultValue: "Team" })}:
                </span>
                <TeamLink id={detail.team_id} name={detail.team_name} />
              </div>
              <div className="flex gap-2">
                <span className="text-muted-foreground shrink-0">
                  {t("admin.feedback.col_rating")}:
                </span>
                <Stars rating={detail.rating} />
              </div>
              <div className="rounded-md bg-muted p-3 text-sm whitespace-pre-wrap">
                {detail.comment ?? t("admin.feedback.no_comment")}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
