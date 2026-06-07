import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { ClipboardList, Maximize2, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { type Column, DataTable, useTableState } from "@/components/data-table";
import { IdCell } from "@/components/id-cell";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  type AdminSubmission,
  apiErrorMessage,
  deleteAdminSubmission,
  getAdminSubmissions,
} from "@/lib/api";

export const Route = createFileRoute("/admin/_admin/submissions")({
  component: SubmissionsPage,
});

function SubmissionsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [answerDialog, setAnswerDialog] = useState<AdminSubmission | null>(null);

  const table = useTableState();

  const {
    data: response,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["admin", "submissions", table.queryString],
    queryFn: () => getAdminSubmissions(table.queryString),
    placeholderData: (prev) => prev,
  });

  const { mutate: remove } = useMutation({
    mutationFn: (id: string) => deleteAdminSubmission(id),
    onSuccess: () => {
      toast.success(t("admin.submissions.deleted"));
      void queryClient.invalidateQueries({
        queryKey: ["admin", "submissions"],
      });
      void queryClient.invalidateQueries({ queryKey: ["admin", "scoreboard"] });
    },
    onError: (err) => toast.error(apiErrorMessage(err, t("admin.submissions.delete_error"))),
  });

  const COLUMNS: Column<AdminSubmission>[] = [
    {
      key: "id",
      header: "ID",
      sortable: false,
      cell: (sub) => <IdCell id={sub.id} />,
      className: "w-32",
    },
    {
      key: "team_name",
      header: t("admin.submissions.col_team"),
      cell: (sub) => <span className="font-medium">{sub.team_name ?? sub.team_id}</span>,
    },
    {
      key: "question_challenge_title",
      header: t("admin.submissions.col_challenge"),
      cell: (sub) => (
        <span className="text-muted-foreground">{sub.question_challenge_title ?? "—"}</span>
      ),
    },
    {
      key: "question_label",
      header: t("admin.submissions.col_question"),
      cell: (sub) => (
        <span className="text-muted-foreground text-xs">{sub.question_label ?? "—"}</span>
      ),
    },
    {
      key: "answer",
      header: t("admin.submissions.col_answer"),
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
      header: t("admin.submissions.col_correct"),
      cell: (sub) => (
        <span className={sub.is_correct ? "text-green-500 font-semibold" : "text-muted-foreground"}>
          {sub.is_correct ? "✓" : "✗"}
        </span>
      ),
      className: "w-20",
    },
    {
      key: "points_earned",
      header: t("admin.submissions.col_points"),
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
      header: t("admin.submissions.col_date"),
      sortable: true,
      cell: (sub) => (
        <span className="text-muted-foreground text-xs whitespace-nowrap">
          {new Date(sub.created_at).toLocaleString()}
        </span>
      ),
      className: "w-40",
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
              if (confirm(t("admin.submissions.delete_confirm"))) remove(sub.id);
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
      <div className="p-8 space-y-6">
        <div className="flex items-center gap-3">
          <ClipboardList className="size-6 text-muted-foreground" />
          <h1 className="text-2xl font-bold">{t("admin.nav.submissions")}</h1>
        </div>

        <DataTable
          columns={COLUMNS}
          response={response}
          table={table}
          isLoading={isLoading}
          isFetching={isFetching}
          rowKey={(sub) => sub.id}
          onRefresh={() => void refetch()}
          onRowClick={(sub) => setAnswerDialog(sub)}
        />
      </div>

      <Dialog open={!!answerDialog} onOpenChange={(o) => !o && setAnswerDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("admin.submissions.dialog_title")}</DialogTitle>
          </DialogHeader>
          {answerDialog && (
            <div className="space-y-3 text-sm">
              <div className="flex gap-2">
                <span className="text-muted-foreground shrink-0">
                  {t("admin.submissions.col_team")}:
                </span>
                <span>{answerDialog.team_name ?? answerDialog.team_id}</span>
              </div>
              <div className="flex gap-2">
                <span className="text-muted-foreground shrink-0">
                  {t("admin.submissions.col_challenge")}:
                </span>
                <span>{answerDialog.question_challenge_title ?? "—"}</span>
              </div>
              <div className="flex gap-2">
                <span className="text-muted-foreground shrink-0">
                  {t("admin.submissions.col_question")}:
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
                    if (confirm(t("admin.submissions.delete_confirm"))) {
                      remove(answerDialog.id);
                      setAnswerDialog(null);
                    }
                  }}
                >
                  <Trash2 className="h-3.5 w-3.5 mr-1.5" />
                  {t("admin.submissions.delete_btn")}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
