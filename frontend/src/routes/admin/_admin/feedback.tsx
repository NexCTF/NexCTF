import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { MessageSquareHeart } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { DataTable, useTableState } from "@/components/data-table";
import { FeedbackDetailDialog, useFeedbackColumns } from "@/components/feedback-table";
import { PageHeader } from "@/components/page-header";
import { type AdminFeedback, getAdminFeedbacks } from "@/lib/api";

export const Route = createFileRoute("/admin/_admin/feedback")({
  component: FeedbackPage,
});

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

  const columns = useFeedbackColumns();

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

      <FeedbackDetailDialog feedback={detail} onClose={() => setDetail(null)} />
    </>
  );
}
