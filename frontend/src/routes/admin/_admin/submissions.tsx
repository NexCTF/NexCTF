import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { ClipboardList } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { DataTable, useTableState } from "@/components/data-table";
import { PageHeader } from "@/components/page-header";
import { SubmissionAnswerDialog, useSubmissionColumns } from "@/components/submission-table";
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

  const columns = useSubmissionColumns({
    onAnswerClick: setAnswerDialog,
    onDelete: remove,
  });

  return (
    <>
      <div className="p-8 space-y-6">
        <PageHeader icon={ClipboardList} title={t("admin.nav.submissions")} />

        <DataTable
          columns={columns}
          response={response}
          table={table}
          isLoading={isLoading}
          isFetching={isFetching}
          rowKey={(sub) => sub.id}
          onRefresh={() => void refetch()}
          onRowClick={(sub) => setAnswerDialog(sub)}
        />
      </div>

      <SubmissionAnswerDialog
        sub={answerDialog}
        onClose={() => setAnswerDialog(null)}
        onDelete={remove}
      />
    </>
  );
}
