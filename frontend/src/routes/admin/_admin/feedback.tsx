import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { MessageSquareHeart, Star } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { type Column, DataTable, useTableState } from "@/components/data-table";
import { IdCell } from "@/components/id-cell";
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

  const COLUMNS: Column<AdminFeedback>[] = [
    {
      key: "id",
      header: "ID",
      sortable: false,
      cell: (fb) => <IdCell id={fb.id} />,
      className: "w-32",
    },
    {
      key: "challenge_title",
      header: t("admin.feedback.col_challenge"),
      cell: (fb) => <span className="font-medium">{fb.challenge_title ?? fb.challenge_id}</span>,
    },
    {
      key: "team_name",
      header: t("admin.feedback.col_team"),
      cell: (fb) => <span className="text-muted-foreground">{fb.team_name ?? fb.team_id}</span>,
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
      cell: (fb) => (
        <span className="block max-w-[320px] truncate text-muted-foreground text-xs">
          {fb.comment ?? "—"}
        </span>
      ),
    },
    {
      key: "created_at",
      header: t("admin.feedback.col_date"),
      sortable: true,
      cell: (fb) => (
        <span className="text-muted-foreground text-xs whitespace-nowrap">
          {new Date(fb.created_at).toLocaleString()}
        </span>
      ),
      className: "w-40",
    },
  ];

  return (
    <>
      <div className="p-8 space-y-6">
        <div className="flex items-center gap-3">
          <MessageSquareHeart className="size-6 text-muted-foreground" />
          <h1 className="text-2xl font-bold">{t("admin.nav.feedback")}</h1>
        </div>

        <DataTable
          columns={COLUMNS}
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
                  {t("admin.feedback.col_challenge")}:
                </span>
                <span>{detail.challenge_title ?? detail.challenge_id}</span>
              </div>
              <div className="flex gap-2">
                <span className="text-muted-foreground shrink-0">
                  {t("admin.feedback.col_team")}:
                </span>
                <span>{detail.team_name ?? detail.team_id}</span>
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
